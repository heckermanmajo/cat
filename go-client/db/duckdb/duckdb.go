package duckdb

import (
	"database/sql"
	_ "embed"
	"fmt"
	"os"
	"time"

	_ "github.com/marcboeker/go-duckdb"
)

//go:embed schema.sql
var schema string

type RawDB struct {
	db *sql.DB
}

func Connect(dbPath string) (*RawDB, error) {
	db, err := sql.Open("duckdb", dbPath)
	if err != nil {
		return nil, fmt.Errorf("duckdb open error: %w", err)
	}

	if _, err := db.Exec(schema); err != nil {
		return nil, fmt.Errorf("duckdb schema error: %w", err)
	}

	return &RawDB{db: db}, nil
}

func (r *RawDB) Close() error {
	return r.db.Close()
}

// StoreFetch speichert einen Rohdaten-Fetch (append-only)
func (r *RawDB) StoreFetch(entityType, entityID, rawJSON, source string) error {
	_, err := r.db.Exec(`
		INSERT INTO raw_fetches (entity_type, entity_id, raw_json, source)
		VALUES (?, ?, ?, ?)
	`, entityType, entityID, rawJSON, source)
	return err
}

// StoreBulkFetch speichert mehrere Fetches auf einmal
func (r *RawDB) StoreBulkFetch(entityType, source string, items []FetchItem) error {
	tx, err := r.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	stmt, err := tx.Prepare(`
		INSERT INTO raw_fetches (entity_type, entity_id, raw_json, source)
		VALUES (?, ?, ?, ?)
	`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, item := range items {
		if _, err := stmt.Exec(entityType, item.EntityID, item.RawJSON, source); err != nil {
			return err
		}
	}

	return tx.Commit()
}

type FetchItem struct {
	EntityID string
	RawJSON  string
}

// GetLatestFetch holt den neuesten Fetch für eine Entität
func (r *RawDB) GetLatestFetch(entityType, entityID string) (string, time.Time, error) {
	var rawJSON string
	var fetchedAt time.Time
	err := r.db.QueryRow(`
		SELECT raw_json, fetched_at
		FROM raw_fetches
		WHERE entity_type = ? AND entity_id = ?
		ORDER BY fetched_at DESC
		LIMIT 1
	`, entityType, entityID).Scan(&rawJSON, &fetchedAt)
	if err != nil {
		return "", time.Time{}, err
	}
	return rawJSON, fetchedAt, nil
}

// GetAllLatestByType holt den neuesten Stand aller Entitäten eines Typs
func (r *RawDB) GetAllLatestByType(entityType string) ([]LatestFetch, error) {
	rows, err := r.db.Query(`
		WITH latest AS (
			SELECT entity_id, MAX(fetched_at) as max_fetched_at
			FROM raw_fetches
			WHERE entity_type = ?
			GROUP BY entity_id
		)
		SELECT r.entity_id, r.raw_json, r.fetched_at
		FROM raw_fetches r
		INNER JOIN latest l ON r.entity_id = l.entity_id AND r.fetched_at = l.max_fetched_at
		WHERE r.entity_type = ?
	`, entityType, entityType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []LatestFetch
	for rows.Next() {
		var f LatestFetch
		if err := rows.Scan(&f.EntityID, &f.RawJSON, &f.FetchedAt); err != nil {
			return nil, err
		}
		results = append(results, f)
	}
	return results, rows.Err()
}

type LatestFetch struct {
	EntityID  string
	RawJSON   string
	FetchedAt time.Time
}

// GetFetchCount gibt die Anzahl der gespeicherten Fetches zurück
func (r *RawDB) GetFetchCount() (int64, error) {
	var count int64
	err := r.db.QueryRow("SELECT COUNT(*) FROM raw_fetches").Scan(&count)
	return count, err
}

// GetFetchCountByType gibt die Anzahl pro Entity-Typ zurück
func (r *RawDB) GetFetchCountByType() (map[string]int64, error) {
	rows, err := r.db.Query(`
		SELECT entity_type, COUNT(*)
		FROM raw_fetches
		GROUP BY entity_type
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[string]int64)
	for rows.Next() {
		var entityType string
		var count int64
		if err := rows.Scan(&entityType, &count); err != nil {
			return nil, err
		}
		result[entityType] = count
	}
	return result, rows.Err()
}

// QueryRaw führt eine beliebige SELECT-Query auf den Rohdaten aus
func (r *RawDB) QueryRaw(query string, args ...interface{}) (*sql.Rows, error) {
	return r.db.Query(query, args...)
}

// FetchRecord repräsentiert einen einzelnen Fetch-Eintrag
type FetchRecord struct {
	EntityType string
	EntityID   string
	RawJSON    string
	Source     string
	FetchedAt  time.Time
}

// FetchFilter enthält Filter-Optionen für GetAllFetches
type FetchFilter struct {
	EntityType string
	Source     string
	Limit      int
	Offset     int
}

// GetAllFetches holt alle Fetches mit Filtern und Pagination
func (r *RawDB) GetAllFetches(filter FetchFilter) ([]FetchRecord, int64, error) {
	// Basis-Query
	query := "SELECT entity_type, entity_id, raw_json, source, fetched_at FROM raw_fetches WHERE 1=1"
	countQuery := "SELECT COUNT(*) FROM raw_fetches WHERE 1=1"
	args := []interface{}{}

	if filter.EntityType != "" {
		query += " AND entity_type = ?"
		countQuery += " AND entity_type = ?"
		args = append(args, filter.EntityType)
	}
	if filter.Source != "" {
		query += " AND source = ?"
		countQuery += " AND source = ?"
		args = append(args, filter.Source)
	}

	// Total Count
	var total int64
	countArgs := make([]interface{}, len(args))
	copy(countArgs, args)
	if err := r.db.QueryRow(countQuery, countArgs...).Scan(&total); err != nil {
		return nil, 0, err
	}

	// Order und Limit
	query += " ORDER BY fetched_at DESC"
	if filter.Limit > 0 {
		query += " LIMIT ?"
		args = append(args, filter.Limit)
	}
	if filter.Offset > 0 {
		query += " OFFSET ?"
		args = append(args, filter.Offset)
	}

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var results []FetchRecord
	for rows.Next() {
		var f FetchRecord
		if err := rows.Scan(&f.EntityType, &f.EntityID, &f.RawJSON, &f.Source, &f.FetchedAt); err != nil {
			return nil, 0, err
		}
		results = append(results, f)
	}
	return results, total, rows.Err()
}

// GetEntityTypes gibt alle vorhandenen Entity-Typen zurück
func (r *RawDB) GetEntityTypes() ([]string, error) {
	rows, err := r.db.Query("SELECT DISTINCT entity_type FROM raw_fetches ORDER BY entity_type")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var types []string
	for rows.Next() {
		var t string
		if err := rows.Scan(&t); err != nil {
			return nil, err
		}
		types = append(types, t)
	}
	return types, rows.Err()
}

// GetSources gibt alle vorhandenen Sources zurück
func (r *RawDB) GetSources() ([]string, error) {
	rows, err := r.db.Query("SELECT DISTINCT source FROM raw_fetches ORDER BY source")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var sources []string
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			return nil, err
		}
		sources = append(sources, s)
	}
	return sources, rows.Err()
}

// EnsureDataDir stellt sicher, dass das Verzeichnis für die DB existiert
func EnsureDataDir(path string) error {
	dir := path[:len(path)-len("/raw.duckdb")]
	if dir != "" {
		return os.MkdirAll(dir, 0755)
	}
	return nil
}
