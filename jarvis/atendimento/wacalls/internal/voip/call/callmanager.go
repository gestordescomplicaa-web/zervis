package call

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"sync"
	"sync/atomic"
	"time"
	"wacalls/internal/voip/core"
	"wacalls/internal/voip/media"
	"wacalls/internal/voip/signaling"
	"wacalls/internal/voip/transport"
	"wacalls/internal/voip/wanode"

	"go.mau.fi/whatsmeow/types"
)

type CallManager struct {
	sock core.VoipSocket
	log  *slog.Logger

	mu          sync.Mutex
	currentCall *CallInfo

	rtpSession  *media.RtpSession
	srtpSession *media.SrtpSession
	codec       media.Codec
	relay       RelayTransport

	selfSsrc      uint32
	peerSsrcs     []uint32
	actualPeerSet bool

	firstPacketSent       bool
	initialTransportSent  bool
	outgoingPreacceptSent bool
	acceptedByJid         string
	peerEncryptionKey     []byte
	debeEnabled           bool

	encodeBuf    []float32
	encodeBufPos int

	lastCaptureAt time.Time
	keepaliveStop chan struct{}

	OnStateChange func(*CallInfo)
	OnIncoming    func(*CallInfo)
	OnEnded       func(*CallInfo)
	OnPeerAudio   func([]float32)

	// Diagnostics (packet-loss debugging). Opt-in via WACALLS_PKT_STATS env.
	// Counts where inbound relay packets go in onRelayData, plus a per-RTP
	// payload-type histogram so a codec/PT mismatch is visible.
	dbgRecv         atomic.Uint64
	dbgStun         atomic.Uint64
	dbgNonRtp       atomic.Uint64
	dbgShort        atomic.Uint64
	dbgSelfSsrc     atomic.Uint64
	dbgUnprotectErr atomic.Uint64
	dbgEmptyPayload atomic.Uint64
	dbgDecodeErr    atomic.Uint64
	dbgDelivered    atomic.Uint64
	dbgSent         atomic.Uint64
	dbgPT           [128]atomic.Uint64
}

func NewCallManager(sock core.VoipSocket, log *slog.Logger) *CallManager {
	if log == nil {
		log = slog.Default()
	}
	m := &CallManager{
		sock:        sock,
		log:         log,
		debeEnabled: true,
	}
	relay := transport.NewSctpRelayManager(log)
	relay.SetOnConnected(func(ip string, port int) { m.onRelayConnected() })
	relay.SetOnReceive(func(data []byte) { m.onRelayData(data) })
	m.relay = relay
	if os.Getenv("WACALLS_PKT_STATS") != "" {
		m.startPktStatsLoop()
	}
	return m
}

// resetPktStats zeroes the packet-loss diagnostic counters so each call's
// histogram starts clean. No-op overhead when WACALLS_PKT_STATS is off.
func (m *CallManager) resetPktStats() {
	m.dbgRecv.Store(0)
	m.dbgStun.Store(0)
	m.dbgNonRtp.Store(0)
	m.dbgShort.Store(0)
	m.dbgSelfSsrc.Store(0)
	m.dbgUnprotectErr.Store(0)
	m.dbgEmptyPayload.Store(0)
	m.dbgDecodeErr.Store(0)
	m.dbgDelivered.Store(0)
	m.dbgSent.Store(0)
	for i := range m.dbgPT {
		m.dbgPT[i].Store(0)
	}
}

// startPktStatsLoop logs a PKT-STATS line every 2s while a call is flowing
// packets, so we can see exactly where inbound audio dies (relay vs PT
// mismatch vs SRTP vs decode) and whether we are transmitting.
func (m *CallManager) startPktStatsLoop() {
	go func() {
		t := time.NewTicker(2 * time.Second)
		defer t.Stop()
		var last uint64
		for range t.C {
			recv := m.dbgRecv.Load()
			if recv == last {
				continue // no inbound activity since last tick
			}
			last = recv
			args := []any{
				"call_id", m.currentCallID(),
				"recv", recv,
				"stun", m.dbgStun.Load(),
				"non_rtp", m.dbgNonRtp.Load(),
				"short", m.dbgShort.Load(),
				"self_ssrc", m.dbgSelfSsrc.Load(),
				"unprotect_err", m.dbgUnprotectErr.Load(),
				"empty", m.dbgEmptyPayload.Load(),
				"decode_err", m.dbgDecodeErr.Load(),
				"delivered", m.dbgDelivered.Load(),
				"sent", m.dbgSent.Load(),
			}
			for i := range m.dbgPT {
				if c := m.dbgPT[i].Load(); c > 0 {
					args = append(args, fmt.Sprintf("pt%d", i), c)
				}
			}
			m.log.Info("PKT-STATS", args...)
		}
	}()
}

func (m *CallManager) currentCallID() string {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.currentCall != nil {
		return m.currentCall.CallID
	}
	return ""
}

func (m *CallManager) CurrentCall() *CallInfo {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.currentCall
}

func (m *CallManager) emitState() {
	if m.OnStateChange != nil && m.currentCall != nil {
		m.OnStateChange(m.currentCall)
	}
}

func (m *CallManager) StartCall(ctx context.Context, callID string, peerJid types.JID, isVideo bool) error {
	m.mu.Lock()
	if m.currentCall != nil && !m.currentCall.IsEnded() {
		m.mu.Unlock()
		return &CallError{"a call is already in progress"}
	}

	mediaType := core.CallMediaTypeAudio
	if isVideo {
		mediaType = core.CallMediaTypeVideo
	}
	creator := m.sock.OwnLID()
	if creator.IsEmpty() {
		creator = m.sock.OwnPN()
	}
	// Sem LID não existe oferta válida: o servidor ignora o stanza endereçado ao
	// PN e o operador só descobre 15s depois, por timeout. Falha aqui, imediata
	// e com causa no log.
	resolved, resolveErr := m.sock.ResolveLIDForCall(ctx, peerJid)
	if resolveErr != nil {
		m.mu.Unlock()
		m.log.Error("call offer aborted", "call_id", callID,
			"peer", peerJid.String(), "error", resolveErr)
		return resolveErr
	}

	call := NewOutgoingCall(callID, resolved.String(), creator.String(), mediaType)
	callKey := media.GenerateCallKey()
	call.EncryptionKey = callKey
	m.currentCall = call
	m.acceptedByJid = ""
	m.peerEncryptionKey = nil
	m.actualPeerSet = false
	m.initialTransportSent = false
	m.outgoingPreacceptSent = false

	selfJid := creator.String()
	m.selfSsrc = media.GenerateSecureSsrc(callID, selfJid, 0)
	m.rtpSession = media.NewWhatsAppOpusSession(m.selfSsrc)
	m.peerSsrcs = []uint32{media.GenerateSecureSsrc(callID, resolved.String(), 0)}
	m.initCodec()
	m.mu.Unlock()

	offer, err := signaling.BuildOfferStanza(ctx, m.sock, callID, callKey, resolved, isVideo)
	if err != nil {
		return err
	}
	ackNode, err := m.sock.Query(ctx, offer)
	if err != nil {
		m.mu.Lock()
		if m.currentCall == call {
			_ = call.ApplyTransition(Transition{Type: TransitionTerminated, Reason: core.EndCallReasonFailed})
			m.emitState()
		}
		m.mu.Unlock()
		m.log.Error("call offer failed", "call_id", callID, "peer", resolved.String(), "error", err)
		return err
	}

	m.mu.Lock()
	_ = m.currentCall.ApplyTransition(Transition{Type: TransitionOfferSent})
	m.emitState()
	m.mu.Unlock()

	if ackNode != nil {
		go m.HandleCallAck(context.Background(), ackNode)
	}

	m.log.Info("call offer sent", "call_id", callID, "peer", resolved.String())
	return nil
}

func (m *CallManager) AcceptCall(ctx context.Context, callID string) error {
	m.mu.Lock()
	call := m.currentCall
	if call == nil || call.CallID != callID {
		m.mu.Unlock()
		return &CallError{"no incoming call with id " + callID}
	}
	if !call.CanAccept() {
		m.mu.Unlock()
		return &CallError{"call cannot be accepted in state " + string(call.StateData.State)}
	}
	if len(call.EncryptionKey) == 0 {
		m.mu.Unlock()
		return &CallError{"incoming call has no decrypted media key"}
	}
	_ = call.ApplyTransition(Transition{Type: TransitionLocalAccepted})
	m.emitState()
	peer := wanode.MustJID(call.PeerJid)
	creator := wanode.MustJID(call.CallCreator)
	isVideo := call.MediaType == core.CallMediaTypeVideo
	relayData := call.RelayData
	m.mu.Unlock()

	acceptNode := signaling.BuildAcceptStanza(callID, peer, creator, isVideo)
	if err := m.sock.SendNode(ctx, acceptNode); err != nil {
		m.mu.Lock()
		if m.currentCall == call && !call.IsEnded() {
			_ = call.ApplyTransition(Transition{Type: TransitionTerminated, Reason: core.EndCallReasonFailed})
			m.emitState()
		}
		m.mu.Unlock()
		m.cleanupMedia()
		m.log.Error("accept send error", "call_id", callID, "peer", peer.String(), "error", err)
		return fmt.Errorf("send inbound accept: %w", err)
	}
	m.log.Info("inbound accept sent", "call_id", callID, "peer", peer.String(),
		"wire", "audio,net:2,encopt,capability")

	if relayData != nil {
		m.setupIncomingMedia(call, relayData)
		m.connectRelays(relayData.Endpoints)
	} else {
		m.log.Warn("call accepted but no relay endpoints yet; media path waits for a transport message", "call_id", callID)
	}
	m.log.Info("call accepted", "call_id", callID)
	return nil
}

func (m *CallManager) setupIncomingMedia(call *CallInfo, relayData *core.RelayData) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if len(relayData.ParticipantJids) > 0 {
		ourBase := wanode.CleanJID(m.ownCredJid())
		ourDeviceJid := ensureDeviceJid(findOurDevice(relayData.ParticipantJids, ourBase, m.ownCredJid()))
		if newSelf := media.GenerateSecureSsrc(call.CallID, ourDeviceJid, 0); newSelf != m.selfSsrc {
			m.selfSsrc = newSelf
			m.rtpSession = media.NewWhatsAppOpusSession(newSelf)
		}
		if peer := firstPeerDevice(relayData.ParticipantJids, ourBase); peer != "" {
			m.peerSsrcs = []uint32{media.GenerateSecureSsrc(call.CallID, ensureDeviceJid(peer), 0)}
			m.actualPeerSet = true

			// Visibilidade de qual dispositivo do destino foi escolhido, quando
			// ele tem mais de um (celular + WhatsApp Web).
			//
			// ATENCAO ao ler este log: ele NAO explica a ligacao que cai quando
			// o celular para de tocar. Essa hipotese foi LEVANTADA aqui e
			// DERRUBADA pela medicao de 06/08/2026 (WACALLS_PKT_STATS): o audio
			// chegava perfeito ate o ultimo segundo — self_ssrc=0,
			// unprotect_err=0, delivered subindo — e a ligacao foi cortada de
			// fora, sem degradacao. Ver "Limitacao conhecida" em PLANO-TRIAL.md.
			//
			// Repare tambem que este ponto so roda em AcceptCall, ou seja
			// quando NOS atendemos (inbound). Na ligacao outbound quem escolhe
			// o peer e o HandleCallAccept (callmanager_signaling.go), que usa o
			// jid de quem de fato atendeu. Foi por instrumentar aqui que a
			// primeira investigacao ficou cega.
			//
			// Nao muda comportamento nenhum.
			var ignorados []string
			for _, jid := range relayData.ParticipantJids {
				if wanode.CleanJID(jid) != ourBase && jid != peer {
					ignorados = append(ignorados, jid)
				}
			}
			if len(ignorados) > 0 {
				m.log.Warn("destino com MULTIPLOS dispositivos - assinando so o primeiro",
					"call_id", call.CallID, "escolhido", peer, "ignorados", ignorados,
					"total_participantes", len(relayData.ParticipantJids))
			} else {
				m.log.Info("peer de midia definido", "call_id", call.CallID, "peer", peer)
			}
		}
	}
	m.relay.SetSubscriptionSsrc(firstSsrc(m.peerSsrcs))
	m.initSrtpKeysLocked()
}

func (m *CallManager) RejectCall(ctx context.Context, callID string, reason core.EndCallReason) error {
	m.mu.Lock()
	call := m.currentCall
	if call == nil || call.CallID != callID {
		m.mu.Unlock()
		return &CallError{"no call with id " + callID}
	}
	_ = call.ApplyTransition(Transition{Type: TransitionLocalRejected, Reason: reason})
	node := signaling.BuildRejectStanza(wanode.MustJID(call.PeerJid), call.CallID, wanode.MustJID(call.CallCreator))
	m.emitState()
	m.mu.Unlock()

	go func() { _, _ = m.sock.Query(ctx, node) }()
	m.cleanupMedia()
	return nil
}

func (m *CallManager) EndCall(ctx context.Context, reason core.EndCallReason) error {
	m.mu.Lock()
	call := m.currentCall
	if call == nil || call.IsEnded() {
		m.mu.Unlock()
		return nil
	}
	_ = call.ApplyTransition(Transition{Type: TransitionTerminated, Reason: reason})
	node := signaling.BuildTerminateStanza(wanode.MustJID(call.PeerJid), call.CallID, wanode.MustJID(call.CallCreator))
	ended := call
	m.emitState()
	m.mu.Unlock()

	go func() { _, _ = m.sock.Query(ctx, node) }()
	if m.OnEnded != nil {
		m.OnEnded(ended)
	}
	m.cleanupMedia()
	return nil
}

func (m *CallManager) ownCredJid() string {
	lid := m.sock.OwnLID()
	if !lid.IsEmpty() {
		return lid.String()
	}
	return m.sock.OwnPN().String()
}

type CallError struct{ Msg string }

func (e *CallError) Error() string { return e.Msg }
