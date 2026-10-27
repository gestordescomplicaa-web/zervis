package main

// CAPTURA PASSIVA DE MENSAGENS.
//
// O objetivo é um só: o que a empresa conversa por texto no WhatsApp vira
// contexto para o agente de voz. Quem liga depois é atendido por quem já sabe
// do que se tratava.
//
// PASSIVA quer dizer que nada de novo acontece no WhatsApp. Só lemos o que a
// sessão pareada JÁ recebeu e o whatsmeow JÁ decifrou — o evento é emitido de
// qualquer forma; até aqui nós apenas o descartávamos. Nesta captura o agente
// não responde, não marca como lido, não mexe em presença, não pede histórico e
// não baixa mídia. Pedir sincronização de histórico, em particular, é dos
// caminhos mais associados a bloqueio — e está fora de propósito.
//
// SEM MÍDIA (decisão de 13/08/2026): só texto puro. Guardamos que existiu um
// áudio ou uma imagem, nunca o arquivo.

import (
	"context"
	"encoding/json"
	"strings"
	"time"

	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
)

// Teto de tamanho do texto guardado. Uma mensagem gigante colada não pode virar
// linha de banco sem limite nem estourar o prompt do agente lá na frente.
const textoMaxChars = 4000

// A fila absorve rajadas sem deixar mensagem de texto competir com a
// sinalizacao de voz. O envio ao painel ja possui uma segunda fila duravel
// (SQLite); esta e apenas a fronteira nao bloqueante do callback do whatsmeow.
const capturaFilaMax = 1024

type mensagemParaCaptura struct {
	sessao *Session
	evento *events.Message
}

func (m *SessionManager) enfileirarCaptura(s *Session, evt *events.Message) {
	select {
	case m.msgQueue <- mensagemParaCaptura{sessao: s, evento: evt}:
	default:
		// A telefonia e' o produto principal. Sob uma rajada maior que o limite,
		// descartamos contexto acessorio de forma VISIVEL em vez de bloquear
		// offers/transports e derrubar uma ligacao.
		s.log.Warn("fila de captura cheia; mensagem descartada", "capacidade", capturaFilaMax)
	}
}

func (m *SessionManager) rodarCapturaMensagens() {
	for {
		select {
		case <-m.appCtx.Done():
			return
		case item := <-m.msgQueue:
			item.sessao.handleMessage(item.evento)
		}
	}
}

// IDs do WhatsApp sao unicos dentro da sessao, nao constituem contrato global
// entre numeros pareados. Escopar evita que duas empresas com o mesmo id de
// evento se dedupliquem uma contra a outra no SQLite ou no Postgres.
func idEventoEscopado(sessionID, eventID string) string {
	return sessionID + ":" + eventID
}

// mensagemNormalizada é o contrato com o painel. Nomes em inglês por serem
// chave de JSON entre serviços; o resto do código segue em português.
type mensagemNormalizada struct {
	EventID    string `json:"event_id"`
	SessionID  string `json:"session_id"`
	Direction  string `json:"direction"` // inbound | outbound
	ChatJID    string `json:"chat_jid"`
	SenderJID  string `json:"sender_jid"`
	Phone      string `json:"phone"`     // forma discável, quando dá pra resolver
	LID        string `json:"lid"`       // forma oculta, quando existe
	PushName   string `json:"push_name"` // como a pessoa se identifica no WhatsApp
	Type       string `json:"type"`      // text | media
	Content    string `json:"content"`
	OccurredAt string `json:"occurred_at"`
}

// textoDaMensagem extrai o texto puro. Devolve ("", false) para o que não é
// texto — mídia, reação, enquete, revogação. O tipo do que veio é registrado
// pelo chamador; o conteúdo, não.
func textoDaMensagem(evt *events.Message) (string, bool) {
	if evt.Message == nil {
		return "", false
	}
	// Conversation = texto simples. ExtendedTextMessage = texto com contexto
	// (resposta a outra mensagem, link com prévia) — o corpo continua sendo
	// texto e interessa igual.
	if t := strings.TrimSpace(evt.Message.GetConversation()); t != "" {
		return t, true
	}
	if e := evt.Message.GetExtendedTextMessage(); e != nil {
		if t := strings.TrimSpace(e.GetText()); t != "" {
			return t, true
		}
	}
	return "", false
}

// identidades separa as duas formas do MESMO contato. O evento já traz o par:
// `SenderAlt`/`RecipientAlt` é a forma alternativa da que veio em `Sender`.
// Aproveitar isso evita uma consulta ao mapa de LIDs — que pode falhar e cuja
// ausência já nos custou uma ligação muda de 15s no passado.
func identidades(evt *events.Message) (telefone string, lid string) {
	principal := evt.Info.Sender
	alternativa := evt.Info.SenderAlt
	// Numa mensagem que EU enviei, quem identifica o contato é o outro lado.
	if evt.Info.IsFromMe {
		principal = evt.Info.Chat
		alternativa = evt.Info.RecipientAlt
	}
	for _, j := range []types.JID{principal, alternativa} {
		if j.IsEmpty() {
			continue
		}
		switch j.Server {
		case types.DefaultUserServer:
			if telefone == "" {
				telefone = j.User
			}
		case types.HiddenUserServer:
			if lid == "" {
				lid = j.User
			}
		}
	}
	return telefone, lid
}

// deveCapturar decide se este evento vira histórico.
//
// GRUPO FICA DE FORA (decisão de 13/08/2026): a memória do agente é por
// CONTATO, e mensagem de grupo é de muita gente ao mesmo tempo. Misturar as
// duas faria o agente atribuir a uma pessoa o que outra escreveu — pior do que
// não ter o histórico.
func deveCapturar(evt *events.Message) (string, bool) {
	if evt.Info.IsGroup {
		return "", false
	}
	// Newsletter/canal é difusão, não conversa.
	if evt.Info.Chat.Server == types.NewsletterServer {
		return "", false
	}
	// Status ("recado") não é dirigido a ninguém.
	if evt.Info.Chat.Server == types.BroadcastServer {
		return "", false
	}
	// Zérvis: só conversa privada passa (lista do que é permitido, não do que é proibido):
	// um tipo novo de conversa do WhatsApp fica de fora até alguém decidir o contrário.
	if evt.Info.Chat.Server != types.DefaultUserServer && evt.Info.Chat.Server != types.HiddenUserServer {
		return "", false
	}
	if evt.Info.ID == "" {
		return "", false
	}
	return evt.Info.ID, true
}

// handleMessage normaliza e enfileira. NUNCA devolve erro para o whatsmeow: é
// um leitor passivo pendurado no fluxo da sessão, e nada aqui pode atrapalhar
// uma ligação em curso ou a conexão do WhatsApp.
func (s *Session) handleMessage(evt *events.Message) {
	defer func() {
		// A captura é acessório. Se ela estourar, a sessão — e as chamadas que
		// dependem dela — seguem como se a captura não existisse.
		if r := recover(); r != nil {
			s.log.Error("captura de mensagem entrou em panico", "erro", r)
		}
	}()

	eventID, ok := deveCapturar(evt)
	if !ok {
		s.log.Debug("mensagem ignorada pelo filtro",
			"grupo", evt.Info.IsGroup, "chat", evt.Info.Chat.Server)
		return
	}
	if !s.mgr.capturaLigada(s.id) {
		// Registra que HOUVE mensagem, mesmo sem capturar. Sem isto não há como
		// distinguir "o evento não chega" de "chega e o opt-in barra" — e foi
		// exatamente essa dúvida que travou o primeiro teste em 14/08/2026.
		// Estrangulado para não virar enxurrada num WhatsApp movimentado.
		s.avisarCapturaDesligada()
		return
	}
	eventID = idEventoEscopado(s.id, eventID)

	texto, ehTexto := textoDaMensagem(evt)
	tipo := "text"
	if !ehTexto {
		// Registra que houve algo, sem o conteúdo. Serve para a conversa não
		// aparecer com buracos inexplicáveis ("ela mandou um áudio aqui").
		tipo = "media"
		texto = ""
	}
	if len(texto) > textoMaxChars {
		texto = texto[:textoMaxChars]
	}

	telefone, lid := identidades(evt)
	direcao := "inbound"
	if evt.Info.IsFromMe {
		direcao = "outbound"
	}

	m := mensagemNormalizada{
		EventID:    eventID,
		SessionID:  s.id,
		Direction:  direcao,
		ChatJID:    evt.Info.Chat.String(),
		SenderJID:  evt.Info.Sender.String(),
		Phone:      telefone,
		LID:        lid,
		PushName:   evt.Info.PushName,
		Type:       tipo,
		Content:    texto,
		OccurredAt: evt.Info.Timestamp.UTC().Format(time.RFC3339),
	}
	payload, err := json.Marshal(m)
	if err != nil {
		s.log.Error("mensagem nao normalizou", "erro", err)
		return
	}

	ctx, cancel := context.WithTimeout(s.mgr.appCtx, 5*time.Second)
	defer cancel()
	if err := enfileirar(ctx, s.mgr.db, eventID, s.id, string(payload)); err != nil {
		s.log.Error("mensagem nao entrou na outbox", "erro", err)
		return
	}
	// Info, nao Debug: o volume aqui e o de mensagens reais, e e o unico sinal
	// de que a captura esta viva. Sem numero de telefone no log — ele nao
	// acrescenta nada ao diagnostico e o log e lido por mais gente que o banco.
	s.log.Info("mensagem capturada", "direcao", direcao, "tipo", tipo)
}

// avisarCapturaDesligada diz, no maximo uma vez por minuto, que mensagens estao
// chegando e sendo descartadas por falta de autorizacao. E a diferenca entre
// "nao chega evento nenhum" e "chega e o opt-in barra" — sem isso, as duas
// situacoes sao o mesmo silencio.
func (s *Session) avisarCapturaDesligada() {
	s.msgMu.Lock()
	defer s.msgMu.Unlock()
	if time.Since(s.msgAvisoEm) < time.Minute {
		return
	}
	s.msgAvisoEm = time.Now()
	s.log.Info("mensagem recebida, mas o compartilhamento com o agente esta desligado")
}
