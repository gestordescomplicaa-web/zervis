package call

import (
	"context"
	"errors"
	"log/slog"
	"testing"

	"wacalls/internal/voip/core"

	waBinary "go.mau.fi/whatsmeow/binary"
	"go.mau.fi/whatsmeow/types"
)

type socketAcceptFake struct {
	erroEnvio error
	enviado   *waBinary.Node
	chave     []byte
}

func (s *socketAcceptFake) OwnPN() types.JID  { return types.JID{} }
func (s *socketAcceptFake) OwnLID() types.JID { return types.JID{} }
func (s *socketAcceptFake) AccountDeviceIdentityNode() (waBinary.Node, bool) {
	return waBinary.Node{}, false
}
func (s *socketAcceptFake) SendNode(_ context.Context, node waBinary.Node) error {
	s.enviado = &node
	return s.erroEnvio
}
func (s *socketAcceptFake) Query(context.Context, waBinary.Node) (*waBinary.Node, error) {
	return nil, nil
}
func (s *socketAcceptFake) GetUSyncDevices(context.Context, []types.JID) ([]types.JID, error) {
	return nil, nil
}
func (s *socketAcceptFake) AssertSessions(context.Context, []types.JID, bool) error {
	return nil
}
func (s *socketAcceptFake) CreateParticipantNodes(context.Context, []types.JID, []byte, waBinary.Attrs) ([]waBinary.Node, bool, error) {
	return nil, false, nil
}
func (s *socketAcceptFake) DecryptCallKey(context.Context, types.JID, *waBinary.Node) ([]byte, error) {
	return s.chave, nil
}
func (s *socketAcceptFake) GetTCToken(context.Context, types.JID) ([]byte, error) {
	return nil, nil
}
func (s *socketAcceptFake) ResolveLIDForPN(_ context.Context, jid types.JID) types.JID {
	return jid
}
func (s *socketAcceptFake) ResolveLIDForCall(_ context.Context, jid types.JID) (types.JID, error) {
	return jid, nil
}

func incomingParaAceitar() *CallInfo {
	call := NewIncomingCall(
		"CALL-ID", "134042238365931:7@lid", "134042238365931@lid", "",
		core.CallMediaTypeAudio,
	)
	call.EncryptionKey = []byte("chave-de-midia-ja-decifrada")
	return call
}

func TestAcceptPropagaFalhaDeEnvioEEncerraChamada(t *testing.T) {
	sock := &socketAcceptFake{erroEnvio: errors.New("socket indisponivel")}
	m := NewCallManager(sock, slog.Default())
	m.currentCall = incomingParaAceitar()

	err := m.AcceptCall(context.Background(), "CALL-ID")
	if err == nil || !m.currentCall.IsEnded() {
		t.Fatalf("falha de accept deve chegar ao chamador e encerrar: err=%v state=%s",
			err, m.currentCall.StateData.State)
	}
	if m.currentCall.StateData.EndReason != core.EndCallReasonFailed {
		t.Fatalf("motivo = %s; want failed", m.currentCall.StateData.EndReason)
	}
}

func TestAcceptRecusaChamadaSemChaveDeMidia(t *testing.T) {
	sock := &socketAcceptFake{}
	m := NewCallManager(sock, slog.Default())
	m.currentCall = incomingParaAceitar()
	m.currentCall.EncryptionKey = nil

	if err := m.AcceptCall(context.Background(), "CALL-ID"); err == nil {
		t.Fatal("chamada sem chave de midia nao pode fingir que foi aceita")
	}
	if sock.enviado != nil {
		t.Fatal("nenhum accept pode sair sem chave de media")
	}
}

func offerInboundTeste(peer types.JID) *waBinary.Node {
	return &waBinary.Node{
		Tag:   "call",
		Attrs: waBinary.Attrs{"from": peer, "id": "WRAPPER"},
		Content: []waBinary.Node{{
			Tag: "offer",
			Attrs: waBinary.Attrs{
				"call-id": "CALL-ID", "call-creator": peer,
			},
		}},
	}
}

func TestOfferSemChaveNaoViraChamadaAtendivel(t *testing.T) {
	peer, _ := types.ParseJID("134042238365931:7@lid")
	sock := &socketAcceptFake{}
	m := NewCallManager(sock, slog.Default())

	if err := m.HandleCallOffer(context.Background(), offerInboundTeste(peer), peer); err == nil {
		t.Fatal("offer sem chave deve falhar antes do preaccept")
	}
	if m.currentCall != nil || sock.enviado != nil {
		t.Fatal("offer invalido nao pode tocar no painel nem enviar preaccept")
	}
}

func TestFalhaNoPreacceptNaoViraChamadaAtendivel(t *testing.T) {
	peer, _ := types.ParseJID("134042238365931:7@lid")
	offer := offerInboundTeste(peer)
	inner := offer.Content.([]waBinary.Node)
	inner[0].Content = []waBinary.Node{{
		Tag: "enc", Attrs: waBinary.Attrs{"type": "pkmsg"}, Content: []byte("cifra"),
	}}
	offer.Content = inner
	sock := &socketAcceptFake{
		chave:     []byte("chave-de-midia-ja-decifrada"),
		erroEnvio: errors.New("socket indisponivel"),
	}
	m := NewCallManager(sock, slog.Default())

	if err := m.HandleCallOffer(context.Background(), offer, peer); err == nil {
		t.Fatal("falha de preaccept precisa chegar ao chamador")
	}
	if m.currentCall == nil || !m.currentCall.IsEnded() {
		t.Fatal("falha de preaccept deve encerrar o estado interno")
	}
}

func TestOfferComLIDPreservaCallerPNParaIdentidade(t *testing.T) {
	peer, _ := types.ParseJID("134042238365931:7@lid")
	offer := offerInboundTeste(peer)
	inner := offer.Content.([]waBinary.Node)
	inner[0].Attrs["caller_pn"] = "558199990000@s.whatsapp.net"
	inner[0].Content = []waBinary.Node{{
		Tag: "enc", Attrs: waBinary.Attrs{"type": "pkmsg"}, Content: []byte("cifra"),
	}}
	offer.Content = inner
	sock := &socketAcceptFake{chave: []byte("chave-de-midia-ja-decifrada")}
	m := NewCallManager(sock, slog.Default())
	var recebida *CallInfo
	m.OnIncoming = func(c *CallInfo) { recebida = c }

	if err := m.HandleCallOffer(context.Background(), offer, peer); err != nil {
		t.Fatalf("offer valido falhou: %v", err)
	}
	if recebida == nil || recebida.CallerPn != "558199990000" {
		t.Fatalf("CallerPn = %v; want 558199990000", recebida)
	}
}
