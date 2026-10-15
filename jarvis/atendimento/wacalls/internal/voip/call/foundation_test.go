package call

import (
	"testing"

	"wacalls/internal/voip/core"
)

func TestCallStateMachine(t *testing.T) {
	c := NewOutgoingCall("CID", "peer@lid", "me@lid", core.CallMediaTypeAudio)
	if c.StateData.State != core.CallStateInitiating {
		t.Fatal("should start Initiating")
	}
	if err := c.ApplyTransition(Transition{Type: TransitionOfferSent}); err != nil {
		t.Fatal(err)
	}
	if c.StateData.State != core.CallStateRinging {
		t.Fatal("should be Ringing after offer_sent")
	}
	if err := c.ApplyTransition(Transition{Type: TransitionRemoteAccepted}); err != nil {
		t.Fatal(err)
	}
	if err := c.ApplyTransition(Transition{Type: TransitionMediaConnected}); err != nil {
		t.Fatal(err)
	}
	if !c.IsActive() {
		t.Fatal("should be Active")
	}

	if err := c.ApplyTransition(Transition{Type: TransitionOfferSent}); err == nil {
		t.Fatal("expected InvalidTransition")
	} else if _, ok := err.(*InvalidTransition); !ok {
		t.Fatalf("expected *InvalidTransition, got %T", err)
	}

	if err := c.ApplyTransition(Transition{Type: TransitionTerminated, Reason: core.EndCallReasonUserEnded}); err != nil {
		t.Fatal(err)
	}
	if !c.IsEnded() {
		t.Fatal("should be Ended")
	}
}

func TestPreferAcceptedDeviceNaoRegrideParaJIDBase(t *testing.T) {
	tests := []struct {
		name, current, candidate, want string
	}{
		{"primeiro accept mobile", "", "551199999999@lid", "551199999999@lid"},
		{"upgrade para device explicito", "551199999999@lid", "551199999999:7@lid", "551199999999:7@lid"},
		{"accept duplicado nao regride", "551199999999:7@lid", "551199999999@lid", "551199999999:7@lid"},
		{"outro device tardio nao troca", "551199999999:7@lid", "551199999999:9@lid", "551199999999:7@lid"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := preferAcceptedDevice(tt.current, tt.candidate); got != tt.want {
				t.Fatalf("preferAcceptedDevice(%q, %q) = %q; want %q", tt.current, tt.candidate, got, tt.want)
			}
		})
	}
}
