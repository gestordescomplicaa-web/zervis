// Zérvis (ADR 0108): o Zé responde nos grupos das empresas ligadas, quando é chamado.
//
// Duas travas aqui, além das do Zé: o envio a um grupo só passa se o grupo está na lista que o Zé
// grava (o arquivo de WACALLS_GRUPOS, só com os grupos das empresas ligadas), e a captura marca
// quando a mensagem do grupo chama o número conectado (menção ou resposta a uma mensagem dele).

package main

import (
	"encoding/json"
	"errors"
	"os"
	"strings"

	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
)

// grupoLigado diz se o grupo está na lista do Zé. Lida a cada envio (é pequena): desligar a empresa
// no painel vale na hora. Sem a lista, nenhum grupo.
func grupoLigado(jid string) bool {
	caminho := os.Getenv("WACALLS_GRUPOS")
	if caminho == "" {
		return false
	}
	bruto, err := os.ReadFile(caminho)
	if err != nil {
		return false
	}
	var lista struct {
		Grupos []string `json:"grupos"`
	}
	if json.Unmarshal(bruto, &lista) != nil {
		return false
	}
	for _, g := range lista.Grupos {
		if g == jid {
			return true
		}
	}
	return false
}

// destinoPermitido aceita a conversa com uma pessoa (como sempre) ou um grupo ligado.
func destinoPermitido(bruto string) (types.JID, error) {
	if jid, err := conversaPrivada(bruto); err == nil {
		return jid, nil
	}
	jid, err := types.ParseJID(strings.TrimSpace(bruto))
	if err != nil || jid.Server != types.GroupServer || jid.User == "" || !grupoLigado(jid.String()) {
		return types.EmptyJID, errors.New("invalid chat_jid")
	}
	return jid, nil
}

// contextoDaMensagem é o contexto do texto (menções e a mensagem citada), quando há.
func contextoDaMensagem(evt *events.Message) *waE2E.ContextInfo {
	if evt == nil || evt.Message == nil {
		return nil
	}
	if e := evt.Message.GetExtendedTextMessage(); e != nil {
		return e.GetContextInfo()
	}
	return nil
}

// chamaOZe: a mensagem menciona um dos números do Zé (o telefone ou o LID) ou responde a uma
// mensagem dele.
func chamaOZe(ctx *waE2E.ContextInfo, proprios ...types.JID) bool {
	if ctx == nil {
		return false
	}
	eu := map[string]bool{}
	for _, p := range proprios {
		if p.User != "" {
			eu[p.User] = true
		}
	}
	if len(eu) == 0 {
		return false
	}
	for _, m := range ctx.GetMentionedJID() {
		if j, err := types.ParseJID(m); err == nil && eu[j.User] {
			return true
		}
	}
	if p := ctx.GetParticipant(); p != "" {
		if j, err := types.ParseJID(p); err == nil && eu[j.User] {
			return true
		}
	}
	return false
}
