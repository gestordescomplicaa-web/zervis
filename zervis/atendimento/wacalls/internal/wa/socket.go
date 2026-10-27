package wa

import (
	"context"
	"fmt"
	"time"

	"wacalls/internal/voip/core"
	"wacalls/internal/voip/signaling"

	"go.mau.fi/whatsmeow"
	waBinary "go.mau.fi/whatsmeow/binary"
	"go.mau.fi/whatsmeow/types"
)

type Socket struct {
	cli *whatsmeow.Client
}

func NewSocket(cli *whatsmeow.Client) *Socket { return &Socket{cli: cli} }

var _ core.VoipSocket = (*Socket)(nil)

func (s *Socket) di() *whatsmeow.DangerousInternalClient { return s.cli.DangerousInternals() }

func (s *Socket) OwnPN() types.JID { return s.di().GetOwnID() }

func (s *Socket) OwnLID() types.JID { return s.di().GetOwnLID() }

func (s *Socket) AccountDeviceIdentityNode() (waBinary.Node, bool) {
	if s.cli.Store == nil || s.cli.Store.Account == nil {
		return waBinary.Node{}, false
	}
	return s.di().MakeDeviceIdentityNode(), true
}

func (s *Socket) SendNode(ctx context.Context, node waBinary.Node) error {
	return s.di().SendNode(ctx, node)
}

func (s *Socket) Query(ctx context.Context, node waBinary.Node) (*waBinary.Node, error) {
	id, _ := node.Attrs["id"].(string)
	if id == "" {
		return nil, s.di().SendNode(ctx, node)
	}
	di := s.di()
	ch := di.WaitResponse(id)
	if err := di.SendNode(ctx, node); err != nil {
		di.CancelResponse(id, ch)
		return nil, err
	}
	select {
	case resp := <-ch:
		return resp, nil
	case <-time.After(15 * time.Second):
		di.CancelResponse(id, ch)
		return nil, fmt.Errorf("whatsapp response timeout: no ACK for node %q after 15s", id)
	case <-ctx.Done():
		di.CancelResponse(id, ch)
		return nil, ctx.Err()
	}
}

func (s *Socket) GetUSyncDevices(ctx context.Context, jids []types.JID) ([]types.JID, error) {
	return s.cli.GetUserDevices(ctx, jids)
}

func (s *Socket) AssertSessions(ctx context.Context, jids []types.JID, force bool) error {
	return nil
}

func (s *Socket) CreateParticipantNodes(ctx context.Context, devices []types.JID, callKey []byte, encAttrs waBinary.Attrs) ([]waBinary.Node, bool, error) {
	plaintext, err := signaling.EncodeCallKeyMessage(callKey)
	if err != nil {
		return nil, false, err
	}
	id := s.cli.GenerateMessageID()
	return s.di().EncryptMessageForDevices(ctx, devices, id, plaintext, plaintext, encAttrs)
}

func (s *Socket) DecryptCallKey(ctx context.Context, from types.JID, encChild *waBinary.Node) ([]byte, error) {
	typ, _ := encChild.Attrs["type"].(string)
	isPreKey := typ == "pkmsg"
	plaintext, _, err := s.di().DecryptDM(ctx, encChild, from, isPreKey, time.Now())
	if err != nil {
		return nil, err
	}
	return signaling.DecodeCallKeyPlaintext(plaintext)
}

func (s *Socket) GetTCToken(ctx context.Context, jid types.JID) ([]byte, error) {
	if s.cli.Store == nil || s.cli.Store.PrivacyTokens == nil {
		return nil, nil
	}
	for _, cand := range []types.JID{s.ResolveLIDForPN(ctx, jid).ToNonAD(), jid.ToNonAD()} {
		if cand.IsEmpty() {
			continue
		}
		tok, err := s.cli.Store.PrivacyTokens.GetPrivacyToken(ctx, cand)
		if err != nil {
			return nil, err
		}
		if tok != nil && len(tok.Token) > 0 {
			return tok.Token, nil
		}
	}
	return nil, nil
}

func (s *Socket) ResolveLIDForPN(ctx context.Context, pn types.JID) types.JID {
	if pn.Server == types.HiddenUserServer {
		return pn
	}
	if s.cli.Store != nil && s.cli.Store.LIDs != nil {
		if lid, err := s.cli.Store.LIDs.GetLIDForPN(ctx, pn); err == nil && !lid.IsEmpty() {
			return lid
		}
	}
	if info, err := s.cli.GetUserInfo(ctx, []types.JID{pn}); err == nil {
		if lid := lidFromUserInfo(pn, info); !lid.IsEmpty() {
			return lid
		}
	}
	return pn
}

// ResolveLIDForCall exige o LID: a sinalização de chamada atual do WhatsApp não
// devolve ACK para uma oferta endereçada ao PN, então cair no PN significa
// esperar 15s por uma resposta que nunca vem. Falhar aqui, na origem e sem
// espera, dá ao operador uma causa legível em vez de um telefone mudo.
func (s *Socket) ResolveLIDForCall(ctx context.Context, pn types.JID) (types.JID, error) {
	return callRecipient(pn, s.ResolveLIDForPN(ctx, pn))
}

// callRecipient isola a decisão de aceitar ou recusar o destinatário resolvido,
// para que a regra seja testável sem uma sessão do WhatsApp conectada.
func callRecipient(requested, resolved types.JID) (types.JID, error) {
	if resolved.Server == types.HiddenUserServer && !resolved.IsEmpty() {
		return resolved, nil
	}
	return types.EmptyJID, fmt.Errorf(
		"no LID for %s: WhatsApp call signaling requires a LID recipient", requested.String())
}

// lidFromUserInfo tolera a canonicalização feita pelo servidor do WhatsApp.
// Em especial no Brasil, uma consulta pelo PN com nono dígito pode devolver o
// mesmo usuário indexado pelo PN legado sem o nono. GetUserInfo recebeu apenas
// uma identidade, portanto um único item de resposta continua sendo uma
// correspondência inequívoca mesmo quando a chave foi canonicalizada.
func lidFromUserInfo(requested types.JID, info map[types.JID]types.UserInfo) types.JID {
	if exact, ok := info[requested]; ok && !exact.LID.IsEmpty() {
		return exact.LID
	}
	if len(info) != 1 {
		return types.EmptyJID
	}
	for _, canonical := range info {
		return canonical.LID
	}
	return types.EmptyJID
}
