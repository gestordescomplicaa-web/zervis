package mlow

import (
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

// deterministicCapacityFrame avoids trigonometry in the fixture itself. The
// encoder receives exactly the same float32 sequence on every run/architecture.
func deterministicCapacityFrame(seed *uint32, pcm []float32) {
	for i := range pcm {
		*seed = *seed*1664525 + 1013904223
		v := int32(*seed>>8) - (1 << 23)
		pcm[i] = float32(v) / float32(1<<24)
	}
}

// TestEncoderCapacityGolden pins the complete wire output before performance
// work. FFT/buffer optimizations must preserve this hash: faster is not useful
// if the phone receives a different or invalid MLow stream.
func TestEncoderCapacityGolden(t *testing.T) {
	enc := NewMlowEncoder()
	h := sha256.New()
	pcm := make([]float32, opusFrameSamps)
	seed := uint32(0x4c494741)
	for frame := 0; frame < 12; frame++ {
		deterministicCapacityFrame(&seed, pcm)
		encoded, err := enc.Encode(pcm)
		if err != nil {
			t.Fatalf("frame %d: %v", frame, err)
		}
		h.Write([]byte{byte(len(encoded) >> 8), byte(len(encoded))})
		h.Write(encoded)
	}
	got := hex.EncodeToString(h.Sum(nil))
	const want = "7fe78d3ef5eecd33ca13cab4c1794c4bc28330deb0f982af9abd4cc0d2e9cbc7"
	if got != want {
		t.Fatalf("wire hash = %s; want %s", got, want)
	}
}

func BenchmarkMlowEncodeCapacity(b *testing.B) {
	enc := NewMlowEncoder()
	pcm := make([]float32, opusFrameSamps)
	seed := uint32(0x4c494741)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		deterministicCapacityFrame(&seed, pcm)
		if _, err := enc.Encode(pcm); err != nil {
			b.Fatal(err)
		}
	}
}
