package storage

import (
	"fmt"
	"os"
	"path/filepath"

	"school-local-backend/db/duckdb"
	"school-local-backend/db/sqlite"
)

// Storage ist die zentrale Fassade für alle Datenbankzugriffe
// - Raw: DuckDB für Rohdaten (Fetches von der Extension)
// - App: SQLite für Anwendungsdaten (Settings, UI-State, Reports)
type Storage struct {
	Raw *duckdb.RawDB
	App *sqlite.AppDB
}

// Config enthält die Konfiguration für die Storage-Initialisierung
type Config struct {
	DataDir string // Verzeichnis für alle Datenbankdateien
}

// DefaultConfig gibt die Standard-Konfiguration zurück
func DefaultConfig() Config {
	return Config{
		DataDir: ".", // Aktuelles Verzeichnis
	}
}

// New erstellt eine neue Storage-Instanz mit beiden Datenbanken
func New(cfg Config) (*Storage, error) {
	// Datenverzeichnis erstellen falls nötig
	if cfg.DataDir != "." {
		if err := os.MkdirAll(cfg.DataDir, 0755); err != nil {
			return nil, fmt.Errorf("failed to create data dir: %w", err)
		}
	}

	// DuckDB für Rohdaten
	rawPath := filepath.Join(cfg.DataDir, "raw.duckdb")
	rawDB, err := duckdb.Connect(rawPath)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to DuckDB: %w", err)
	}

	// SQLite für App-Daten
	appPath := filepath.Join(cfg.DataDir, "app.sqlite")
	appDB, err := sqlite.Connect(appPath)
	if err != nil {
		rawDB.Close()
		return nil, fmt.Errorf("failed to connect to SQLite: %w", err)
	}

	return &Storage{
		Raw: rawDB,
		App: appDB,
	}, nil
}

// Close schließt beide Datenbankverbindungen
func (s *Storage) Close() error {
	var errs []error
	if err := s.Raw.Close(); err != nil {
		errs = append(errs, fmt.Errorf("raw db close: %w", err))
	}
	if err := s.App.Close(); err != nil {
		errs = append(errs, fmt.Errorf("app db close: %w", err))
	}
	if len(errs) > 0 {
		return fmt.Errorf("storage close errors: %v", errs)
	}
	return nil
}

// Stats gibt Statistiken über die gespeicherten Daten zurück
type Stats struct {
	RawFetchCount   int64
	FetchesByType   map[string]int64
	RecentSyncCount int
}

func (s *Storage) GetStats() (*Stats, error) {
	stats := &Stats{}

	// Rohdaten-Statistiken
	count, err := s.Raw.GetFetchCount()
	if err != nil {
		return nil, err
	}
	stats.RawFetchCount = count

	byType, err := s.Raw.GetFetchCountByType()
	if err != nil {
		return nil, err
	}
	stats.FetchesByType = byType

	// Sync-Log
	syncs, err := s.App.GetRecentSyncs(10)
	if err != nil {
		return nil, err
	}
	stats.RecentSyncCount = len(syncs)

	return stats, nil
}
