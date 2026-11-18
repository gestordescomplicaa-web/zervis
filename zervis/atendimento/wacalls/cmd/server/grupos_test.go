package main

import (
	"testing"

	"go.mau.fi/whatsmeow/types"
)

func TestGruposSoDeConversaOrdenadosPeloNome(t *testing.T) {
	grupo := func(user, nome string, pessoas int, comunidade bool) *types.GroupInfo {
		g := &types.GroupInfo{JID: types.NewJID(user, types.GroupServer)}
		g.Name = nome
		g.IsParent = comunidade
		g.Participants = make([]types.GroupParticipant, pessoas)
		return g
	}
	lista := montarGrupos([]*types.GroupInfo{
		grupo("120363000000000002", "padaria — equipe", 4, false),
		grupo("120363000000000003", "Comunidade", 90, true),
		nil,
		grupo("120363000000000001", "Academia Forte", 7, false),
	})
	if len(lista) != 2 {
		t.Fatalf("esperava 2 grupos, veio %d: %+v", len(lista), lista)
	}
	if lista[0].Nome != "Academia Forte" || lista[0].Participantes != 7 ||
		lista[0].Chat != "120363000000000001@g.us" {
		t.Fatalf("primeiro grupo errado: %+v", lista[0])
	}
	if lista[1].Nome != "padaria — equipe" {
		t.Fatalf("segundo grupo errado: %+v", lista[1])
	}
}
