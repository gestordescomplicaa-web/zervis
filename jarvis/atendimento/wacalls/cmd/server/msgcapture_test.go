package main

// A captura é PASSIVA e seletiva. Estes testes prendem as decisões que, se
// mudarem sem querer, ou vazam dado que não devia ser guardado, ou perdem
// mensagem do cliente em silêncio.

import (
	"context"
	"database/sql"
	"testing"
	"time"

	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	"google.golang.org/protobuf/proto"
)

func msgDe(chat, sender types.JID, id string, fromMe bool, grupo bool) *events.Message {
	return &events.Message{
		Info: types.MessageInfo{
			ID:        id,
			Timestamp: time.Now(),
			MessageSource: types.MessageSource{
				Chat: chat, Sender: sender, IsFromMe: fromMe, IsGroup: grupo,
			},
		},
	}
}

func jidPN(u string) types.JID  { return types.JID{User: u, Server: types.DefaultUserServer} }
func jidLID(u string) types.JID { return types.JID{User: u, Server: types.HiddenUserServer} }

// ---------- o que NÃO entra ----------

func TestGrupoNaoEhCapturado(t *testing.T) {
	// A memória do agente é por CONTATO. Mensagem de grupo é de muita gente ao
	// mesmo tempo: misturar faria o agente atribuir a uma pessoa o que outra
	// escreveu — pior do que não ter histórico nenhum.
	evt := msgDe(jidPN("5581999@g.us"), jidPN("558199"), "A1", false, true)
	if _, ok := deveCapturar(evt); ok {
		t.Fatal("grupo não pode ser capturado")
	}
}

func TestNewsletterEStatusFicamDeFora(t *testing.T) {
	for _, srv := range []string{types.NewsletterServer, types.BroadcastServer} {
		evt := msgDe(types.JID{User: "x", Server: srv}, jidPN("558199"), "A2", false, false)
		if _, ok := deveCapturar(evt); ok {
			t.Fatalf("%s é difusão, não conversa", srv)
		}
	}
}

func TestSemIDNaoEntra(t *testing.T) {
	// Sem `event_id` não há como deduplicar, e o whatsmeow reentrega.
	evt := msgDe(jidPN("558199"), jidPN("558199"), "", false, false)
	if _, ok := deveCapturar(evt); ok {
		t.Fatal("mensagem sem id não pode entrar na fila")
	}
}

// ---------- texto: só texto puro ----------

func TestTextoSimplesEExtendido(t *testing.T) {
	evt := msgDe(jidPN("558199"), jidPN("558199"), "A3", false, false)
	evt.Message = &waE2E.Message{Conversation: proto.String(" oi, tudo bem? ")}
	if txt, ok := textoDaMensagem(evt); !ok || txt != "oi, tudo bem?" {
		t.Fatalf("texto simples: %q %v", txt, ok)
	}
	// Texto com contexto (resposta, link com prévia) continua sendo texto.
	evt.Message = &waE2E.Message{ExtendedTextMessage: &waE2E.ExtendedTextMessage{
		Text: proto.String("segue o link"),
	}}
	if txt, ok := textoDaMensagem(evt); !ok || txt != "segue o link" {
		t.Fatalf("texto estendido: %q %v", txt, ok)
	}
}

func TestMidiaNaoVemComoTexto(t *testing.T) {
	// Decisão de 13/08/2026: só texto puro, nunca o arquivo.
	evt := msgDe(jidPN("558199"), jidPN("558199"), "A4", false, false)
	evt.Message = &waE2E.Message{AudioMessage: &waE2E.AudioMessage{}}
	if txt, ok := textoDaMensagem(evt); ok || txt != "" {
		t.Fatalf("áudio não pode virar texto: %q %v", txt, ok)
	}
}

// ---------- identidade: as duas grafias da mesma pessoa ----------

func TestIdentidadeUsaOParDoProprioEvento(t *testing.T) {
	// O evento já traz a forma alternativa; aproveitá-la evita consultar o mapa
	// de LIDs, cuja ausência já custou uma ligação muda de 15s.
	evt := msgDe(jidPN("558199990000"), jidLID("100000000000001"), "A5", false, false)
	evt.Info.SenderAlt = jidPN("558199990000")
	tel, lid := identidades(evt)
	if tel != "558199990000" || lid != "100000000000001" {
		t.Fatalf("esperava as duas formas, veio tel=%q lid=%q", tel, lid)
	}
}

func TestNaMinhaMensagemOContatoEhOOutroLado(t *testing.T) {
	// Em `IsFromMe`, `Sender` sou eu — quem identifica o contato é o chat.
	evt := msgDe(jidPN("558199990000"), jidPN("558199991003"), "A6", true, false)
	evt.Info.RecipientAlt = jidLID("999888777")
	tel, lid := identidades(evt)
	if tel != "558199990000" {
		t.Fatalf("devia usar o chat como contato, veio %q", tel)
	}
	if lid != "999888777" {
		t.Fatalf("devia pegar o LID do destinatário, veio %q", lid)
	}
}

func TestEventIDEhEscopadoPelaSessao(t *testing.T) {
	// Dois numeros pareados podem receber o mesmo id opaco. A deduplicacao nao
	// pode fazer uma empresa apagar a mensagem da outra.
	a := idEventoEscopado("sessao-a", "MESMO")
	b := idEventoEscopado("sessao-b", "MESMO")
	if a == b || a != "sessao-a:MESMO" {
		t.Fatalf("ids sem isolamento por sessao: a=%q b=%q", a, b)
	}
}

// ---------- a fila não perde e não duplica ----------

func abrirDBTeste(t *testing.T) *sql.DB {
	t.Helper()
	db, err := openDB(t.TempDir() + "/t.db")
	if err != nil {
		t.Fatal(err)
	}
	if err := criarOutbox(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	return db
}

func TestReentregaNaoDuplicaNemReordena(t *testing.T) {
	// O whatsmeow pode reentregar o mesmo evento. INSERT OR IGNORE (e não
	// REPLACE) impede que isso zere o contador de tentativas e reordene a fila,
	// que seria um jeito silencioso de uma mensagem nunca sair.
	ctx, db := context.Background(), abrirDBTeste(t)
	defer db.Close()
	for i := 0; i < 3; i++ {
		if err := enfileirar(ctx, db, "MESMO", "s1", `{"a":1}`); err != nil {
			t.Fatal(err)
		}
	}
	marcarTentativa(ctx, db, []string{"MESMO"})
	_ = enfileirar(ctx, db, "MESMO", "s1", `{"a":1}`)
	var n, tentativas int
	db.QueryRow(`SELECT COUNT(*), MAX(tentativas) FROM message_outbox`).Scan(&n, &tentativas)
	if n != 1 {
		t.Fatalf("esperava 1 linha, veio %d", n)
	}
	if tentativas != 1 {
		t.Fatalf("reentrega zerou o contador (tentativas=%d)", tentativas)
	}
}

func TestSoApagaOQueFoiConfirmado(t *testing.T) {
	ctx, db := context.Background(), abrirDBTeste(t)
	defer db.Close()
	_ = enfileirar(ctx, db, "E1", "s1", `{}`)
	_ = enfileirar(ctx, db, "E2", "s1", `{}`)
	if err := confirmar(ctx, db, []string{"E1"}); err != nil {
		t.Fatal(err)
	}
	itens, _ := pendentes(ctx, db)
	if len(itens) != 1 || itens[0].EventID != "E2" {
		t.Fatalf("o não confirmado tem que ficar na fila: %+v", itens)
	}
}

func TestExpurgoSoLevaOQuePassouDaValidade(t *testing.T) {
	ctx, db := context.Background(), abrirDBTeste(t)
	defer db.Close()
	_ = enfileirar(ctx, db, "NOVA", "s1", `{}`)
	antiga := time.Now().Add(-(outboxValidadeHoras + 1) * time.Hour).Unix()
	db.Exec(`INSERT INTO message_outbox (event_id, session_id, payload, criado_em)
	         VALUES ('VELHA','s1','{}',?)`, antiga)
	if n := expurgar(ctx, db); n != 1 {
		t.Fatalf("esperava expurgar só a antiga, saíram %d", n)
	}
	itens, _ := pendentes(ctx, db)
	if len(itens) != 1 || itens[0].EventID != "NOVA" {
		t.Fatalf("a recente tinha que ficar: %+v", itens)
	}
}

func TestFilaSaiNaOrdemDeChegada(t *testing.T) {
	ctx, db := context.Background(), abrirDBTeste(t)
	defer db.Close()
	db.Exec(`INSERT INTO message_outbox (event_id, session_id, payload, criado_em)
	         VALUES ('B','s1','{}',200), ('A','s1','{}',100)`)
	itens, _ := pendentes(ctx, db)
	if len(itens) != 2 || itens[0].EventID != "A" {
		t.Fatalf("a mais antiga sai primeiro: %+v", itens)
	}
}

func TestSoConversaPrivadaPassa(t *testing.T) {
	contato := types.NewJID("5581999990000", types.DefaultUserServer)
	// Um grupo que não veio marcado como grupo continua de fora pelo servidor do chat.
	grupo := types.NewJID("120363000000000000", types.GroupServer)
	if _, ok := deveCapturar(msgDe(grupo, contato, "G1", false, false)); ok {
		t.Fatal("chat de grupo não pode passar mesmo sem IsGroup")
	}
	if _, ok := deveCapturar(msgDe(contato, contato, "P1", false, false)); !ok {
		t.Fatal("conversa privada precisa passar")
	}
	lid := types.NewJID("123456789", types.HiddenUserServer)
	if _, ok := deveCapturar(msgDe(lid, lid, "L1", false, false)); !ok {
		t.Fatal("conversa privada por LID precisa passar")
	}
}
