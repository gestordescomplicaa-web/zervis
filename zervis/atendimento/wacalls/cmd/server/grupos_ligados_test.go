package main

import (
	"os"
	"path/filepath"
	"testing"

	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/types"
)

func TestSoGruposDaListaRecebemEnvio(t *testing.T) {
	lista := filepath.Join(t.TempDir(), "grupos.json")
	ligado, outro := "120363000000000001@g.us", "120363000000000002@g.us"
	t.Setenv("WACALLS_GRUPOS", lista)
	if _, err := destinoPermitido(ligado); err == nil {
		t.Fatal("sem a lista, nenhum grupo")
	}
	if err := os.WriteFile(lista, []byte(`{"grupos": ["`+ligado+`"]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := destinoPermitido(ligado); err != nil {
		t.Fatalf("grupo ligado recusado: %v", err)
	}
	if _, err := destinoPermitido(outro); err == nil {
		t.Fatal("grupo fora da lista passou")
	}
	if _, err := destinoPermitido("5511999990000@s.whatsapp.net"); err != nil {
		t.Fatalf("conversa privada recusada: %v", err)
	}
	if _, err := destinoPermitido("status@broadcast"); err == nil {
		t.Fatal("status passou")
	}
}

func TestChamaOZePelaMencaoOuPelaResposta(t *testing.T) {
	ze := types.NewJID("5511988887777", types.DefaultUserServer)
	lid := types.NewJID("123456789", types.HiddenUserServer)
	texto := func(c *waE2E.ContextInfo) *waE2E.ContextInfo { return c }
	mencao := "5511988887777@s.whatsapp.net"
	pelaLID := "123456789@lid"
	outro := "5511911112222@s.whatsapp.net"
	if !chamaOZe(texto(&waE2E.ContextInfo{MentionedJID: []string{outro, mencao}}), ze, lid) {
		t.Fatal("menção ao número não chamou")
	}
	if !chamaOZe(texto(&waE2E.ContextInfo{Participant: &pelaLID}), ze, lid) {
		t.Fatal("resposta à mensagem do Zé (pelo LID) não chamou")
	}
	if chamaOZe(texto(&waE2E.ContextInfo{MentionedJID: []string{outro}, Participant: &outro}), ze, lid) {
		t.Fatal("menção a outra pessoa chamou")
	}
	if chamaOZe(nil, ze) || chamaOZe(&waE2E.ContextInfo{MentionedJID: []string{mencao}}) {
		t.Fatal("sem contexto ou sem o número do Zé, não chama")
	}
}
