package mlow

import (
	"math"
	"sync"
)

// cpx is a single-precision complex value.
//
// Source of truth: https://github.com/oxidezap/whatsapp-rust/blob/674e85164b35ca19115dfebcf605708d15951ee7/wacore/src/voip/mlow/smpl_perc.rs#L318-L343
type cpx struct {
	re, im float32
}

func (a cpx) add(b cpx) cpx {
	return cpx{re: a.re + b.re, im: a.im + b.im}
}

func (a cpx) mul(b cpx) cpx {
	return cpx{
		re: a.re*b.re - a.im*b.im,
		im: a.re*b.im + a.im*b.re,
	}
}

// smallestFactor returns the smallest prime factor of n (>= 2).
func smallestFactor(n int) int {
	// Source of truth: https://github.com/oxidezap/whatsapp-rust/blob/674e85164b35ca19115dfebcf605708d15951ee7/wacore/src/voip/mlow/smpl_perc.rs#L346-L358
	if n%2 == 0 {
		return 2
	}
	p := 3
	for p*p <= n {
		if n%p == 0 {
			return p
		}
		p += 2
	}
	return n
}

// fftPlan contains the immutable factor tree and its twiddle factors. MLow only
// uses fixed-size FFTs (512 and 576), but the old implementation recalculated
// every sin/cos and allocated a temporary slice at every recursion, for every
// 60 ms audio frame. Plans are shared read-only across calls.
type fftPlan struct {
	n, p, m    int
	prime      bool
	twiddles   []cpx
	child      *fftPlan
	scratchLen int
}

type fftPlanKey struct {
	n       int
	inverse bool
}

var fftPlans sync.Map

func fftPlanFor(n int, sign float32) *fftPlan {
	key := fftPlanKey{n: n, inverse: sign > 0}
	if cached, ok := fftPlans.Load(key); ok {
		return cached.(*fftPlan)
	}
	built := buildFFTPlan(n, sign)
	actual, _ := fftPlans.LoadOrStore(key, built)
	return actual.(*fftPlan)
}

func buildFFTPlan(n int, sign float32) *fftPlan {
	p := smallestFactor(n)
	plan := &fftPlan{n: n, p: p, prime: p == n}
	if plan.prime {
		plan.twiddles = make([]cpx, n*n)
		for k := 0; k < n; k++ {
			// Preserve the exact float32 operation order of the original leaf.
			angK := sign * 2.0 * smplPI * float32(k) / float32(n)
			for j := 0; j < n; j++ {
				ang := angK * float32(j)
				plan.twiddles[k*n+j] = cpx{
					re: float32(math.Cos(float64(ang))),
					im: float32(math.Sin(float64(ang))),
				}
			}
		}
		return plan
	}

	plan.m = n / p
	plan.child = buildFFTPlan(plan.m, sign)
	plan.scratchLen = n + plan.child.scratchLen
	plan.twiddles = make([]cpx, n*p)
	for k := 0; k < n; k++ {
		for q := 0; q < p; q++ {
			// Preserve the exact float32 operation order of the original combine.
			ang := sign * 2.0 * smplPI * float32(k) * float32(q) / float32(n)
			plan.twiddles[k*p+q] = cpx{
				re: float32(math.Cos(float64(ang))),
				im: float32(math.Sin(float64(ang))),
			}
		}
	}
	return plan
}

// fftRecPlanned is the same recursive mixed-radix Cooley-Tukey DFT, using an
// immutable plan and caller-owned scratch. Addition/multiplication order stays
// unchanged so the MLow wire output remains bit-exact.
func fftRecPlanned(x []cpx, stride int, plan *fftPlan, out, scratch []cpx) {
	// Source of truth: https://github.com/oxidezap/whatsapp-rust/blob/674e85164b35ca19115dfebcf605708d15951ee7/wacore/src/voip/mlow/smpl_perc.rs#L362-L405
	if plan.n == 1 {
		out[0] = x[0]
		return
	}
	if plan.prime {
		for k := 0; k < plan.n; k++ {
			var acc cpx
			row := plan.twiddles[k*plan.n : (k+1)*plan.n]
			for j := 0; j < plan.n; j++ {
				w := row[j]
				acc = acc.add(x[j*stride].mul(w))
			}
			out[k] = acc
		}
		return
	}
	sub := scratch[:plan.n]
	childScratch := scratch[plan.n:]
	for q := 0; q < plan.p; q++ {
		fftRecPlanned(
			x[q*stride:], stride*plan.p, plan.child,
			sub[q*plan.m:(q+1)*plan.m], childScratch,
		)
	}
	for k := 0; k < plan.n; k++ {
		kmod := k % plan.m
		var acc cpx
		for q := 0; q < plan.p; q++ {
			tw := plan.twiddles[k*plan.p+q]
			acc = acc.add(sub[q*plan.m+kmod].mul(tw))
		}
		out[k] = acc
	}
}

// cfft computes the complex FFT of a mixed-radix length into out. sign=-1 forward,
// +1 inverse.
func cfft(input, out []cpx, sign float32) {
	// Source of truth: https://github.com/oxidezap/whatsapp-rust/blob/674e85164b35ca19115dfebcf605708d15951ee7/wacore/src/voip/mlow/smpl_perc.rs#L408-L412
	plan := fftPlanFor(len(input), sign)
	fftRecPlanned(input, 1, plan, out, make([]cpx, plan.scratchLen))
}

type fftWorkspace struct {
	input, output []cpx
	scratch       []cpx
}

var fftWorkspacePools sync.Map

func fftWorkspacePool(n int) *sync.Pool {
	if cached, ok := fftWorkspacePools.Load(n); ok {
		return cached.(*sync.Pool)
	}
	plan := fftPlanFor(n, -1.0)
	built := &sync.Pool{New: func() any {
		return &fftWorkspace{
			input:   make([]cpx, n),
			output:  make([]cpx, n),
			scratch: make([]cpx, plan.scratchLen),
		}
	}}
	actual, _ := fftWorkspacePools.LoadOrStore(n, built)
	return actual.(*sync.Pool)
}

func acquireFFTWorkspace(n int) (*fftWorkspace, *sync.Pool) {
	pool := fftWorkspacePool(n)
	return pool.Get().(*fftWorkspace), pool
}

// rfftForwardOrdered is the forward real FFT of n real samples, re-packed into the
// ordered REAL layout: f[0]=DC.re, f[1]=Nyquist.re, then [re,im] pairs for bins
// 1..n/2-1. Output length is n.
func rfftForwardOrdered(time, f []float32) {
	// Source of truth: https://github.com/oxidezap/whatsapp-rust/blob/674e85164b35ca19115dfebcf605708d15951ee7/wacore/src/voip/mlow/smpl_perc.rs#L416-L432
	n := len(time)
	workspace, pool := acquireFFTWorkspace(n)
	defer pool.Put(workspace)
	cin := workspace.input
	for i := 0; i < n; i++ {
		cin[i] = cpx{re: time[i]}
	}
	spec := workspace.output
	plan := fftPlanFor(n, -1.0)
	fftRecPlanned(cin, 1, plan, spec, workspace.scratch)
	f[0] = spec[0].re
	f[1] = spec[n/2].re
	for i := 1; i < n/2; i++ {
		f[2*i] = spec[i].re
		f[2*i+1] = spec[i].im
	}
}
