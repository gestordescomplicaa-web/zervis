package main

// ENVIO TRANSACIONAL DE TEXTO.
//
// Este endpoint não transforma o leitor passivo do WhatsApp em chatbot. Ele
// aceita somente categorias internas fechadas (Agenda e demonstracao), uma
// mensagem curta ja produzida pelo dominio de origem e uma chave idempotente.
// O Dashboard resolve tenant -> sessao; o WaCalls nao recebe nem confia em tenant.

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"time"

	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/types"
	"google.golang.org/protobuf/proto"
)

const (
	agendaMessageKind = "agenda_transactional"
	demoMessageKind   = "demo_transactional"
	// Zérvis: a resposta do agente de atendimento, só a quem escreveu antes (ADR 0031).
	atendimentoMessageKind   = "atendimento_reply"
	agendaMessageMaxBytes    = 16 << 10
	agendaMessageMaxText     = 1200
	agendaMessageMaxPhones   = 4
	agendaMessageSendTimeout = 20 * time.Second
)

var agendaIdempotencyPattern = regexp.MustCompile(`^[A-Za-z0-9:_-]{8,180}$`)

type agendaMessageRequest struct {
	Kind           string   `json:"kind"`
	Phones         []string `json:"phones"`
	Text           string   `json:"text"`
	IdempotencyKey string   `json:"idempotency_key"`
}

type agendaMessageReceipt struct {
	MessageID   string
	Target      string
	PayloadHash string
}

func criarRecibosAgenda(ctx context.Context, db *sql.DB) error {
	_, err := db.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS agenda_message_receipts (
		session_id      TEXT NOT NULL,
		idempotency_key TEXT NOT NULL,
		message_id      TEXT NOT NULL,
		target          TEXT NOT NULL,
		payload_sha256  TEXT NOT NULL,
		sent_at         INTEGER NOT NULL,
		PRIMARY KEY (session_id, idempotency_key)
	)`)
	return err
}

func validarAgendaMessageRequest(body agendaMessageRequest) (agendaMessageRequest, error) {
	body.Kind = strings.TrimSpace(body.Kind)
	body.Text = strings.TrimSpace(body.Text)
	body.IdempotencyKey = strings.TrimSpace(body.IdempotencyKey)
	if body.Kind != agendaMessageKind && body.Kind != demoMessageKind &&
		body.Kind != atendimentoMessageKind {
		return body, fmt.Errorf("unsupported message kind")
	}
	if body.Text == "" || len([]rune(body.Text)) > agendaMessageMaxText {
		return body, fmt.Errorf("text must contain 1 to %d characters", agendaMessageMaxText)
	}
	if !agendaIdempotencyPattern.MatchString(body.IdempotencyKey) {
		return body, errors.New("invalid idempotency_key")
	}
	if len(body.Phones) == 0 || len(body.Phones) > agendaMessageMaxPhones {
		return body, fmt.Errorf("phones must contain 1 to %d candidates", agendaMessageMaxPhones)
	}
	phones := make([]string, 0, len(body.Phones))
	seen := make(map[string]struct{}, len(body.Phones))
	for _, raw := range body.Phones {
		phone := normalizePhone(raw)
		if len(phone) < 8 || len(phone) > 20 {
			return body, errors.New("invalid phone candidate")
		}
		if _, ok := seen[phone]; ok {
			continue
		}
		seen[phone] = struct{}{}
		phones = append(phones, phone)
	}
	if len(phones) == 0 {
		return body, errors.New("phones required")
	}
	body.Phones = phones
	return body, nil
}

func agendaPayloadHash(body agendaMessageRequest) string {
	// A ordem das variantes não altera a intenção. Ordená-las impede que um
	// retry equivalente seja recusado apenas porque o chamador reordenou a lista.
	phones := append([]string(nil), body.Phones...)
	sort.Strings(phones)
	sum := sha256.Sum256([]byte(strings.Join(phones, ",") + "\x00" + body.Text))
	return hex.EncodeToString(sum[:])
}

func agendaDeterministicMessageID(sessionID, key string) types.MessageID {
	sum := sha256.Sum256([]byte("ligatia/agenda-message/v1:" + sessionID + ":" + key))
	// Mesmo formato usado pelo cliente web do whatsmeow. Repetir uma tentativa
	// após ACK sem recibo local reutiliza o ID e evita duas confirmações.
	return types.MessageID(whatsmeow.WebMessageIDPrefix + strings.ToUpper(hex.EncodeToString(sum[:9])))
}

func lerReciboAgenda(ctx context.Context, db *sql.DB, sessionID, key string) (*agendaMessageReceipt, error) {
	var out agendaMessageReceipt
	err := db.QueryRowContext(ctx,
		`SELECT message_id, target, payload_sha256
		   FROM agenda_message_receipts
		  WHERE session_id = ? AND idempotency_key = ?`,
		sessionID, key).Scan(&out.MessageID, &out.Target, &out.PayloadHash)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &out, nil
}

func gravarReciboAgenda(ctx context.Context, db *sql.DB, sessionID, key string,
	messageID types.MessageID, target, payloadHash string) error {
	_, err := db.ExecContext(ctx,
		`INSERT INTO agenda_message_receipts
		       (session_id, idempotency_key, message_id, target, payload_sha256, sent_at)
		 VALUES (?, ?, ?, ?, ?, ?)
		 ON CONFLICT(session_id, idempotency_key) DO NOTHING`,
		sessionID, key, string(messageID), target, payloadHash, time.Now().Unix())
	return err
}

func (s *server) handleAgendaMessage(w http.ResponseWriter, r *http.Request) {
	sess := s.sessionByID(w, r.PathValue("sid"))
	if sess == nil {
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, agendaMessageMaxBytes)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	var raw agendaMessageRequest
	if err := decoder.Decode(&raw); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON body"})
		return
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "single JSON object required"})
		return
	}
	body, err := validarAgendaMessageRequest(raw)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	// A trava é por sessão e só cobre mensagens transacionais curtas. Não usa
	// o mutex de autenticação e não interfere em offer/accept/transport da voz.
	sess.agendaMessageMu.Lock()
	defer sess.agendaMessageMu.Unlock()

	payloadHash := agendaPayloadHash(body)
	receipt, err := lerReciboAgenda(r.Context(), s.db, sess.id, body.IdempotencyKey)
	if err != nil {
		s.log.Error("agenda message receipt lookup failed", "session", sess.id, "error", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "receipt lookup failed"})
		return
	}
	if receipt != nil {
		if receipt.PayloadHash != payloadHash {
			writeJSON(w, http.StatusConflict, map[string]string{"error": "idempotency key reused with different payload"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{
			"acknowledged": true,
			"duplicate":    true,
			"message_id":   receipt.MessageID,
			"phone":        receipt.Target,
		})
		return
	}

	if sess.client == nil || sess.client.Store.ID == nil ||
		!sess.client.IsConnected() || !sess.client.IsLoggedIn() {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "session not connected"})
		return
	}

	lookupCtx, lookupCancel := context.WithTimeout(r.Context(), 10*time.Second)
	registered, err := sess.resolvePhoneCandidates(lookupCtx, body.Phones)
	lookupCancel()
	if err != nil {
		s.log.Warn("agenda recipient lookup failed", "session", sess.id, "error", err)
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "recipient lookup failed"})
		return
	}
	if len(registered) == 0 {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "recipient is not registered on WhatsApp"})
		return
	}
	if len(registered) > 1 {
		writeJSON(w, http.StatusConflict, map[string]string{"error": "ambiguous WhatsApp recipient"})
		return
	}

	phone := registered[0]
	target := types.NewJID(phone, types.DefaultUserServer)
	messageID := agendaDeterministicMessageID(sess.id, body.IdempotencyKey)
	sendCtx, sendCancel := context.WithTimeout(r.Context(), agendaMessageSendTimeout)
	response, err := sess.client.SendMessage(
		sendCtx,
		target,
		&waE2E.Message{Conversation: proto.String(body.Text)},
		whatsmeow.SendRequestExtra{ID: messageID, Timeout: 15 * time.Second},
	)
	sendCancel()
	if err != nil {
		s.log.Warn("agenda message not acknowledged", "session", sess.id,
			"message_id", messageID, "error", err)
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "message was not acknowledged"})
		return
	}
	if response.ID != "" {
		messageID = response.ID
	}
	if err := gravarReciboAgenda(r.Context(), s.db, sess.id, body.IdempotencyKey,
		messageID, phone, payloadHash); err != nil {
		// O servidor já confirmou a mensagem. Devolver falha fará o painel tentar
		// novamente com o mesmo ID determinístico, que é a opção segura.
		s.log.Error("agenda message acknowledged without local receipt", "session", sess.id,
			"message_id", messageID, "error", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "message acknowledged but receipt failed"})
		return
	}
	s.log.Info("agenda message acknowledged", "session", sess.id, "message_id", messageID)
	writeJSON(w, http.StatusOK, map[string]any{
		"acknowledged": true,
		"duplicate":    false,
		"message_id":   messageID,
		"phone":        phone,
	})
}
