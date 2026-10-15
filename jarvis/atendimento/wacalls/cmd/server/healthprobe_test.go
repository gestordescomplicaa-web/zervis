package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// A imagem é distroless: sem shell, wget ou curl, o healthcheck do container é
// o próprio binário. Se a sonda parar de distinguir vivo de morto, o Swarm perde
// a capacidade de substituir um WaCalls travado — a falha que o healthcheck
// existe para pegar.

func TestHealthProbeTargetNormalizaEnderecoDeEscuta(t *testing.T) {
	casos := map[string]string{
		":8080":          "127.0.0.1:8080",
		"0.0.0.0:8080":   "127.0.0.1:8080",
		"[::]:8080":      "127.0.0.1:8080",
		"127.0.0.1:9000": "127.0.0.1:9000",
		" :8080 ":        "127.0.0.1:8080",
		"sem-porta":      "127.0.0.1:8080",
	}
	for entrada, esperado := range casos {
		if got := healthProbeTarget(entrada); got != esperado {
			t.Errorf("healthProbeTarget(%q) = %q, esperado %q", entrada, got, esperado)
		}
	}
}

func TestProbeHealthAceitaServidorQueResponde(t *testing.T) {
	// 401 é o que o WaCalls devolve nas rotas autenticadas: prova que está
	// roteando. Exigir 200 ataria a sonda ao cliente estático, que é opcional.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer srv.Close()

	if code := probeHealth(srv.Listener.Addr().String()); code != 0 {
		t.Fatalf("servidor no ar deve passar no healthcheck: saiu %d", code)
	}
}

func TestProbeHealthRecusaErroDeServidor(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	if code := probeHealth(srv.Listener.Addr().String()); code != 1 {
		t.Fatalf("5xx deve reprovar o healthcheck: saiu %d", code)
	}
}

func TestProbeHealthRecusaPortaFechada(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	addr := srv.Listener.Addr().String()
	srv.Close() // ninguém mais escuta: é o processo morto/travado

	if code := probeHealth(addr); code != 1 {
		t.Fatalf("porta fechada deve reprovar o healthcheck: saiu %d", code)
	}
}
