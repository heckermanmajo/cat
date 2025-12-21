# Local Data Setup

Dokumentation der lokalen Datenarchitektur des Go-Clients.

## Architektur-Überblick

Das System verwendet eine **Zwei-Datenbank-Architektur** mit klarer Trennung der Verantwortlichkeiten:

| Datenbank | Datei | Zweck |
|-----------|-------|-------|
| **DuckDB** | `raw.duckdb` | Rohdaten-Layer (append-only, JSON-first) |
| **SQLite** | `app.sqlite` | App-Daten (Settings, UI-State, Logs, Lizenz) |

### Dateistruktur

```
catknows                    # Binary
catknows_data/              # Datenverzeichnis (neben dem Binary)
├── raw.duckdb              # Rohdaten (DuckDB)
└── app.sqlite              # App-Daten (SQLite)
```

Der Speicherort kann per CLI-Flag angepasst werden:
```bash
./catknows -data-dir /custom/path
```

---

## DuckDB - Rohdaten-Layer

### Zweck

- Speicherung aller gescrapten Daten von der Browser-Extension
- **Append-only**: Daten werden nie überschrieben, immer angehängt
- **Versioniert**: Jeder Fetch wird mit Zeitstempel gespeichert
- **JSON-first**: Rohdaten werden als JSON-String gespeichert

### Schema

```sql
CREATE TABLE IF NOT EXISTS raw_fetches (
    entity_type TEXT NOT NULL,      -- z.B. 'member', 'post', 'profile'
    entity_id   TEXT NOT NULL,      -- ID der Entity
    raw_json    TEXT NOT NULL,      -- Rohdaten als JSON
    source      TEXT DEFAULT 'skool',
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_fetches_entity
ON raw_fetches(entity_type, entity_id, fetched_at DESC);
```

### Entity-Typen

| Typ | Beschreibung |
|-----|-------------|
| `member` | Community-Mitglieder |
| `post` | Posts/Beiträge |
| `profile` | Nutzerprofile |
| `about_page` | About-Seite der Community |
| `community_page` | Community-Übersicht |
| `likes` | Post-Likes |

### Implementierung

**Datei:** `go-client/db/duckdb/duckdb.go`

**Wichtige Methoden:**

```go
// Einzelnen Fetch speichern
StoreFetch(entityType, entityID, rawJSON, source string) error

// Bulk-Insert (Transaction-basiert)
StoreBulkFetch(entityType, source string, items []FetchItem) error

// Neueste Version einer Entity abrufen
GetLatestFetch(entityType, entityID string) (*LatestFetch, error)

// Alle neuesten Versionen eines Typs
GetAllLatestByType(entityType string) ([]LatestFetch, error)

// Paginated Abfrage mit Filter
GetAllFetches(filter FetchFilter) ([]FetchRecord, int, error)

// Statistiken
GetFetchCount() (int, error)
GetFetchCountByType() (map[string]int, error)
GetEntityTypes() ([]string, error)
GetSources() ([]string, error)

// Direkte SQL-Abfrage
QueryRaw(query string, args ...interface{}) (*sql.Rows, error)
```

### Datentypen

```go
type FetchItem struct {
    EntityID string
    RawJSON  string
}

type LatestFetch struct {
    EntityID  string
    RawJSON   string
    FetchedAt time.Time
}

type FetchRecord struct {
    EntityType string
    EntityID   string
    RawJSON    string
    Source     string
    FetchedAt  time.Time
}

type FetchFilter struct {
    EntityType string
    Source     string
    Limit      int
    Offset     int
}
```

---

## SQLite - App-Daten-Layer

### Zweck

- Anwendungszustand und Konfiguration
- Keine Rohdaten, nur Metadaten und App-Artefakte

### Schema

**Datei:** `go-client/db/sqlite/schema.sql`

```sql
-- Key-Value Settings
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- UI-State (Tab-Auswahl, letzte Ansicht)
CREATE TABLE IF NOT EXISTS ui_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Gespeicherte Filter/Abfragen
CREATE TABLE IF NOT EXISTS saved_queries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    query_type TEXT NOT NULL,
    query_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lizenz (Single Row)
CREATE TABLE IF NOT EXISTS license (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    key        TEXT,
    status     TEXT,
    expires_at TIMESTAMP,
    checked_at TIMESTAMP
);

-- Analyse-Reports (Snapshots)
CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    report_type TEXT NOT NULL,
    data_json   TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sync-Protokoll
CREATE TABLE IF NOT EXISTS sync_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type    TEXT NOT NULL,
    entity_count INTEGER,
    status       TEXT,
    error_msg    TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Zentrales Logging
CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT NOT NULL,
    source     TEXT NOT NULL,
    message    TEXT NOT NULL,
    details    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Implementierung

**Datei:** `go-client/db/sqlite/sqlite.go`

**Settings:**
```go
GetSetting(key string) (string, error)
SetSetting(key, value string) error
GetAllSettings() (map[string]string, error)
```

**UI-State:**
```go
GetUIState(key string) (string, error)
SetUIState(key, value string) error
```

**Saved Queries:**
```go
SaveQuery(name, queryType, queryJSON string) (int64, error)
GetSavedQueries(queryType string) ([]SavedQuery, error)
DeleteSavedQuery(id int64) error
```

**Lizenz:**
```go
GetLicense() (*License, error)
SetLicense(key, status string, expiresAt time.Time) error
```

**Reports:**
```go
SaveReport(name, reportType, dataJSON string) (int64, error)
GetReports(reportType string) ([]Report, error)
```

**Sync-Log:**
```go
LogSync(syncType string, entityCount int, status, errorMsg string) error
GetRecentSyncs(limit int) ([]SyncLogEntry, error)
```

**Logging:**
```go
WriteLog(level, source, message, details string) error
LogDebug/LogInfo/LogWarn/LogError(source, message string) error
GetLogs(filter LogFilter) ([]LogEntry, int, error)
GetLogSources() ([]string, error)
ClearLogs() error
GetLogCount() (int, error)
```

### Log-Levels

```go
const (
    LogLevelDebug = "debug"
    LogLevelInfo  = "info"
    LogLevelWarn  = "warn"
    LogLevelError = "error"
)
```

---

## Storage-Fassade

**Datei:** `go-client/storage/storage.go`

Die `Storage` struct ist die zentrale Schnittstelle für alle Datenzugriffe:

```go
type Storage struct {
    Raw *duckdb.RawDB   // DuckDB für Rohdaten
    App *sqlite.AppDB   // SQLite für App-Daten
}

type Config struct {
    DataDir string  // Pfad zum Datenverzeichnis
}
```

**Initialisierung:**
```go
storage, err := storage.New(storage.Config{
    DataDir: "catknows_data",
})
defer storage.Close()
```

**Statistik-Methode:**
```go
func (s *Storage) GetStats() (*Stats, error)

type Stats struct {
    TotalFetches   int            // Gesamtzahl aller Fetches
    FetchesByType  map[string]int // Aufschlüsselung nach Entity-Typ
    EntityTypes    []string       // Liste aller Entity-Typen
    Sources        []string       // Liste aller Quellen
}
```

---

## API-Endpoints

### Daten-Sync (von Extension)

```
POST /api/sync
```

**Request:**
```json
{
    "action": "sync",
    "timestamp": 1234567890,
    "entity_type": "member",
    "source": "skool",
    "data": [
        {"entity_id": "123", "raw_json": "{...}"},
        {"entity_id": "456", "raw_json": "{...}"}
    ]
}
```

**Response:**
```json
{
    "message": "Sync completed",
    "status": "success",
    "count": 2
}
```

### Statistiken

```
GET /api/stats
```

**Response:**
```json
{
    "total_fetches": 1500,
    "fetches_by_type": {
        "member": 500,
        "post": 800,
        "profile": 200
    },
    "entity_types": ["member", "post", "profile"],
    "sources": ["skool"]
}
```

### Neueste Daten abrufen

```
GET /api/data/latest?type=member
```

**Response:**
```json
{
    "entity_type": "member",
    "count": 500,
    "data": [
        {
            "entity_id": "123",
            "raw_json": "{...}",
            "fetched_at": "2024-01-15T10:30:00Z"
        }
    ]
}
```

### Fetches durchsuchen

```
GET /api/fetches?entity_type=member&limit=20&offset=0
```

### Logs

```
GET  /api/logs?level=error&source=sync&limit=50
POST /api/logs   {"level": "info", "source": "ui", "message": "...", "details": "..."}
DELETE /api/logs
```

### Settings

```
GET  /api/settings           # Alle Settings (API-Keys maskiert)
GET  /api/setting?key=...    # Einzelnes Setting
POST /api/settings           # Setting speichern {"key": "...", "value": "..."}
```

---

## Datenfluss

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Browser         │     │ Go-Client       │     │ Frontend        │
│ Extension       │     │ (localhost)     │     │ (React)         │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  POST /api/sync       │                       │
         │ ─────────────────────>│                       │
         │                       │                       │
         │                       │  Store in DuckDB      │
         │                       │  (append-only)        │
         │                       │                       │
         │                       │  Log in SQLite        │
         │                       │  (sync_log)           │
         │                       │                       │
         │                       │<──────────────────────│
         │                       │  GET /api/data/latest │
         │                       │                       │
         │                       │  Query DuckDB         │
         │                       │  (latest per entity)  │
         │                       │                       │
         │                       │──────────────────────>│
         │                       │  JSON Response        │
```

---

## Design-Prinzipien

1. **Rohdaten bleiben roh**
   - Keine Transformation bei Speicherung
   - JSON-first für Flexibilität
   - Append-only für Vollständigkeit

2. **Der aktuelle Zustand wird abgefragt, nicht synchronisiert**
   - `GetLatestFetch()` liefert immer die neueste Version
   - Keine Synchronisations-Logik nötig

3. **Nur bewusste Artefakte werden in SQLite persistiert**
   - Settings, Reports, Logs
   - Keine abgeleiteten Daten

4. **Single Binary Distribution**
   - Beide Datenbanken werden beim Start initialisiert
   - Schema-Migration automatisch

---

## Code-Struktur

```
go-client/
├── db/
│   ├── duckdb/
│   │   ├── duckdb.go       # RawDB Implementation
│   │   └── schema.sql      # Rohdaten-Schema
│   └── sqlite/
│       ├── sqlite.go       # AppDB Implementation
│       └── schema.sql      # App-Daten-Schema
├── storage/
│   └── storage.go          # Zentrale Storage-Fassade
├── server/
│   ├── handlers.go         # HTTP-Handler mit Storage-Zugriff
│   └── router.go           # Route-Setup
├── main.go                 # Entry-Point
└── go.mod                  # Dependencies
```

---

## Abhängigkeiten

```go
// DuckDB
github.com/marcboeker/go-duckdb v1.8.5

// SQLite (Pure Go, kein CGO)
modernc.org/sqlite v1.29.6

// HTTP Router
github.com/go-chi/chi/v5 v5.0.12
```

---

## Status der Implementierung

| Komponente | Status | Notizen |
|------------|--------|---------|
| DuckDB Schema | Fertig | |
| DuckDB CRUD | Fertig | Alle Methoden implementiert |
| SQLite Schema | Fertig | |
| SQLite CRUD | Fertig | Alle Methoden implementiert |
| Storage-Fassade | Fertig | |
| API Sync | Fertig | Extension → Go-Client |
| API Stats | Fertig | |
| API Data/Latest | Fertig | |
| API Logs | Fertig | |
| API Settings | Fertig | API-Key Masking aktiv |
| Logging-Integration | Teilweise | Handlers loggen noch nicht |
