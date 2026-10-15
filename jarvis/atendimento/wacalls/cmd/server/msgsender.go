package main

// ENTREGA DA OUTBOX AO PAINEL.
//
// Roda numa goroutine própria e é a única parte que fala com o mundo externo.
// Duas invariantes governam o desenho:
//
//  1. NUNCA segurar a conexão do SQLite durante o HTTP. O banco tem UMA conexão
//     (SetMaxOpenConns(1)) e é a mesma que o whatsmeow usa para gravar chaves de
//     criptografia. Prender ali durante uma chamada de rede travaria a sessão de
//     WhatsApp inteira. Por isso o ciclo é: lê e solta -> envia -> confirma.
//     (O mesmo erro, com o pool do agente, deixou uma ligação muda em 13/08.)
//
//  2. Só apaga com confirmação. Falhou, fica na fila e tenta de novo.

import (
	"bytes"
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	envioIntervalo = 5 * time.Second
	envioTimeout   = 15 * time.Second
	// A resposta do opt-in vale por pouco tempo: quem desliga o compartilhamento
	// no painel espera que pare de valer logo, e a consulta é barata.
	optinTTL = 60 * time.Second
)

func dashboardURL() string {
	u := strings.TrimRight(os.Getenv("DASHBOARD_URL"), "/")
	if u == "" {
		u = "http://dashboard:8080"
	}
	return u
}

// tokenInterno reproduz a derivação que a ponte e o agente já usam. Mesma
// semente, mesmo rótulo — se divergir, o painel recusa com 401 e a fila para.
func tokenInterno() string {
	semente := strings.TrimSpace(os.Getenv("INTERNAL_TOKEN"))
	if semente == "" {
		semente = strings.TrimSpace(os.Getenv("LIVEKIT_API_SECRET"))
	}
	if semente == "" {
		return ""
	}
	h := sha256.Sum256([]byte("agente-voz/interno/v1:" + semente))
	return hex.EncodeToString(h[:])
}

// capturaCache guarda a resposta do painel sobre "esta sessão captura?".
type capturaCache struct {
	mu   sync.RWMutex
	ate  map[string]time.Time
	vale map[string]bool
}

func novaCapturaCache() *capturaCache {
	return &capturaCache{ate: map[string]time.Time{}, vale: map[string]bool{}}
}

func (c *capturaCache) ler(sessionID string) (bool, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if t, ok := c.ate[sessionID]; ok && time.Now().Before(t) {
		return c.vale[sessionID], true
	}
	return false, false
}

func (c *capturaCache) gravar(sessionID string, v bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.vale[sessionID] = v
	c.ate[sessionID] = time.Now().Add(optinTTL)
}

// capturaLigada pergunta ao painel se a central desta sessão autorizou o
// compartilhamento do histórico.
//
// NA DÚVIDA, NÃO CAPTURA. Painel fora do ar, token errado, rota ausente: a
// resposta é não. Guardar conversa de terceiros sem confirmar a autorização é
// o erro que não se desfaz — apagar depois não desfaz ter armazenado.
func (m *SessionManager) capturaLigada(sessionID string) bool {
	if v, ok := m.captura.ler(sessionID); ok {
		return v
	}
	ctx, cancel := context.WithTimeout(m.appCtx, 5*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/api/interno/whatsapp/captura/%s", dashboardURL(), sessionID), nil)
	if err != nil {
		return false
	}
	req.Header.Set("X-Internal-Token", tokenInterno())
	resp, err := (&http.Client{Timeout: 5 * time.Second}).Do(req)
	if err != nil {
		m.log.Debug("optin de captura nao consultado", "erro", err)
		return false
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return false
	}
	var r struct {
		Capturar bool `json:"capturar"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&r); err != nil {
		return false
	}
	m.captura.gravar(sessionID, r.Capturar)
	return r.Capturar
}

// enviarLote entrega e devolve os ids aceitos.
func enviarLote(ctx context.Context, itens []outboxItem) ([]string, error) {
	corpo := make([]json.RawMessage, 0, len(itens))
	ids := make([]string, 0, len(itens))
	for _, it := range itens {
		corpo = append(corpo, json.RawMessage(it.Payload))
		ids = append(ids, it.EventID)
	}
	b, err := json.Marshal(map[string]any{"mensagens": corpo})
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		dashboardURL()+"/api/interno/whatsapp/mensagens", bytes.NewReader(b))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Internal-Token", tokenInterno())
	resp, err := (&http.Client{Timeout: envioTimeout}).Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("painel respondeu %d", resp.StatusCode)
	}
	// O painel grava o lote inteiro ou nada (uma transação), então 2xx confirma
	// todos. Confirmar item a item exigiria que ele devolvesse a lista, o que
	// só vale a pena quando houver motivo para recusa parcial.
	return ids, nil
}

// rodarEnvioOutbox mantém a fila andando até o processo encerrar.
func rodarEnvioOutbox(ctx context.Context, db *sql.DB, log *slog.Logger) {
	tick := time.NewTicker(envioIntervalo)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
		}
		if n := expurgar(ctx, db); n > 0 {
			// Não é rotina: é mensagem de cliente que se perdeu.
			log.Warn("mensagens descartadas da outbox por validade", "quantidade", n)
		}
		itens, err := pendentes(ctx, db)
		if err != nil || len(itens) == 0 {
			continue
		}
		ids, err := enviarLote(ctx, itens)
		if err != nil {
			marcarTentativa(ctx, db, idsDe(itens))
			log.Debug("outbox nao entregue; tentara de novo", "erro", err, "itens", len(itens))
			continue
		}
		if err := confirmar(ctx, db, ids); err != nil {
			// Entregou mas não conseguiu apagar: o painel deduplica por
			// event_id, então o reenvio é inofensivo.
			log.Warn("outbox entregue mas nao confirmada localmente", "erro", err)
		}
	}
}

func idsDe(itens []outboxItem) []string {
	out := make([]string, 0, len(itens))
	for _, it := range itens {
		out = append(out, it.EventID)
	}
	return out
}
