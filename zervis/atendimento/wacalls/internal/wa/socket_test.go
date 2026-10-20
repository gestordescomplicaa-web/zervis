package wa

import (
	"testing"

	"go.mau.fi/whatsmeow/types"
)

func TestLIDFromUserInfoUsesExactRequestedPN(t *testing.T) {
	requested := types.NewJID("5515999991004", types.DefaultUserServer)
	want := types.NewJID("123456789", types.HiddenUserServer)

	got := lidFromUserInfo(requested, map[types.JID]types.UserInfo{
		requested: {LID: want},
	})
	if got != want {
		t.Fatalf("got %s, want %s", got, want)
	}
}

func TestLIDFromUserInfoAcceptsSingleCanonicalizedPN(t *testing.T) {
	requested := types.NewJID("5581999991001", types.DefaultUserServer)
	canonical := types.NewJID("558199990000", types.DefaultUserServer)
	want := types.NewJID("134042238365931", types.HiddenUserServer)

	got := lidFromUserInfo(requested, map[types.JID]types.UserInfo{
		canonical: {LID: want},
	})
	if got != want {
		t.Fatalf("got %s, want canonical LID %s", got, want)
	}
}

func TestLIDFromUserInfoFailsClosedForAmbiguousResponse(t *testing.T) {
	requested := types.NewJID("5581999991001", types.DefaultUserServer)
	got := lidFromUserInfo(requested, map[types.JID]types.UserInfo{
		types.NewJID("558199990000", types.DefaultUserServer): {
			LID: types.NewJID("111", types.HiddenUserServer),
		},
		types.NewJID("5581999991002", types.DefaultUserServer): {
			LID: types.NewJID("222", types.HiddenUserServer),
		},
	})
	if !got.IsEmpty() {
		t.Fatalf("got %s, want empty LID for ambiguous response", got)
	}
}
