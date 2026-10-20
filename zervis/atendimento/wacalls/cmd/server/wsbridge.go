package main

import (
	"context"
	"log/slog"
	"net/http"

	"wacalls/internal/voip/core"
	"wacalls/internal/voip/media"

	"github.com/coder/websocket"
)

// WSBridge: transporte de áudio por WebSocket, no lugar do navegador. Carrega PCM 16kHz
// mono Int16LE entre o WaCalls e o BRIDGE DO AGENTE (Python). Mesmo contrato do Bridge
// WebRTC: WritePCM = downlink (cliente -> agente/STT); OnAgentPCM = uplink (TTS -> cliente).
type WSBridge struct {
	conn *websocket.Conn
	log  *slog.Logger
	done chan struct{}

	OnAgentPCM func(pcm []float32) // PCM do agente -> alimenta o uplink da chamada
	OnClose    func()              // WS caiu -> encerrar a chamada
}

func newWSBridge(conn *websocket.Conn, log *slog.Logger) *WSBridge {
	b := &WSBridge{conn: conn, log: log, done: make(chan struct{})}
	go b.readLoop()
	return b
}

// WritePCM envia o PCM do cliente (16kHz float32) ao agente como Int16LE. No-op se vazio.
func (b *WSBridge) WritePCM(pcm []float32) error {
	if len(pcm) == 0 {
		return nil
	}
	return b.conn.Write(context.Background(), websocket.MessageBinary, media.PCMFloat32ToInt16LE(pcm))
}

func (b *WSBridge) readLoop() {
	defer close(b.done)
	for {
		typ, data, err := b.conn.Read(context.Background())
		if err != nil {
			break
		}
		if typ == websocket.MessageBinary && len(data) > 0 && b.OnAgentPCM != nil {
			b.OnAgentPCM(media.PCMInt16LEToFloat32(data))
		}
	}
	if b.OnClose != nil {
		b.OnClose()
	}
}

func (b *WSBridge) Close() {
	_ = b.conn.Close(websocket.StatusNormalClosure, "")
}

func (b *WSBridge) wait() { <-b.done }

// handlePCM: WebSocket que liga o áudio de UMA chamada ao bridge do agente (Python).
// GET /api/sessions/{sid}/calls/{id}/pcm  — mídia binária: PCM 16kHz mono Int16LE.
// InsecureSkipVerify: serviço é só interno (rede do Docker), sem origin de navegador.
func (s *server) handlePCM(w http.ResponseWriter, r *http.Request) {
	sess := s.sessionByID(w, r.PathValue("sid"))
	if sess == nil {
		return
	}
	callID := r.PathValue("id")
	ac, ok := sess.reg.get(callID)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "no such call"})
		return
	}
	conn, err := websocket.Accept(w, r, &websocket.AcceptOptions{InsecureSkipVerify: true})
	if err != nil {
		return
	}
	bridge := newWSBridge(conn, s.log)
	bridge.OnAgentPCM = func(pcm []float32) { ac.cm.FeedCapturedPCM(pcm) }
	bridge.OnClose = func() { go sess.terminateCall(callID, core.EndCallReasonUserEnded) }
	sess.setBridge(callID, bridge)
	s.log.Info("pcm bridge (agent) attached", "session", sess.id, "call_id", callID)
	bridge.wait() // segura o handler enquanto a chamada/áudio vive
}
