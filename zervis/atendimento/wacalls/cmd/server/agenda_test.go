package main

import (
	"context"
	"testing"

	"go.mau.fi/whatsmeow/types"
)

func (a agendaFalsa) GetAllContacts(context.Context) (map[types.JID]types.ContactInfo, error) {
	return a, nil
}

type lidsFalsos map[types.JID]types.JID

func (l lidsFalsos) GetPNForLID(_ context.Context, lid types.JID) (types.JID, error) {
	return l[lid], nil
}

func TestAgendaJuntaNumeroELIDESoTemQuemEstaSalvo(t *testing.T) {
	pn := types.NewJID("5581999990001", types.DefaultUserServer)
	lid := types.NewJID("123456789", types.HiddenUserServer)
	soLID := types.NewJID("987654321", types.HiddenUserServer)
	agenda := agendaFalsa{
		pn:    {Found: true, FullName: "Marta Quintela", PushName: "Martinha"},
		lid:   {Found: true, FullName: "Marta Quintela"},
		soLID: {Found: true, FirstName: "Bruno"},
		types.NewJID("5581999990002", types.DefaultUserServer): {Found: true, PushName: "Só perfil"},
		types.NewJID("120363000000000000", types.GroupServer):  {Found: true, FullName: "Grupo"},
	}
	lista, err := montarAgenda(context.Background(), agenda, lidsFalsos{lid: pn})
	if err != nil {
		t.Fatal(err)
	}
	if len(lista) != 2 {
		t.Fatalf("esperava Bruno e Marta, veio %+v", lista)
	}
	if lista[0] != (contatoDaAgenda{Nome: "Bruno", LID: "987654321"}) {
		t.Fatalf("contato só pelo LID: %+v", lista[0])
	}
	if lista[1] != (contatoDaAgenda{Nome: "Marta Quintela", Telefone: "5581999990001", LID: "123456789"}) {
		t.Fatalf("número e LID juntos: %+v", lista[1])
	}
}
