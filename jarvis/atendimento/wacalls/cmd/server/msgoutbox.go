package main

// OUTBOX DE MENSAGENS — o que o WhatsApp entregou fica guardado até o painel
// confirmar que recebeu.
//
// POR QUE NÃO USAR O BROKER: `Broker.broadcast` descarta em silêncio quando o
// assinante está lento ou ausente (o `default:` do select). Para estado de
// chamada isso é correto — o próximo evento corrige. Para mensagem é fatal: a
// que se perde some para sempre e ninguém percebe.
//
// O SQLite aqui é FILA, não arquivo. O histórico definitivo mora no Postgres do
// painel; entregue, a linha é apagada. `event_id` como chave primária dá
// deduplicação de graça, e o whatsmeow pode reentregar o mesmo evento.

import (
	"context"
	"database/sql"
	"time"
)

// Teto de idade. Uma mensagem que não entrou no painel em três dias não vai
// mais entrar — o painel foi reinstalado, o token mudou, algo assim. Sem isto,
// uma falha prolongada faria o SQLite virar o segundo banco de conversas que
// este desenho existe para evitar.
const outboxValidadeHoras = 72

// Quantas linhas cada rodada de envio carrega. Pequeno de propósito: a conexão
// do SQLite é ÚNICA (SetMaxOpenConns(1)) e é a mesma que o whatsmeow usa para
// gravar chaves de criptografia. Lote grande atrasaria a sessão de WhatsApp.
const outboxLote = 50

type outboxItem struct {
	EventID string
	Payload string
}

func criarOutbox(ctx context.Context, db *sql.DB) error {
	_, err := db.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS message_outbox (
		event_id   TEXT PRIMARY KEY,
		session_id TEXT NOT NULL,
		payload    TEXT NOT NULL,
		tentativas INTEGER NOT NULL DEFAULT 0,
		criado_em  INTEGER NOT NULL
	)`)
	if err != nil {
		return err
	}
	// A leitura da fila é sempre "os mais antigos primeiro".
	_, err = db.ExecContext(ctx,
		`CREATE INDEX IF NOT EXISTS idx_outbox_criado ON message_outbox (criado_em)`)
	return err
}

// enfileirar grava a mensagem normalizada. IGNORE em vez de REPLACE: reentrega
// do mesmo `event_id` não pode zerar o contador de tentativas nem reordenar a
// fila — seria um jeito silencioso de uma mensagem problemática nunca sair.
func enfileirar(ctx context.Context, db *sql.DB, eventID, sessionID, payload string) error {
	_, err := db.ExecContext(ctx,
		`INSERT OR IGNORE INTO message_outbox (event_id, session_id, payload, criado_em)
		 VALUES (?, ?, ?, ?)`,
		eventID, sessionID, payload, time.Now().Unix())
	return err
}

// pendentes devolve o próximo lote. Devolve os dados e SOLTA a conexão: quem
// chama vai fazer HTTP, e segurar a única conexão do banco durante uma chamada
// de rede travaria a gravação de chaves do whatsmeow junto.
func pendentes(ctx context.Context, db *sql.DB) ([]outboxItem, error) {
	rows, err := db.QueryContext(ctx,
		`SELECT event_id, payload FROM message_outbox
		  ORDER BY criado_em LIMIT ?`, outboxLote)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []outboxItem
	for rows.Next() {
		var it outboxItem
		if err := rows.Scan(&it.EventID, &it.Payload); err != nil {
			return nil, err
		}
		out = append(out, it)
	}
	return out, rows.Err()
}

// confirmar apaga o que o painel já gravou.
func confirmar(ctx context.Context, db *sql.DB, ids []string) error {
	if len(ids) == 0 {
		return nil
	}
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	st, err := tx.PrepareContext(ctx, `DELETE FROM message_outbox WHERE event_id = ?`)
	if err != nil {
		return err
	}
	defer st.Close()
	for _, id := range ids {
		if _, err := st.ExecContext(ctx, id); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// marcarTentativa registra a falha. O contador serve para diagnóstico: uma
// mensagem com muitas tentativas é sintoma de payload que o painel recusa, não
// de rede instável.
func marcarTentativa(ctx context.Context, db *sql.DB, ids []string) {
	for _, id := range ids {
		_, _ = db.ExecContext(ctx,
			`UPDATE message_outbox SET tentativas = tentativas + 1 WHERE event_id = ?`, id)
	}
}

// expurgar remove o que passou da validade. Devolve quantas saíram para o log
// poder gritar: mensagem descartada é perda de dado do cliente, não rotina.
func expurgar(ctx context.Context, db *sql.DB) int64 {
	limite := time.Now().Add(-outboxValidadeHoras * time.Hour).Unix()
	r, err := db.ExecContext(ctx,
		`DELETE FROM message_outbox WHERE criado_em < ?`, limite)
	if err != nil {
		return 0
	}
	n, _ := r.RowsAffected()
	return n
}
