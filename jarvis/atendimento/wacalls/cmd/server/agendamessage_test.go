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
