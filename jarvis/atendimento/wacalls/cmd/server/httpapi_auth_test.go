package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestInternalAuthProtectsEveryAPIPath(t *testing.T) {
	called := false
	h := withInternalAuth("segredo-de-teste", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.WriteHeader(http.StatusNoContent)
	}))

	for _, tc := range []struct {
		name   string
		token  string
		status int
	}{
		{"sem token", "", http.StatusUnauthorized},
		{"token errado", "errado", http.StatusUnauthorized},
		{"token correto", "segredo-de-teste", http.StatusNoContent},
	} {
		t.Run(tc.name, func(t *testing.T) {
			called = false
			r := httptest.NewRequest(http.MethodGet, "/api/sessions", nil)
			if tc.token != "" {
				r.Header.Set("X-Internal-Token", tc.token)
			}
			w := httptest.NewRecorder()
			h.ServeHTTP(w, r)
			if w.Code != tc.status {
				t.Fatalf("status = %d, want %d", w.Code, tc.status)
			}
			if called != (tc.status == http.StatusNoContent) {
				t.Fatalf("handler called = %v for %s", called, tc.name)
			}
		})
	}
}

func TestInternalAuthFailsClosedWhenSecretIsMissing(t *testing.T) {
	h := withInternalAuth("", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatal("API handler must not run without configured service secret")
	}))
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/api/events", nil)
	h.ServeHTTP(w, r)
	if w.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", w.Code, http.StatusServiceUnavailable)
	}
}

func TestInternalAuthLeavesStaticFilesOutsideTheAPI(t *testing.T) {
	called := false
	h := withInternalAuth("segredo-de-teste", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
	}))
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/", nil)
	h.ServeHTTP(w, r)
	if w.Code != http.StatusOK || !called {
		t.Fatalf("static path should reach its handler, status=%d called=%v", w.Code, called)
	}
}
