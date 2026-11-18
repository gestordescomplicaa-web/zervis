package main

// O áudio sob pedido (ADR 0103): só a referência, por pouco tempo, uma vez.

import (
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"

	"go.mau.fi/whatsmeow/proto/waE2E"
	"google.golang.org/protobuf/proto"
)

func TestAudioValeUmaVezEDentroDaValidade(t *testing.T) {
	a := novosAudios()
	agora := time.Now()
	m := &waE2E.AudioMessage{Seconds: proto.Uint32(3)}
	a.guardar("s:1", m, agora)
	if got, ok := a.pegar("s:1", agora.Add(time.Minute)); !ok || got != m {
		t.Fatal("o áudio recente devia estar guardado")
	}
	if _, ok := a.pegar("s:1", agora.Add(time.Minute)); ok {
		t.Fatal("um pedido só vale uma vez")
	}
	a.guardar("s:2", m, agora)
	if _, ok := a.pegar("s:2", agora.Add(audioValidade+time.Second)); ok {
		t.Fatal("depois da validade, nada")
	}
	a.guardar("", m, agora)
	a.guardar("s:3", nil, agora)
	if len(a.itens) != 0 {
		t.Fatal("sem id ou sem áudio, nada é guardado")
	}
}

func TestAudioGuardaSoOsMaisRecentes(t *testing.T) {
	a := novosAudios()
	agora := time.Now()
	for i := 0; i < audioGuardadosMax+5; i++ {
		a.guardar("s:"+strconv.Itoa(i), &waE2E.AudioMessage{}, agora)
	}
	if len(a.itens) != audioGuardadosMax || len(a.ordem) != audioGuardadosMax {
		t.Fatalf("devia guardar só %d, guardou %d", audioGuardadosMax, len(a.itens))
	}
}

func TestPedidoDeAudioRecusaOQueNaoExisteEOLongo(t *testing.T) {
	mgr := &SessionManager{sessions: map[string]*Session{"s": {id: "s"}}, audios: novosAudios()}
	srv := &server{sessions: mgr}
	mgr.audios.guardar("s:longo", &waE2E.AudioMessage{Seconds: proto.Uint32(audioSegundosMax + 1)}, time.Now())
	casos := map[string]int{
		"/api/sessions/s/audio?evento=s:nada":  http.StatusNotFound,
		"/api/sessions/s/audio?evento=s:longo": http.StatusRequestEntityTooLarge,
		"/api/sessions/x/audio?evento=s:longo": http.StatusNotFound,
	}
	for caminho, esperado := range casos {
		req := httptest.NewRequest(http.MethodGet, caminho, nil)
		req.SetPathValue("sid", req.URL.Path[len("/api/sessions/"):len("/api/sessions/")+1])
		rec := httptest.NewRecorder()
		srv.handleAudio(rec, req)
		if rec.Code != esperado {
			t.Fatalf("%s: esperava %d, veio %d", caminho, esperado, rec.Code)
		}
	}
}
