package main

import (
	"reflect"
	"testing"

	"go.mau.fi/whatsmeow/types"
)

func TestDistinctRegisteredPhonesCollapsesSameLID(t *testing.T) {
	got := distinctRegisteredPhones([]resolvedPhoneCandidate{
		{phone: "558199990000", identity: "123456789@lid"},
		{phone: "5581999991001", identity: "123456789@lid"},
	})
	want := []string{"558199990000"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("same WhatsApp identity must keep the preferred form: got %v want %v", got, want)
	}
}

func TestDistinctRegisteredPhonesKeepsDifferentLIDsAmbiguous(t *testing.T) {
	got := distinctRegisteredPhones([]resolvedPhoneCandidate{
		{phone: "558199990000", identity: "111@lid"},
		{phone: "5581999991001", identity: "222@lid"},
	})
	want := []string{"558199990000", "5581999991001"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("different WhatsApp identities must remain ambiguous: got %v want %v", got, want)
	}
}

// Regressão do outbound mudo: o WhatsApp indexa este número SEM o nono dígito,
// e é essa grafia que hidrata o mapa PN -> LID. Devolver a grafia solicitada
// (com o nono) mandava a discagem procurar um LID que nunca fora hidratado,
// caindo no PN e ficando 15s sem ACK.
func TestDistinctRegisteredPhonesKeepsCanonicalSpelling(t *testing.T) {
	got := distinctRegisteredPhones([]resolvedPhoneCandidate{
		{phone: "558199990000", identity: "134042238365931@lid"},
	})
	want := []string{"558199990000"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("a grafia canônica é a que tem LID hidratado: got %v want %v", got, want)
	}
}

func TestDistinctRegisteredPhonesFailsSafeWithoutCanonicalIdentity(t *testing.T) {
	got := distinctRegisteredPhones([]resolvedPhoneCandidate{
		{phone: "558199990000"},
		{phone: "5581999991001"},
	})
	want := []string{"558199990000", "5581999991001"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("different PNs without a canonical LID must remain distinct: got %v want %v", got, want)
	}
}

// Caso de 03/11/2026: a whatsmeow nova devolve o LID no JID; o envio ia para
// 134230663237656@s.whatsapp.net e falhava com "no LID found".
func TestIdentidadeCanonicaComLIDNoJID(t *testing.T) {
	pedido := types.NewJID("5581993563525", types.DefaultUserServer)
	pn, lid := identidadeCanonica(pedido, types.IsOnWhatsAppResponse{
		JID:         types.NewJID("134230663237656", types.HiddenUserServer),
		PhoneNumber: types.NewJID("558193563525", types.DefaultUserServer),
		IsIn:        true,
	})
	if pn.String() != "558193563525@s.whatsapp.net" || lid.String() != "134230663237656@lid" {
		t.Fatalf("pn=%s lid=%s", pn, lid)
	}
	// Resposta antiga (sem LID): o JID é o telefone canônico.
	pn, lid = identidadeCanonica(pedido, types.IsOnWhatsAppResponse{
		JID: types.NewJID("558193563525", types.DefaultUserServer), IsIn: true,
	})
	if pn.User != "558193563525" || !lid.IsEmpty() {
		t.Fatalf("pn=%s lid=%s", pn, lid)
	}
	// Só o LID, sem telefone: fica o telefone pedido.
	pn, lid = identidadeCanonica(pedido, types.IsOnWhatsAppResponse{
		JID: types.NewJID("134230663237656", types.HiddenUserServer), IsIn: true,
	})
	if pn.User != "5581993563525" || lid.User != "134230663237656" {
		t.Fatalf("pn=%s lid=%s", pn, lid)
	}
}
