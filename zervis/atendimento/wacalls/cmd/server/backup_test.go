package main

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestCreateSQLiteBackupProducesConsistentSnapshot(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "source.db")
	db, err := openDB(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if _, err := db.Exec("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT); INSERT INTO records(value) VALUES ('before')"); err != nil {
		t.Fatal(err)
	}

	backupDir := filepath.Join(t.TempDir(), "snapshots")
	path, err := createSQLiteBackup(context.Background(), db, backupDir, time.Date(2026, 8, 7, 4, 30, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("INSERT INTO records(value) VALUES ('after')"); err != nil {
		t.Fatal(err)
	}

	snapshot, err := sql.Open("sqlite", "file:"+path+"?mode=ro")
	if err != nil {
		t.Fatal(err)
	}
	defer snapshot.Close()
	var count int
	if err := snapshot.QueryRow("SELECT COUNT(*) FROM records").Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("snapshot changed after source write: got %d records", count)
	}
	if mode := os.FileMode(0o777) & fileMode(t, path); mode != 0o600 {
		t.Fatalf("snapshot permissions = %o, want 600", mode)
	}
}

func TestPruneSQLiteBackupsKeepsNewestAndIgnoresOtherFiles(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{
		"wacalls-20260801-000000.000000000.db",
		"wacalls-20260802-000000.000000000.db",
		"wacalls-20260803-000000.000000000.db",
		"unrelated.txt",
	} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if err := pruneSQLiteBackups(dir, 2); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "wacalls-20260801-000000.000000000.db")); !os.IsNotExist(err) {
		t.Fatalf("oldest snapshot was not removed: %v", err)
	}
	for _, name := range []string{
		"wacalls-20260802-000000.000000000.db",
		"wacalls-20260803-000000.000000000.db",
		"unrelated.txt",
	} {
		if _, err := os.Stat(filepath.Join(dir, name)); err != nil {
			t.Fatalf("expected %s to remain: %v", name, err)
		}
	}
}

func fileMode(t *testing.T, path string) os.FileMode {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	return info.Mode()
}
