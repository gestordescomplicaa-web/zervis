package main

import (
	"context"
	"path/filepath"
	"testing"
)

func TestAgendaMessageRequestIsClosedAndNormalized(t *testing.T) {
	body, err := validarAgendaMessageRequest(agendaMessageRequest{
		Kind:           agendaMessageKind,
		Phones:         []string{"+55 (81) 99999-0000", "5581999990000"},
		Text:           "  Consulta confirmada.  ",
		IdempotencyKey: "agenda:clinica:123",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(body.Phones) != 1 || body.Phones[0] != "5581999990000" {
		t.Fatalf("unexpected phones: %#v", body.Phones)
	}
	if body.Text != "Consulta confirmada." {
		t.Fatalf("unexpected text: %q", body.Text)
	}

	for _, invalid := range []agendaMessageRequest{
		{Kind: "free_text", Phones: []string{"5581999990000"}, Text: "oi", IdempotencyKey: "agenda:1"},
		{Kind: agendaMessageKind, Phones: nil, Text: "oi", IdempotencyKey: "agenda:1"},
		{Kind: agendaMessageKind, Phones: []string{"5581999990000"}, Text: "", IdempotencyKey: "agenda:1"},
		{Kind: agendaMessageKind, Phones: []string{"5581999990000"}, Text: "oi", IdempotencyKey: "chave com espaço"},
	} {
		if _, err := validarAgendaMessageRequest(invalid); err == nil {
			t.Fatalf("invalid request accepted: %#v", invalid)
		}
	}
}

func TestDemoMessageKindIsExplicitlyAllowed(t *testing.T) {
	body, err := validarAgendaMessageRequest(agendaMessageRequest{
		Kind:           demoMessageKind,
		Phones:         []string{"5581999990000"},
		Text:           "A demonstracao vai comecar.",
		IdempotencyKey: "demo:pedido:123:ack",
	})
	if err != nil {
		t.Fatal(err)
	}
	if body.Kind != demoMessageKind {
		t.Fatalf("unexpected kind: %q", body.Kind)
	}
}

func TestAgendaMessageIDIsStablePerSessionAndKey(t *testing.T) {
	a := agendaDeterministicMessageID("sessao-a", "agenda:clinica:123")
	b := agendaDeterministicMessageID("sessao-a", "agenda:clinica:123")
	c := agendaDeterministicMessageID("sessao-b", "agenda:clinica:123")
	if a != b || a == c {
		t.Fatalf("unexpected deterministic ids: %q %q %q", a, b, c)
	}
	if len(a) != 22 || string(a[:4]) != "3EB0" {
		t.Fatalf("unexpected WhatsApp id format: %q", a)
	}
}

func TestAgendaReceiptIsDurableAndPayloadBound(t *testing.T) {
	db, err := openDB(filepath.Join(t.TempDir(), "agenda.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	ctx := context.Background()
	if err := criarRecibosAgenda(ctx, db); err != nil {
		t.Fatal(err)
	}
	body, err := validarAgendaMessageRequest(agendaMessageRequest{
		Kind: agendaMessageKind, Phones: []string{"5581999990000"}, Text: "Confirmado.",
		IdempotencyKey: "agenda:clinica:456",
	})
	if err != nil {
		t.Fatal(err)
	}
	hash := agendaPayloadHash(body)
	id := agendaDeterministicMessageID("sessao", body.IdempotencyKey)
	if err := gravarReciboAgenda(ctx, db, "sessao", body.IdempotencyKey, id,
		"5581999990000", hash); err != nil {
		t.Fatal(err)
	}
	got, err := lerReciboAgenda(ctx, db, "sessao", body.IdempotencyKey)
	if err != nil {
		t.Fatal(err)
	}
	if got == nil || got.MessageID != string(id) || got.PayloadHash != hash {
		t.Fatalf("unexpected receipt: %#v", got)
	}
}

func TestAgendaMessageAceitaRespostaDoAtendimento(t *testing.T) {
	body, err := validarAgendaMessageRequest(agendaMessageRequest{
		Kind: atendimentoMessageKind, Phones: []string{"5581999990000"}, Text: "Oi! Como posso ajudar?",
		IdempotencyKey: "atendimento:abc12345",
	})
	if err != nil || body.Kind != atendimentoMessageKind {
		t.Fatalf("resposta do atendimento recusada: %v", err)
	}
}

// Zérvis: responder na conversa exata (telefone ou LID), nunca em grupo.
func TestAgendaMessageNaConversa(t *testing.T) {
	base := agendaMessageRequest{Kind: atendimentoMessageKind, Text: "oi", IdempotencyKey: "zervis:12345678"}
	for _, chat := range []string{"134230663237656@lid", "558193563525@s.whatsapp.net"} {
		pedido := base
		pedido.ChatJID = chat
		if _, err := validarAgendaMessageRequest(pedido); err != nil {
			t.Fatalf("%s: %v", chat, err)
		}
	}
	for _, chat := range []string{"120363000000000000@g.us", "status@broadcast", "123@newsletter", "558193563525:3@s.whatsapp.net", "lixo"} {
		pedido := base
		pedido.ChatJID = chat
		if _, err := validarAgendaMessageRequest(pedido); err == nil {
			t.Fatalf("%s deveria ser recusado", chat)
		}
	}
	ambos := base
	ambos.ChatJID, ambos.Phones = "134230663237656@lid", []string{"558193563525"}
	if _, err := validarAgendaMessageRequest(ambos); err == nil {
		t.Fatal("chat_jid e phones juntos deveriam ser recusados")
	}
	porTelefone := base
	porTelefone.Phones = []string{"558193563525"}
	naConversa := base
	naConversa.ChatJID = "558193563525@s.whatsapp.net"
	if agendaPayloadHash(porTelefone) == agendaPayloadHash(naConversa) {
		t.Fatal("o alvo entra no resumo do pedido")
	}
}
