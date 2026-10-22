package main

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"wacalls/internal/voip/call"
	"wacalls/internal/voip/core"
	"wacalls/internal/voip/signaling"
	"wacalls/internal/voip/wanode"
	"wacalls/internal/wa"

	"go.mau.fi/whatsmeow"
	waBinary "go.mau.fi/whatsmeow/binary"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
)

type Session struct {
	id   string
	name string
	mgr  *SessionManager
	log  *slog.Logger

	client *whatsmeow.Client
	reg    *callRegistry

	mu   sync.Mutex
	auth AuthSnapshot

	// Estrangulamento do aviso "captura desligada" (ver msgcapture.go).
	msgMu      sync.Mutex
	msgAvisoEm time.Time

	// Mensagens transacionais da Agenda saem em série por sessão. Isto fecha a
	// corrida entre duas réplicas do painel usando a mesma chave idempotente sem
	// tocar no callback de chamadas nem no fluxo de áudio.
	agendaMessageMu sync.Mutex
}

func newSession(mgr *SessionManager, id, name string, client *whatsmeow.Client) *Session {
	s := &Session{
		id:     id,
		name:   name,
		mgr:    mgr,
		log:    mgr.log.With("session", id),
		client: client,
		auth:   AuthSnapshot{State: "connecting"},
		reg:    newCallRegistry(),
	}
	client.AddEventHandler(s.handleEvent)
	return s
}

func (s *Session) createCall(callID string) *call.CallManager {
	cm := call.NewCallManager(wa.NewSocket(s.client), s.log)
	s.wireCall(cm, callID)
	s.reg.add(callID, &activeCall{cm: cm})
	return cm
}

func (s *Session) wireCall(cm *call.CallManager, callID string) {
	cm.OnIncoming = func(c *call.CallInfo) {
		phone := c.CallerPn
		if phone == "" {
			phone = s.resolvePhone(c.PeerJid)
		}
		s.mgr.broker.upsertCall(CallRecord{
			SessionID: s.id, CallID: c.CallID, Direction: "inbound", Peer: c.PeerJid,
			Phone: phone, StartedAt: time.Now().UnixMilli(), Status: StatusRinging,
		})
		s.mgr.broker.emitIncoming(s.id, c.CallID, c.PeerJid, phone)
	}
	cm.OnStateChange = func(c *call.CallInfo) {
		if c.IsEnded() {
			s.removeCall(c.CallID)
			s.mgr.broker.endCall(c.CallID, string(c.StateData.EndReason))
			return
		}
		dir := "outbound"
		if c.Direction == core.CallDirectionIncoming {
			dir = "inbound"
		}
		existing, _ := s.mgr.broker.getCall(c.CallID)
		rec := CallRecord{
			SessionID: s.id, CallID: c.CallID, Direction: dir, Peer: c.PeerJid,
			StartedAt: time.Now().UnixMilli(), Status: mapStatus(c.StateData.State),
		}
		if existing != nil {
			rec.Owner = existing.Owner
			rec.StartedAt = existing.StartedAt
			rec.Phone = existing.Phone
		}
		if rec.Phone == "" {
			rec.Phone = s.resolvePhone(c.PeerJid)
		}
		s.mgr.broker.upsertCall(rec)
	}
	cm.OnEnded = func(c *call.CallInfo) {
		s.removeCall(c.CallID)
		s.mgr.broker.endCall(c.CallID, string(c.StateData.EndReason))
	}
	cm.OnPeerAudio = func(pcm16 []float32) {
		ac, ok := s.reg.get(callID)
		if !ok || ac.bridge == nil {
			return
		}
		_ = ac.bridge.WritePCM(pcm16)
	}
}

// resolvePhone tenta descobrir o número de telefone real por trás de um JID.
// Se já é um número (s.whatsapp.net), devolve direto. Se é um LID (@lid, que mascara
// o telefone), consulta o mapeamento LID->PN que o whatsmeow mantém (preenchido por
// contato/histórico/grupo). Devolve "" se não der pra resolver — o chamador faz fallback.
func (s *Session) resolvePhone(peerJid string) string {
	jid, err := types.ParseJID(peerJid)
	if err != nil {
		return ""
	}
	if jid.Server == types.DefaultUserServer {
		return jid.User
	}
	if jid.Server != types.HiddenUserServer {
		return ""
	}
	if s.client == nil || s.client.Store == nil || s.client.Store.LIDs == nil {
		return ""
	}
	ctx, cancel := context.WithTimeout(s.mgr.appCtx, 3*time.Second)
	defer cancel()
	pn, err := s.client.Store.LIDs.GetPNForLID(ctx, jid)
	if err != nil || pn.IsEmpty() {
		return ""
	}
	return pn.User
}

func (s *Session) startOutgoing(ctx context.Context, peer types.JID, isVideo bool) (string, error) {
	callID := signaling.GenerateCallID()
	cm := s.createCall(callID)
	if err := cm.StartCall(ctx, callID, peer, isVideo); err != nil {
		s.removeCall(callID)
		return "", err
	}
	return callID, nil
}

// resolvePhoneCandidates asks WhatsApp which of the supplied PN variants is
// actually registered. A successful HTTP call offer is not enough: WhatsApp
// can accept an offer for a PN that does not belong to a real account. Keeping
// this check in the paired session also makes the answer tenant/session-specific.
func (s *Session) resolvePhoneCandidates(ctx context.Context, phones []string) ([]string, error) {
	if s.client == nil {
		return nil, fmt.Errorf("session client unavailable")
	}
	jids := make([]types.JID, 0, len(phones))
	seen := make(map[string]struct{}, len(phones))
	for _, phone := range phones {
		phone = normalizePhone(phone)
		if phone == "" {
			continue
		}
		jid := types.NewJID(phone, types.DefaultUserServer)
		if _, ok := seen[jid.String()]; ok {
			continue
		}
		seen[jid.String()] = struct{}{}
		jids = append(jids, jid)
	}
	if len(jids) == 0 {
		return nil, fmt.Errorf("no phone candidates")
	}
	queries := make([]string, 0, len(jids))
	for _, jid := range jids {
		queries = append(queries, "+"+jid.User)
	}
	// GetUserInfo devolve uma entrada para cada consulta, inclusive quando ela
	// não prova que o telefone existe. IsOnWhatsApp é o contrato correto: IsIn
	// confirma o registro e JID traz a identidade canônica.
	onWhatsApp, err := s.client.IsOnWhatsApp(ctx, queries)
	if err != nil {
		return nil, err
	}
	byPhone := make(map[string]types.IsOnWhatsAppResponse, len(onWhatsApp))
	for _, response := range onWhatsApp {
		phone := normalizePhone(response.Query)
		if phone != "" {
			byPhone[phone] = response
		}
	}
	resolved := make([]resolvedPhoneCandidate, 0, len(jids))
	for _, jid := range jids {
		response, ok := byPhone[jid.User]
		if !ok || !response.IsIn {
			continue
		}
		// IsOnWhatsApp confirma o registro, mas não hidrata necessariamente o
		// mapa PN -> LID usado pela sinalização de chamadas. Antes da troca para
		// IsOnWhatsApp, GetUserInfo fazia esse preenchimento como efeito colateral;
		// perdê-lo fez a oferta sair para o PN e ficar sem ACK em alguns celulares.
		// Consulte a identidade canônica agora para que o WaCalls tenha o LID antes
		// de criar a oferta.
		canonical := response.JID
		if canonical.IsEmpty() {
			canonical = jid
		}
		canonicalPN := types.NewJID(canonical.User, types.DefaultUserServer)
		identity := canonicalPN.ToNonAD().String()
		lid := types.EmptyJID
		if info, infoErr := s.client.GetUserInfo(ctx, []types.JID{canonicalPN}); infoErr != nil {
			s.log.Warn("whatsapp canonical identity lookup failed",
				"phone", jid.User, "canonical", canonicalPN.String(), "error", infoErr)
		} else {
			for _, userInfo := range info {
				if !userInfo.LID.IsEmpty() {
					lid = userInfo.LID
					break
				}
			}
			if !lid.IsEmpty() {
				identity = lid.ToNonAD().String()
			}
		}
		s.log.Info("whatsapp phone resolved",
			"phone", jid.User, "canonical", canonicalPN.String(),
			"registered", response.IsIn, "lid", lid.String())
		// Devolve a grafia CANÔNICA, não a solicitada. A hidratação do mapa
		// PN -> LID acima acontece para canonicalPN; devolver a outra grafia
		// (ex.: com o nono dígito quando o WhatsApp indexa sem ele) faz a
		// discagem procurar um LID que nunca foi hidratado, cair no PN e ficar
		// sem ACK por 15s.
		resolved = append(resolved, resolvedPhoneCandidate{
			phone: canonicalPN.User, identity: identity,
		})
	}
	return distinctRegisteredPhones(resolved), nil
}

type resolvedPhoneCandidate struct {
	phone    string
	identity string
}

// distinctRegisteredPhones preserva a ordem solicitada: o bridge envia a
// forma mais rápida primeiro. Só elimina duplicatas quando o WhatsApp provou,
// pelo LID, que são a mesma conta; LIDs diferentes continuam ambíguos.
func distinctRegisteredPhones(candidates []resolvedPhoneCandidate) []string {
	registered := make([]string, 0, len(candidates))
	seen := make(map[string]struct{}, len(candidates))
	for _, candidate := range candidates {
		identity := candidate.identity
		if identity == "" {
			identity = candidate.phone
		}
		if _, ok := seen[identity]; ok {
			continue
		}
		seen[identity] = struct{}{}
		registered = append(registered, candidate.phone)
	}
	return registered
}

func (s *Session) callForEvent(from types.JID, data *waBinary.Node) (*activeCall, bool) {
	callID := callIDFromNode(wrapCall(from, data))
	if callID == "" {
		return nil, false
	}
	return s.reg.get(callID)
}

func (s *Session) onIncomingOffer(ctx context.Context, evt *events.CallOffer) {
	node := wrapCall(evt.From, evt.Data)
	callID := callIDFromNode(node)
	if callID == "" {
		return
	}
	if max := s.mgr.maxCalls; max > 0 && s.reg.count() >= max {
		s.rejectOffer(ctx, node, evt.From, "session at capacity")
		return
	}
	// O próprio evento de chamada pode trazer o par LID<->PN mesmo quando o
	// histórico ainda não hidratou o cache. Persistir antes do callback evita
	// mostrar os dígitos opacos do LID como se fossem um telefone.
	if !evt.CallCreatorAlt.IsEmpty() {
		s.client.StoreLIDPNMapping(ctx, evt.CallCreator, evt.CallCreatorAlt)
	}
	cm := s.createCall(callID)
	if err := cm.HandleCallOffer(ctx, node, evt.From); err != nil {
		s.removeCall(callID)
		s.rejectOffer(ctx, node, evt.From, "invalid or incomplete media offer")
		s.log.Error("inbound call initialization failed", "call_id", callID,
			"peer", evt.From.String(), "error", err)
	}
}

func (s *Session) rejectOffer(ctx context.Context, node *waBinary.Node, from types.JID, reason string) {
	info := signaling.ExtractNodeInfo(node)
	if info == nil {
		return
	}
	creator := wanode.AttrString(info.InnerNode.Attrs, "call-creator")
	if creator == "" {
		creator = from.String()
	}
	reject := signaling.BuildRejectStanza(from, info.CallID, wanode.MustJID(creator))
	_ = wa.NewSocket(s.client).SendNode(ctx, reject)
	s.log.Info("inbound call rejected", "call_id", info.CallID, "reason", reason)
}

func (s *Session) handleEvent(rawEvt any) {
	ctx := context.Background()
	switch evt := rawEvt.(type) {
	case *events.Connected:
		if id := s.client.Store.ID; id != nil {
			_ = s.mgr.store.setJID(s.mgr.appCtx, s.id, id.String())
		}
		s.setAuth(AuthSnapshot{State: "open", Paired: true})
	case *events.LoggedOut:
		s.setAuth(AuthSnapshot{State: "logged_out", Paired: false})
	case *events.Message:
		// Leitor PASSIVO: o whatsmeow ja decifrou esta mensagem de qualquer
		// forma — ate aqui nos apenas a descartavamos. Nada e enviado ao
		// WhatsApp por causa desta linha. A normalizacao roda em worker proprio:
		// consulta HTTP de opt-in nunca pode atrasar um CallOffer.
		s.mgr.enfileirarCaptura(s, evt)
	case *events.CallOffer:
		s.onIncomingOffer(ctx, evt)
	case *events.CallAccept:
		if ac, ok := s.callForEvent(evt.From, evt.Data); ok {
			ac.cm.HandleCallAccept(ctx, wrapCall(evt.From, evt.Data), evt.From)
		}
	case *events.CallTransport:
		if ac, ok := s.callForEvent(evt.From, evt.Data); ok {
			ac.cm.HandleCallTransport(ctx, wrapCall(evt.From, evt.Data), evt.From)
		}
	case *events.CallTerminate:
		if ac, ok := s.callForEvent(evt.From, evt.Data); ok {
			ac.cm.HandleCallTerminate(wrapCall(evt.From, evt.Data))
		}
	case *events.CallReject:
		if ac, ok := s.callForEvent(evt.From, evt.Data); ok {
			ac.cm.HandleCallTerminate(wrapCall(evt.From, evt.Data))
		}
	}
}

func (s *Session) connect(ctx context.Context) error {
	if s.client.Store.ID != nil {
		return s.client.Connect()
	}
	return s.startPairing(ctx)
}

func (s *Session) startPairing(ctx context.Context) error {
	qrChan, err := s.client.GetQRChannel(ctx)
	if err != nil {
		return err
	}
	if err := s.client.Connect(); err != nil {
		return err
	}
	go func() {
		for evt := range qrChan {
			switch evt.Event {
			case "code":
				s.log.Info("pairing QR ready")
				s.setAuth(AuthSnapshot{State: "qr", QR: evt.Code})
				s.mgr.broker.emitSessionQR(s.id, evt.Code)
			case "success":
				if id := s.client.Store.ID; id != nil {
					_ = s.mgr.store.setJID(s.mgr.appCtx, s.id, id.String())
				}
				s.setAuth(AuthSnapshot{State: "open", Paired: true})
			case "timeout":
				s.setAuth(AuthSnapshot{State: "logged_out", Paired: false})
			}
		}
	}()
	return nil
}

func (s *Session) setAuth(a AuthSnapshot) {
	s.mu.Lock()
	s.auth = a
	s.mu.Unlock()
	s.mgr.broker.emitAuthState(s.id, a)
	s.mgr.broker.emitSessionList(s.mgr.infos())
}

func (s *Session) info() SessionInfo {
	s.mu.Lock()
	a := s.auth
	s.mu.Unlock()
	jid := ""
	if id := s.client.Store.ID; id != nil {
		jid = id.String()
	}
	qr := ""
	if a.State == "qr" {
		qr = a.QR
	}
	return SessionInfo{ID: s.id, Name: s.name, JID: jid, State: a.State, Paired: a.Paired || jid != "", QR: qr}
}

func (s *Session) setBridge(callID string, b PCMBridge) {
	oldB, found := s.reg.setBridge(callID, b)
	if !found {
		b.Close()
		return
	}
	if oldB != nil {
		oldB.Close()
	}
}

func (s *Session) removeCall(callID string) {
	ac, ok := s.reg.remove(callID)
	if !ok {
		return
	}
	if ac.bridge != nil {
		ac.bridge.Close()
	}
}

func (s *Session) terminateCall(callID string, reason core.EndCallReason) {
	ac, ok := s.reg.get(callID)
	if !ok {
		return
	}
	_ = ac.cm.EndCall(context.Background(), reason)
}

func (s *Session) teardownAllCalls() {
	for _, ac := range s.reg.drain() {
		_ = ac.cm.EndCall(context.Background(), core.EndCallReasonUserEnded)
		if ac.bridge != nil {
			ac.bridge.Close()
		}
	}
}

func (s *Session) replaceClient(client *whatsmeow.Client) {
	s.teardownAllCalls()
	s.client.Disconnect()
	s.client = client
	client.AddEventHandler(s.handleEvent)
}

func (s *Session) shutdown() {
	s.teardownAllCalls()
	s.client.Disconnect()
}

func mapStatus(state core.CallState) CallStatus {
	switch state {
	case core.CallStateActive:
		return StatusConnected
	case core.CallStateEnded:
		return StatusEnded
	case core.CallStateInitiating:
		return StatusStarting
	default:
		return StatusRinging
	}
}
