package signaling

import (
	"bytes"
	"testing"

	"wacalls/internal/voip/wanode"

	"go.mau.fi/whatsmeow/types"
)

func jidTeste(t *testing.T, raw string) types.JID {
	t.Helper()
	jid, err := types.ParseJID(raw)
	if err != nil {
		t.Fatalf("jid %q: %v", raw, err)
	}
	return jid
}

func acaoDaChamada(t *testing.T, tag string, nodeChildren func() []string) {
	t.Helper()
	got := nodeChildren()
	want := []string{"audio", "net", "encopt", "capability"}
	if len(got) != len(want) {
		t.Fatalf("%s children = %v; want %v", tag, got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("%s children = %v; want %v", tag, got, want)
		}
	}
}

func TestAcceptAudioSegueFormatoAtual(t *testing.T) {
	peer := jidTeste(t, "134042238365931:7@lid")
	creator := jidTeste(t, "134042238365931@lid")
	node := BuildAcceptStanza("CALL-ID", peer, creator, false)

	if got := wanode.AttrString(node.Attrs, "to"); got != peer.String() {
		t.Fatalf("accept deve preservar o device JID: got %q want %q", got, peer.String())
	}
	if wanode.AttrString(node.Attrs, "id") == "" {
		t.Fatal("accept precisa de wrapper id para correlacao do servidor")
	}
	outer := wanode.NodeChildren(&node)
	if len(outer) != 1 || outer[0].Tag != "accept" {
		t.Fatalf("wrapper inesperado: %+v", outer)
	}
	accept := outer[0]
	children := wanode.NodeChildren(&accept)
	acaoDaChamada(t, "accept", func() []string {
		out := make([]string, 0, len(children))
		for i := range children {
			out = append(out, children[i].Tag)
		}
		return out
	})
	if got := wanode.AttrString(children[1].Attrs, "medium"); got != "2" {
		t.Fatalf("accept net medium = %q; want 2", got)
	}
	for i := range children {
		if children[i].Tag == "enc" || children[i].Tag == "device-identity" {
			t.Fatalf("accept nao pode reenviar chave/dispositivo: %s", children[i].Tag)
		}
	}
	if !bytes.Equal(wanode.NodeBytes(&children[3]), capabilityOffer) {
		t.Fatalf("capability do accept = %x; want %x", wanode.NodeBytes(&children[3]), capabilityOffer)
	}
}

func TestPreacceptAudioSegueFormatoAtual(t *testing.T) {
	peer := jidTeste(t, "134042238365931:7@lid")
	creator := jidTeste(t, "134042238365931@lid")
	node := BuildPreacceptStanza(peer, "CALL-ID", creator)
	outer := wanode.NodeChildren(&node)
	if len(outer) != 1 || outer[0].Tag != "preaccept" {
		t.Fatalf("wrapper inesperado: %+v", outer)
	}
	children := wanode.NodeChildren(&outer[0])
	want := []string{"audio", "encopt", "capability"}
	if len(children) != len(want) {
		t.Fatalf("preaccept children = %d; want %d", len(children), len(want))
	}
	for i := range want {
		if children[i].Tag != want[i] {
			t.Fatalf("preaccept child %d = %s; want %s", i, children[i].Tag, want[i])
		}
	}
	if !bytes.Equal(wanode.NodeBytes(&children[2]), capabilityPreaccept) {
		t.Fatalf("capability do preaccept = %x; want %x", wanode.NodeBytes(&children[2]), capabilityPreaccept)
	}
}
