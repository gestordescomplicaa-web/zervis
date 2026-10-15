package main

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const (
	backupPrefix = "wacalls-"
	backupSuffix = ".db"
)

// createSQLiteBackup uses SQLite itself instead of copying the live WAL files.
// VACUUM INTO produces a transactionally consistent snapshot while calls and
// session updates continue to use the source database.
func createSQLiteBackup(ctx context.Context, db *sql.DB, dir string, now time.Time) (string, error) {
	if db == nil {
		return "", fmt.Errorf("database is nil")
	}
	if strings.TrimSpace(dir) == "" {
		return "", fmt.Errorf("backup directory is empty")
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", fmt.Errorf("create backup directory: %w", err)
	}
	if err := os.Chmod(dir, 0o700); err != nil {
		return "", fmt.Errorf("protect backup directory: %w", err)
	}

	stamp := now.UTC().Format("20060102-150405.000000000")
	finalPath := filepath.Join(dir, backupPrefix+stamp+backupSuffix)
	partialPath := finalPath + ".partial"
	if _, err := os.Stat(finalPath); err == nil {
		return "", fmt.Errorf("backup already exists: %s", filepath.Base(finalPath))
	} else if !os.IsNotExist(err) {
		return "", fmt.Errorf("inspect backup target: %w", err)
	}
	if _, err := os.Stat(partialPath); err == nil {
		return "", fmt.Errorf("partial backup already exists: %s", filepath.Base(partialPath))
	} else if !os.IsNotExist(err) {
		return "", fmt.Errorf("inspect partial target: %w", err)
	}

	completed := false
	defer func() {
		if !completed {
			_ = os.Remove(partialPath)
		}
	}()
	if _, err := db.ExecContext(ctx, "VACUUM INTO ?", partialPath); err != nil {
		return "", fmt.Errorf("vacuum into snapshot: %w", err)
	}
	if err := verifySQLiteBackup(ctx, partialPath); err != nil {
		return "", err
	}
	if err := os.Chmod(partialPath, 0o600); err != nil {
		return "", fmt.Errorf("protect snapshot: %w", err)
	}
	file, err := os.Open(partialPath)
	if err != nil {
		return "", fmt.Errorf("open snapshot for sync: %w", err)
	}
	if err := file.Sync(); err != nil {
		_ = file.Close()
		return "", fmt.Errorf("sync snapshot: %w", err)
	}
	if err := file.Close(); err != nil {
		return "", fmt.Errorf("close snapshot: %w", err)
	}
	if err := os.Rename(partialPath, finalPath); err != nil {
		return "", fmt.Errorf("publish snapshot: %w", err)
	}
	completed = true
	return finalPath, nil
}

func verifySQLiteBackup(ctx context.Context, path string) error {
	check, err := sql.Open("sqlite", "file:"+path+"?mode=ro&_pragma=busy_timeout(5000)")
	if err != nil {
		return fmt.Errorf("open snapshot for verification: %w", err)
	}
	defer check.Close()
	check.SetMaxOpenConns(1)
	var result string
	if err := check.QueryRowContext(ctx, "PRAGMA quick_check").Scan(&result); err != nil {
		return fmt.Errorf("verify snapshot: %w", err)
	}
	if result != "ok" {
		return fmt.Errorf("verify snapshot: %s", result)
	}
	return nil
}

func pruneSQLiteBackups(dir string, keep int) error {
	if keep < 1 {
		return fmt.Errorf("backup retention must be positive")
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("read backup directory: %w", err)
	}
	var names []string
	for _, entry := range entries {
		name := entry.Name()
		if !entry.IsDir() && strings.HasPrefix(name, backupPrefix) && strings.HasSuffix(name, backupSuffix) {
			names = append(names, name)
		}
	}
	sort.Strings(names)
	for _, name := range names[:max(0, len(names)-keep)] {
		if err := os.Remove(filepath.Join(dir, name)); err != nil {
			return fmt.Errorf("remove expired snapshot %s: %w", name, err)
		}
	}
	return nil
}

func runSQLiteBackups(ctx context.Context, db *sql.DB, dir string, interval time.Duration, keep int, log *slog.Logger) {
	run := func() {
		path, err := createSQLiteBackup(ctx, db, dir, time.Now())
		if err != nil {
			if ctx.Err() == nil {
				log.Error("SQLite backup failed", "err", err)
			}
			return
		}
		if err := pruneSQLiteBackups(dir, keep); err != nil {
			log.Error("SQLite backup retention failed", "err", err)
			return
		}
		log.Info("SQLite backup completed", "file", filepath.Base(path))
	}

	run()
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			run()
		}
	}
}
