package signaling

import (
	"context"
	"fmt"
	"wacalls/internal/voip/core"
	"wacalls/internal/voip/wanode"

	waBinary "go.mau.fi/whatsmeow/binary"
	"go.mau.fi/whatsmeow/types"
)

var (
	// Capturas atuais do cliente oficial (2026-07). Estes bytes fazem parte da
	// negociacao de codec; o formato anterior ainda era aceito no outbound,
	// mas passou a fazer o telefone encerrar o answer inbound como
	// `uncallable` logo depois do nosso <accept>.
	capabilityOffer     = []byte{0x01, 0x05, 0xf7, 0x09, 0xe0, 0xbb, 0x13}
	capabilityPreaccept = []byte{0x01, 0x05, 0xf7, 0x09, 0xe0, 0xbb, 0x07}
)

func BuildOfferStanza(ctx context.Context, sock core.VoipSocket, callID string, callKey []byte, peerJid types.JID, isVideo bool) (waBinary.Node, error) {
	creator := sock.OwnLID()
	if creator.IsEmpty() {
		creator = sock.OwnPN()
	}

	rawDevices, err := sock.GetUSyncDevices(ctx, []types.JID{peerJid})
	if err != nil {
		return waBinary.Node{}, fmt.Errorf("usync devices: %w", err)
	}
	if err := sock.AssertSessions(ctx, rawDevices, false); err != nil {
		return waBinary.Node{}, fmt.Errorf("assert sessions: %w", err)
	}

	destinations, includeDeviceIdentity, err := sock.CreateParticipantNodes(ctx, rawDevices, callKey, waBinary.Attrs{"count": "0"})
	if err != nil {
		return waBinary.Node{}, fmt.Errorf("participant nodes: %w", err)
	}

	var offerContent []waBinary.Node

	if token, err := sock.GetTCToken(ctx, wanode.MustJID(wanode.CleanJID(peerJid.String()))); err == nil && len(token) > 0 {
		offerContent = append(offerContent, waBinary.Node{Tag: "privacy", Content: token})
	}

	offerContent = append(offerContent,
		waBinary.Node{Tag: "audio", Attrs: waBinary.Attrs{"enc": "opus", "rate": "8000"}},
		waBinary.Node{Tag: "audio", Attrs: waBinary.Attrs{"enc": "opus", "rate": "16000"}},
	)
	if isVideo {
		offerContent = append(offerContent, waBinary.Node{Tag: "video", Attrs: waBinary.Attrs{
			"enc": "vp8", "dec": "vp8", "orientation": "0",
			"screen_width": "1920", "screen_height": "1080", "device_orientation": "0",
		}})
	}
	offerContent = append(offerContent,
		waBinary.Node{Tag: "net", Attrs: waBinary.Attrs{"medium": "3"}},
		waBinary.Node{Tag: "capability", Attrs: waBinary.Attrs{"ver": "1"}, Content: capabilityOffer},
		waBinary.Node{Tag: "destination", Content: destinations},
		waBinary.Node{Tag: "encopt", Attrs: waBinary.Attrs{"keygen": "2"}},
	)
	if includeDeviceIdentity {
		if di, ok := sock.AccountDeviceIdentityNode(); ok {
			offerContent = append(offerContent, di)
		}
	}

	return waBinary.Node{
		Tag:   "call",
		Attrs: waBinary.Attrs{"to": peerJid, "id": GenerateCallStanzaID()},
		Content: []waBinary.Node{{
			Tag:     "offer",
			Attrs:   waBinary.Attrs{"call-id": callID, "call-creator": creator},
			Content: offerContent,
		}},
	}, nil
}

// BuildAcceptStanza reproduz o answer enviado pelo cliente atual: a chave da
// chamada vem no OFFER e e' usada localmente pelo SRTP; ela NAO e' reenviada
// dentro do ACCEPT. O formato antigo incluia <enc>, device-identity e
// net medium=3. O servidor aceitava a escrita, mas o telefone encerrava a
// chamada imediatamente com reason=uncallable.
func BuildAcceptStanza(callID string, peerJid, callCreator types.JID, isVideo bool) waBinary.Node {
	acceptContent := []waBinary.Node{
		{Tag: "audio", Attrs: waBinary.Attrs{"enc": "opus", "rate": "16000"}},
	}
	if isVideo {
		acceptContent = append(acceptContent, waBinary.Node{Tag: "video", Attrs: waBinary.Attrs{
			"dec": "H264", "device_orientation": "0",
		}})
	}
	acceptContent = append(acceptContent,
		waBinary.Node{Tag: "net", Attrs: waBinary.Attrs{"medium": "2"}},
		waBinary.Node{Tag: "encopt", Attrs: waBinary.Attrs{"keygen": "2"}},
	)
	if !isVideo {
		acceptContent = append(acceptContent,
			waBinary.Node{Tag: "capability", Attrs: waBinary.Attrs{"ver": "1"}, Content: capabilityOffer})
	}

	return waBinary.Node{
		Tag: "call",
		// Sinalizacao e' por dispositivo. Limpar o :device aqui pode responder ao
		// aparelho errado quando o contato usa celular + WhatsApp Web.
		Attrs: waBinary.Attrs{"to": peerJid, "id": GenerateCallStanzaID()},
		Content: []waBinary.Node{{
			Tag:     "accept",
			Attrs:   waBinary.Attrs{"call-id": callID, "call-creator": callCreator},
			Content: acceptContent,
		}},
	}
}

func BuildTerminateStanza(peerJid types.JID, callID string, callCreator types.JID) waBinary.Node {
	return callWrap(peerJid, waBinary.Node{
		Tag:   "terminate",
		Attrs: waBinary.Attrs{"call-id": callID, "call-creator": callCreator},
	})
}

func BuildRejectStanza(peerJid types.JID, callID string, callCreator types.JID) waBinary.Node {
	return callWrap(peerJid, waBinary.Node{
		Tag:   "reject",
		Attrs: waBinary.Attrs{"call-id": callID, "call-creator": callCreator},
	})
}

func BuildPreacceptStanza(peerJid types.JID, callID string, callCreator types.JID) waBinary.Node {
	return waBinary.Node{
		Tag:   "call",
		Attrs: waBinary.Attrs{"to": peerJid, "id": GenerateCallStanzaID()},
		Content: []waBinary.Node{{
			Tag:   "preaccept",
			Attrs: waBinary.Attrs{"call-id": callID, "call-creator": callCreator},
			Content: []waBinary.Node{
				{Tag: "audio", Attrs: waBinary.Attrs{"enc": "opus", "rate": "16000"}},
				{Tag: "encopt", Attrs: waBinary.Attrs{"keygen": "2"}},
				{Tag: "capability", Attrs: waBinary.Attrs{"ver": "1"}, Content: capabilityPreaccept},
			},
		}},
	}
}

func CreateCallAck(nodeID string, peerJid types.JID, typ string) waBinary.Node {
	return waBinary.Node{
		Tag:   "ack",
		Attrs: waBinary.Attrs{"id": nodeID, "to": peerJid, "class": "call", "type": typ},
	}
}

type RelayLatencyEntry struct {
	RelayName    string
	Latency      int
	AddressBytes []byte
}

func BuildRelayLatencyStanza(peerJid types.JID, callID string, callCreator types.JID, relays []RelayLatencyEntry, destinationJids []types.JID) waBinary.Node {
	seen := map[string]bool{}
	var teNodes []waBinary.Node
	for _, r := range relays {
		if r.RelayName == "" || seen[r.RelayName] {
			continue
		}
		seen[r.RelayName] = true
		encodedLatency := 0x2000000 + r.Latency
		te := waBinary.Node{
			Tag:   "te",
			Attrs: waBinary.Attrs{"latency": fmt.Sprintf("%d", encodedLatency), "relay_name": r.RelayName},
		}
		if len(r.AddressBytes) > 0 {
			te.Content = r.AddressBytes
		}
		teNodes = append(teNodes, te)
	}

	content := append([]waBinary.Node(nil), teNodes...)
	if len(destinationJids) > 0 {
		var dst []waBinary.Node
		for _, jid := range destinationJids {
			dst = append(dst, waBinary.Node{Tag: "to", Attrs: waBinary.Attrs{"jid": jid}})
		}
		content = append(content, waBinary.Node{Tag: "destination", Content: dst})
	}

	return callWrap(wanode.MustJID(wanode.CleanJID(peerJid.String())), waBinary.Node{
		Tag:     "relaylatency",
		Attrs:   waBinary.Attrs{"call-id": callID, "call-creator": callCreator},
		Content: content,
	})
}

func BuildTransportStanza(peerJid types.JID, callID string, callCreator types.JID) waBinary.Node {
	return callWrap(wanode.MustJID(wanode.CleanJID(peerJid.String())), waBinary.Node{
		Tag: "transport",
		Attrs: waBinary.Attrs{
			"call-id": callID, "call-creator": callCreator,
			"transport-message-type": "0", "p2p-cand-round": "0",
		},
		Content: []waBinary.Node{{Tag: "net", Attrs: waBinary.Attrs{"medium": "2", "protocol": "0"}}},
	})
}

func BuildMuteV2Stanza(peerDeviceJid types.JID, callID string, callCreator types.JID, muteState int) waBinary.Node {
	return waBinary.Node{
		Tag:   "call",
		Attrs: waBinary.Attrs{"to": peerDeviceJid, "id": GenerateCallStanzaID()},
		Content: []waBinary.Node{{
			Tag: "mute_v2",
			Attrs: waBinary.Attrs{
				"call-id": callID, "call-creator": callCreator,
				"mute-state": fmt.Sprintf("%d", muteState),
			},
		}},
	}
}

func BuildAcceptReceiptStanza(peerDeviceJid types.JID, acceptMsgID, callID string, callCreator, ourJid types.JID) waBinary.Node {
	return waBinary.Node{
		Tag:   "receipt",
		Attrs: waBinary.Attrs{"to": peerDeviceJid, "id": acceptMsgID, "from": ourJid},
		Content: []waBinary.Node{{
			Tag:   "accept",
			Attrs: waBinary.Attrs{"call-id": callID, "call-creator": callCreator},
		}},
	}
}

func callWrap(to types.JID, inner waBinary.Node) waBinary.Node {
	return waBinary.Node{
		Tag:     "call",
		Attrs:   waBinary.Attrs{"to": to, "id": GenerateCallStanzaID()},
		Content: []waBinary.Node{inner},
	}
}
