package main

import (
	"context"
	"errors"
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.mau.fi/whatsmeow/store"
	"google.golang.org/protobuf/proto"
)

// nomeDoAparelho é o que o cliente vê em "Aparelhos conectados" no celular
// dele, para sempre, depois de ler o QR.
//
// POR QUE ISTO EXISTE: o padrão da biblioteca é a string "whatsmeow"
// (store/clientpayload.go). Quem pareava via um nome de biblioteca sem
// significado nenhum — parece software estranho no aparelho, e na hora de
// desconectar a pessoa não sabe qual entrada é a nossa. Com dois números
// conectados, os dois apareciam idênticos.
//
// NÃO afeta risco de ban nem roteamento de sessão: ban é comportamento
// (volume/denúncia) e o roteamento usa o session_id da nossa tabela
// `wa_sessoes`. Isto aqui é identidade visível, só.
//
// Env em vez de constante: quem revende com marca própria troca sem recompilar.
func nomeDoAparelho() string {
	if n := os.Getenv("WA_DEVICE_NAME"); n != "" {
		return n
	}
	return "Zérvis"
}

func main() {
	// PRECISA ser a primeira coisa do main: `store.DeviceProps` é lido no
	// momento do PAREAMENTO (whatsmeow/pair.go), e `Restore()` logo abaixo já
	// constrói clientes. Definir depois disso pegaria só as sessões novas.
	store.DeviceProps.Os = proto.String(nomeDoAparelho())

	addr := flag.String("addr", ":8080", "HTTP listen address")
	dbPath := flag.String("db", "wacalls.db", "SQLite session database path")
	staticDir := flag.String("static", "", "static client directory (optional)")
	debug := flag.Bool("debug", false, "verbose logging")
	maxCalls := flag.Int("max-calls-per-session", 8, "max concurrent calls per session (0 = unlimited)")
	backupDir := flag.String("backup-dir", "", "directory for consistent SQLite snapshots (empty disables backups)")
	backupInterval := flag.Duration("backup-interval", 24*time.Hour, "interval between SQLite snapshots")
	backupKeep := flag.Int("backup-keep", 14, "number of local SQLite snapshots to retain")
	healthcheck := flag.Bool("healthcheck", false, "probe the local HTTP server and exit 0/1 (for container healthcheck)")
	flag.Parse()

	// A imagem é distroless: não há shell, wget ou curl para sondar o processo.
	// O próprio binário faz o teste — o Docker roda `wacalls -healthcheck`, que
	// consulta o servidor local e sai antes de tocar em banco ou sessões.
	if *healthcheck {
		os.Exit(probeHealth(*addr))
	}

	level := slog.LevelInfo
	if *debug {
		level = slog.LevelDebug
	}
	log := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: level}))
	slog.SetDefault(log)
	if os.Getenv("WACALLS_INTERNAL_TOKEN") == "" {
		log.Error("WACALLS_INTERNAL_TOKEN is required; refusing to expose call control without service auth")
		os.Exit(1)
	}
	if *backupDir != "" && (*backupInterval <= 0 || *backupKeep < 1) {
		log.Error("invalid backup configuration", "interval", *backupInterval, "keep", *backupKeep)
		os.Exit(1)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	srv, err := newServer(ctx, *dbPath, *staticDir, *maxCalls, log)
	if err != nil {
		log.Error("startup failed", "err", err)
		os.Exit(1)
	}
	defer srv.db.Close()
	defer srv.sessions.disconnectAll()

	if err := srv.sessions.Restore(ctx); err != nil {
		log.Error("session restore failed", "err", err)
		os.Exit(1)
	}
	if *backupDir != "" {
		go runSQLiteBackups(ctx, srv.db, *backupDir, *backupInterval, *backupKeep, log)
	}

	httpSrv := &http.Server{Addr: *addr, Handler: srv.routes()}
	go func() {
		log.Info("HTTP server listening", "addr", *addr)
		if err := httpSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("http server error", "err", err)
		}
	}()

	<-ctx.Done()
	log.Info("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = httpSrv.Shutdown(shutdownCtx)
}
