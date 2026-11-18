package main

// ÁUDIO SOB PEDIDO (Zérvis, ADR 0103).
//
// A captura continua sem mídia (decisão de 13/08/2026): do áudio que chega numa
// conversa privada guardamos só a referência que o próprio WhatsApp manda (o
// caminho e a chave do arquivo), em memória e por poucos minutos. O arquivo só
// é baixado quando o Zé pede, e ele só pede o áudio do número autorizado a
// conversar com ele. O resto expira sem nunca ter sido baixado.

import (
	"context"
	"net/http"
	"sync"
	"time"

	"go.mau.fi/whatsmeow/proto/waE2E"
)

const (
	audioValidade     = 10 * time.Minute
	audioGuardadosMax = 200
	audioSegundosMax  = 600     // dez minutos de fala
	audioBytesMax     = 8 << 20 // um áudio de voz de dez minutos tem perto de 1 MB
)

type audioGuardado struct {
	msg *waE2E.AudioMessage
	em  time.Time
}

type audiosRecentes struct {
	mu    sync.Mutex
	itens map[string]audioGuardado
	ordem []string
}

func novosAudios() *audiosRecentes {
	return &audiosRecentes{itens: map[string]audioGuardado{}}
}

func (a *audiosRecentes) guardar(id string, msg *waE2E.AudioMessage, agora time.Time) {
	if msg == nil || id == "" {
		return
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	if _, ja := a.itens[id]; !ja {
		a.ordem = append(a.ordem, id)
	}
	a.itens[id] = audioGuardado{msg: msg, em: agora}
	for len(a.ordem) > audioGuardadosMax {
		delete(a.itens, a.ordem[0])
		a.ordem = a.ordem[1:]
	}
}

// pegar devolve a referência ainda válida; um pedido só vale uma vez.
func (a *audiosRecentes) pegar(id string, agora time.Time) (*waE2E.AudioMessage, bool) {
	a.mu.Lock()
	defer a.mu.Unlock()
	g, ok := a.itens[id]
	if !ok {
		return nil, false
	}
	delete(a.itens, id)
	if agora.Sub(g.em) > audioValidade {
		return nil, false
	}
	return g.msg, true
}

// handleAudio entrega o arquivo de um áudio recente, pelo id do evento que a
// captura mandou ao Zé (`<sessão>:<mensagem>`).
func (s *server) handleAudio(w http.ResponseWriter, r *http.Request) {
	sess := s.sessionByID(w, r.PathValue("sid"))
	if sess == nil {
		return
	}
	msg, ok := s.sessions.audios.pegar(r.URL.Query().Get("evento"), time.Now())
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "audio not available"})
		return
	}
	if msg.GetSeconds() > audioSegundosMax || msg.GetFileLength() > audioBytesMax {
		writeJSON(w, http.StatusRequestEntityTooLarge, map[string]string{"error": "audio too long"})
		return
	}
	if sess.client == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "session not connected"})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	dados, err := sess.client.Download(ctx, msg)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "download failed"})
		return
	}
	if len(dados) > audioBytesMax {
		writeJSON(w, http.StatusRequestEntityTooLarge, map[string]string{"error": "audio too long"})
		return
	}
	tipo := msg.GetMimetype()
	if tipo == "" {
		tipo = "audio/ogg"
	}
	w.Header().Set("Content-Type", tipo)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(dados)
}
