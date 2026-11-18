// Zérvis (ADR 0105): os grupos em que o número conectado está, para ligar um grupo a uma
// empresa no painel. Só a lista (o nome e quantas pessoas): nenhuma mensagem é lida nem enviada.

package main

import (
	"context"
	"net/http"
	"sort"
	"strings"
	"time"

	"go.mau.fi/whatsmeow/types"
)

// grupoDoZe é um grupo em que o número conectado participa.
type grupoDoZe struct {
	Chat          string `json:"chat"`
	Nome          string `json:"name"`
	Participantes int    `json:"participants"`
}

// montarGrupos fica só com os grupos de conversa (a comunidade em si não recebe mensagens) e
// ordena pelo nome.
func montarGrupos(infos []*types.GroupInfo) []grupoDoZe {
	lista := make([]grupoDoZe, 0, len(infos))
	for _, g := range infos {
		if g == nil || g.JID.Server != types.GroupServer || g.IsParent {
			continue
		}
		lista = append(lista, grupoDoZe{
			Chat:          g.JID.String(),
			Nome:          strings.TrimSpace(g.Name),
			Participantes: len(g.Participants),
		})
	}
	sort.SliceStable(lista, func(i, j int) bool {
		return strings.ToLower(lista[i].Nome) < strings.ToLower(lista[j].Nome)
	})
	return lista
}

func (s *server) handleGroups(w http.ResponseWriter, r *http.Request) {
	sess := s.sessionByID(w, r.PathValue("sid"))
	if sess == nil {
		return
	}
	if sess.client == nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "groups unavailable"})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()
	infos, err := sess.client.GetJoinedGroups(ctx)
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "groups unavailable"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"groups": montarGrupos(infos)})
}
