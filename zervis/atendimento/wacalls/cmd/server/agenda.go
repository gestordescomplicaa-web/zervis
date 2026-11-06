// Zérvis (06/11/2026): a agenda do celular, para o Zé achar quem nunca escreveu desde a conexão
// ("responde a Isabelle Vieira"). O whatsmeow já sincroniza a agenda (app state) depois do
// pareamento e a guarda no store local: aqui só se lê, nada é pedido ao WhatsApp.

package main

import (
	"context"
	"errors"
	"net/http"
	"sort"
	"strings"
	"time"

	"go.mau.fi/whatsmeow/types"
)

// contatoDaAgenda é um contato salvo no celular: o nome como está na agenda e o número, quando
// se sabe (um contato que só veio pelo LID e sem o mapa para o número fica só com o LID).
type contatoDaAgenda struct {
	Nome     string `json:"name"`
	Telefone string `json:"phone,omitempty"`
	LID      string `json:"lid,omitempty"`
}

type agendaCompleta interface {
	GetAllContacts(ctx context.Context) (map[types.JID]types.ContactInfo, error)
}

type numeroDoLID interface {
	GetPNForLID(ctx context.Context, lid types.JID) (types.JID, error)
}

var errSemAgenda = errors.New("agenda indisponível")

func (s *Session) agenda(ctx context.Context) ([]contatoDaAgenda, error) {
	if s.client == nil || s.client.Store == nil || s.client.Store.Contacts == nil {
		return nil, errSemAgenda
	}
	var lids numeroDoLID
	if s.client.Store.LIDs != nil {
		lids = s.client.Store.LIDs
	}
	return montarAgenda(ctx, s.client.Store.Contacts, lids)
}

// montarAgenda junta o mesmo contato vindo pelo número e pelo LID, fica só com quem tem nome na
// agenda (o nome de perfil não é a agenda) e ordena pelo nome.
func montarAgenda(ctx context.Context, agenda agendaCompleta, lids numeroDoLID) ([]contatoDaAgenda, error) {
	todos, err := agenda.GetAllContacts(ctx)
	if err != nil {
		return nil, err
	}
	porChave := map[string]*contatoDaAgenda{}
	for jid, info := range todos {
		nome := strings.TrimSpace(info.FullName)
		if nome == "" {
			nome = strings.TrimSpace(info.FirstName)
		}
		if nome == "" {
			continue
		}
		c := contatoDaAgenda{Nome: nome}
		switch jid.Server {
		case types.DefaultUserServer:
			c.Telefone = jid.User
		case types.HiddenUserServer:
			c.LID = jid.User
			if lids != nil {
				if pn, err := lids.GetPNForLID(ctx, jid); err == nil && !pn.IsEmpty() {
					c.Telefone = pn.User
				}
			}
		default:
			continue
		}
		chave := c.Telefone
		if chave == "" {
			chave = "lid:" + c.LID
		}
		if atual, ok := porChave[chave]; ok {
			if atual.LID == "" {
				atual.LID = c.LID
			}
			continue
		}
		porChave[chave] = &c
	}
	lista := make([]contatoDaAgenda, 0, len(porChave))
	for _, c := range porChave {
		lista = append(lista, *c)
	}
	sort.Slice(lista, func(i, j int) bool {
		if lista[i].Nome != lista[j].Nome {
			return lista[i].Nome < lista[j].Nome
		}
		return lista[i].Telefone < lista[j].Telefone
	})
	return lista, nil
}

func (s *server) handleContacts(w http.ResponseWriter, r *http.Request) {
	sess := s.sessionByID(w, r.PathValue("sid"))
	if sess == nil {
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	lista, err := sess.agenda(ctx)
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"error": "contacts unavailable"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"contacts": lista})
}
