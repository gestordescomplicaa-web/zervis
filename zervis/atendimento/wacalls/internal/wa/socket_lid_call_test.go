package wa

import (
	"testing"

	"go.mau.fi/whatsmeow/types"
)

// Regressão do outbound mudo: a oferta de chamada endereçada ao PN não recebe
// ACK do WhatsApp e o operador esperava 15s por uma resposta que nunca vinha.
// O destinatário de uma chamada precisa ser recusado na origem quando o LID
// não foi resolvido, com causa legível no lugar de um telefone silencioso.

func TestCallRecipientAcceptsLID(t *testing.T) {
	pn := types.NewJID("5581999991001", types.DefaultUserServer)
	lid := types.NewJID("134042238365931", types.HiddenUserServer)

	got, err := callRecipient(pn, lid)
	if err != nil {
		t.Fatalf("um LID resolvido deve ser aceito: %v", err)
	}
	if got != lid {
		t.Fatalf("LID alterado: got %v want %v", got, lid)
	}
}

func TestCallRecipientRefusesPhoneNumberFallback(t *testing.T) {
	pn := types.NewJID("5581999991001", types.DefaultUserServer)

	// ResolveLIDForPN devolve o próprio PN quando não encontra o LID.
	got, err := callRecipient(pn, pn)
	if err == nil {
		t.Fatal("discar com PN deve falhar de imediato, não esperar o timeout de 15s")
	}
	if !got.IsEmpty() {
		t.Fatalf("nenhum destinatário deve ser devolvido quando o LID falta: got %v", got)
	}
}

func TestCallRecipientRefusesEmptyResolution(t *testing.T) {
	pn := types.NewJID("5581999991001", types.DefaultUserServer)

	got, err := callRecipient(pn, types.EmptyJID)
	if err == nil {
		t.Fatal("resolução vazia não pode virar destinatário de chamada")
	}
	if !got.IsEmpty() {
		t.Fatalf("nenhum destinatário deve ser devolvido: got %v", got)
	}
}
