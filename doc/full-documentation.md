# CatKnows - Vollständige Projektdokumentation

> Diese Datei fasst alle Dokumentationen zusammen, um einen vollständigen Überblick über das Projekt zu geben.

---

# Teil 1: Projektübersicht

Lokale Software-Architektur mit Browser-Extension für Skool.com-Datenanalyse.

**Zielgruppe**: Coding-Agents und Entwickler, die schnell verstehen sollen, was das System ist und wie es aufgebaut ist.

---

## Ziel des Systems

Dieses Projekt ist eine **lokal installierbare Software**, die:

* **beim Kunden lokal läuft**
* **nur Nutzerdaten des Kunden verarbeitet**
* **keine sensiblen Daten an unsere Server sendet**
* **über einen Lizenzschlüssel aktiviert wird**
* **analytische und AI-gestützte Auswertungen lokal durchführt**

Der zentrale Gedanke:
**Der Nutzer scrapt seine eigenen Daten selbst – wir stellen nur das Werkzeug.**

---

## High-Level-Architektur

Das System besteht aus **fünf Hauptkomponenten**:

| Komponente | Pfad | Technologie | Status |
|------------|------|-------------|--------|
| Browser Extension | `browser-extension/` | Manifest V3, JS | Implementiert |
| Go-Client | `go-client/` | Go, Chi Router | Implementiert |
| Frontend-UI | `frontend-client-ui/` | React, TypeScript, Vite | Implementiert |
| Web-Server | `webserver/` | PHP | Teilweise implementiert |
| Old Codebase | `old_codebase/` | Vanilla JS, PHP | Nur Referenz |

---

## 1. Browser Extension

**Pfad:** `browser-extension/`

**Version:** 0.1.0 (Manifest V3)

**Struktur:**
```
browser-extension/
├── src/
│   ├── manifest/manifest.json   # Extension-Manifest
│   ├── background/index.js      # Background Service Worker
│   ├── content/index.js         # Content Script (Auto-Fetch)
│   └── popup/                   # Extension Popup UI
│       ├── popup.html
│       ├── popup.js
│       └── popup.css
└── dist/                        # Build-Output
```

**Funktionen:**
- **Content Script**: Auto-Fetch beim Besuch von Skool.com-Seiten
- **Background Worker**: Routing der Requests zum lokalen Go-Client
- **Popup UI**: Queue-Generierung, Ausführung mit Progress-Tracking, Cache-Management

**Host Permissions:**
- `https://*.skool.com/*`
- `http://localhost:3000/*`

---

## 2. Go-Client (Lokale Kernsoftware)

**Pfad:** `go-client/`

Das **Herzstück der Anwendung** - eine einzige ausführbare Datei.

### CLI-Flags

```bash
./catknows [flags]

Flags:
  -port int          Server port (default 3000)
  -no-browser        Don't open browser automatically
  -data-dir string   Directory for database files (default: catknows_data next to binary)
```

### Code-Struktur

```
go-client/
├── main.go              # Entry-Point, CLI-Flags, Server-Start
├── embedded.go          # Static File Embedding (go:embed)
├── db/
│   ├── duckdb/          # Rohdaten-Layer
│   │   └── duckdb.go    # RawDB Implementation
│   └── sqlite/          # App-Daten-Layer
│       └── sqlite.go    # AppDB Implementation
├── storage/
│   └── storage.go       # Zentrale Storage-Fassade
├── server/
│   ├── router.go        # Chi Router Setup, SPA Handler
│   └── handlers.go      # Alle HTTP-Handler
├── fetchqueue/
│   └── queue.go         # Fetch-Queue-Builder
├── ai/
│   ├── ai.go            # OpenAI-kompatible API Client
│   └── ai_test.go       # AI Integration Tests
├── license/
│   └── license.go       # Lizenz-Manager (Ed25519 Signaturprüfung)
└── static/              # Frontend-Assets (kopiert von frontend-client-ui/dist)
```

### Datenhaltung (Zwei-Datenbank-Architektur)

| Datenbank | Datei | Zweck |
|-----------|-------|-------|
| **DuckDB** | `raw.duckdb` | Rohdaten-Layer (append-only, JSON-first, versioniert) |
| **SQLite** | `app.sqlite` | App-Daten (Settings, UI-State, Logs, Lizenz, Reports, Sync-Log) |

**Dateistruktur:**
```
catknows                    # Binary
catknows_data/              # Datenverzeichnis
├── raw.duckdb              # Rohdaten (DuckDB)
└── app.sqlite              # App-Daten (SQLite)
```

### API-Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/hello` | GET | Health-Check |
| `/api/ping` | POST | Echo-Test |
| `/api/sync` | POST | Daten von Extension speichern (-> DuckDB) |
| `/api/stats` | GET | Rohdaten-Statistiken |
| `/api/data/latest` | GET | Neueste Daten pro Entity-Typ |
| `/api/fetches` | GET | Alle Fetches durchsuchen (Filter, Pagination) |
| `/api/fetch-queue` | GET/POST | Fetch-Queue generieren |
| `/api/fetch-queue/next` | GET | Nächsten Task aus Queue holen |
| `/api/logs` | GET/POST/DELETE | Logs abrufen, schreiben, löschen |
| `/api/settings` | GET/POST | Alle Settings lesen/schreiben |
| `/api/setting` | GET | Einzelnes Setting lesen |

### Fetch-Queue-System

**Pfad:** `go-client/fetchqueue/queue.go`

Der QueueBuilder generiert dynamisch FetchTasks basierend auf dem aktuellen Datenstand in DuckDB.

**Fetch-Typen:**
| Typ | Priorität | Beschreibung |
|-----|-----------|--------------|
| `about_page` | HIGH/MEDIUM | Community About-Seite |
| `members` | HIGH/MEDIUM | Members-Listen (paginiert) |
| `community_page` | HIGH/MEDIUM | Posts-Übersicht |
| `profile` | LOW | Einzelne Member-Profile |
| `post_details` | MEDIUM/LOW | Post-Details |
| `likes` | LOW | Post-Likes |

**Queue-Generierung:**
1. Für jede konfigurierte Community werden alle Entity-Typen geprüft
2. Fehlende oder veraltete (>24h) Daten werden als Tasks hinzugefügt
3. Tasks werden nach Priorität sortiert (1=HIGH, 2=MEDIUM, 3=LOW)

### AI-Integration

**Pfad:** `go-client/ai/ai.go`

OpenAI-kompatibler Client für lokale AI-Analysen.

```go
client := ai.NewClient(ai.Config{
    APIKey:  "sk-...",        // oder aus OPENAI_API_KEY env
    Model:   "gpt-4o-mini",   // Standard-Modell
    Timeout: 30 * time.Second,
})

response, err := client.SimpleChat(ctx, "Analysiere diese Daten...")
```

---

## 3. Frontend-UI (React)

**Pfad:** `frontend-client-ui/`

**Technologie:** React + TypeScript + Vite

### Struktur

```
frontend-client-ui/
├── src/
│   ├── main.tsx              # Entry-Point
│   ├── App.tsx               # Haupt-App mit Tab-Navigation
│   ├── App.css               # Globale Styles
│   ├── contexts/
│   │   └── ThemeContext.tsx  # Dark/Light Theme
│   └── components/
│       ├── FetchQueueView.tsx/.css   # Queue-Generierung & Statistiken
│       ├── FetchesView.tsx/.css      # Rohdaten-Inspektion
│       ├── LoggingView.tsx/.css      # Log-Anzeige & Filterung
│       ├── SettingsView.tsx/.css     # API-Keys & Community-IDs
│       └── ThemeSelector.tsx/.css    # Theme-Umschalter
└── dist/                     # Build-Output (-> go-client/static/)
```

### Tabs

| Tab | Komponente | Funktion |
|-----|------------|----------|
| Dashboard | (Platzhalter) | Übersicht (noch nicht implementiert) |
| Fetch Queue | `FetchQueueView` | Queue generieren, Task-Statistiken anzeigen |
| Fetches | `FetchesView` | Rohdaten durchsuchen, JSON inspizieren |
| Logs | `LoggingView` | Logs filtern, Details anzeigen, löschen |
| Settings | `SettingsView` | Community-IDs, OpenAI API-Key konfigurieren |

---

## 4. Web-Server (Zentral)

**Pfad:** `webserver/`

Infrastruktur-Service für Lizenz und Downloads.

```
webserver/
├── index.php                # Landing-Page mit Auto-Plattform-Erkennung
├── setup.sql                # Datenbank-Schema (Lizenzen, Aktivierungen)
├── api/
│   ├── download.php         # Binary-Download API
│   └── license/
│       └── validate.php     # Lizenz-Validierung (Ed25519 Signatur)
├── config/
│   ├── database.php         # DB-Verbindung
│   └── keys.php             # Private/Public Keys
├── scripts/
│   ├── generate-keys.php    # Ed25519 Schlüsselpaar generieren
│   └── create-license.php   # Neue Lizenz erstellen
└── downloads/               # Binaries pro Plattform
    ├── catknows-macos-arm64
    ├── catknows-macos-amd64
    ├── catknows-windows-amd64.exe
    └── catknows-linux-amd64
```

### Lizenz-Mechanismus

Ed25519-Signatur-basiert mit Nonce und Timestamp für Replay-Schutz.

---

## 5. Old Codebase (Legacy/Referenz)

**Pfad:** `old_codebase/`

Alte Web-Service-Architektur (Vanilla JS + PHP). Wird **nicht weiterentwickelt**, dient nur als Referenz für Features und fachliche Logik.

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
         │                       │  Log in SQLite        │
         │                       │                       │
         │                       │<──────────────────────│
         │                       │  GET /api/data/latest │
         │                       │                       │
         │                       │  Query DuckDB         │
         │                       │──────────────────────>│
         │                       │  JSON Response        │
```

---

## Development

### Build & Run

```bash
# Vollständiges Dev-Build (empfohlen)
./scripts/build_dev.sh

# Das Script:
# 1. Baut Frontend (npm run build)
# 2. Kopiert Assets nach go-client/static/
# 3. Baut Go-Binary
# 4. Stoppt bestehenden Server auf Port 3000
# 5. Startet neuen Server
# 6. Öffnet Browser mit http://localhost:3000
```

### Weitere Scripts

| Script | Beschreibung |
|--------|--------------|
| `scripts/build_dev.sh` | Vollständiges Dev-Build |
| `scripts/build-all.sh` | Cross-Compile für alle Plattformen |

### Testing

**Pragmatischer Demo-Driven-Ansatz** statt klassischer Unit-Tests.

- **Frontend**: Eingebaute Test-UIs (Fetch Queue, Fetches, Logs, Settings)
- **Extension**: Popup als funktionales Test-Harness
- **Go**: API-Endpoints für manuelle Tests + Go-Tests für AI-Integration

```bash
# AI-Tests (benötigen OPENAI_API_KEY)
cd go-client
OPENAI_API_KEY="sk-..." go test -v ./ai/...

# Curl-Tests
curl http://localhost:3000/api/hello
curl http://localhost:3000/api/stats
curl "http://localhost:3000/api/fetch-queue?communityIds=test-community"
```

---

## Implementierungsstatus

| Komponente | Status |
|------------|--------|
| DuckDB Rohdaten-Layer | Fertig |
| SQLite App-Daten-Layer | Fertig |
| Storage-Fassade | Fertig |
| API Sync/Stats/Data | Fertig |
| API Logs/Settings | Fertig |
| Fetch-Queue-Builder | Fertig |
| Frontend (4 Views) | Fertig |
| Browser Extension | Fertig |
| AI-Integration | Fertig |
| Lizenz-Validierung | Fertig |
| Download-API | Fertig |
| Update-Prüfung im Client | Fehlt |
| Dashboard-View | Fehlt |

---

## Zentrale Design-Prinzipien

* **Privacy by Design** - Alle Nutzerdaten bleiben lokal
* **User-Initiated Scraping** - Kein Server-Scraping
* **Single Binary Delivery** - Eine Datei, alles enthalten
* **Klare Trennung** - Extension=Fetch, Go-Client=Logik, Frontend=UI, Web-Server=Lizenz
* **Offline-fähig** - Analysen ohne Internet, Internet nur für Lizenz & AI

---

---

# Teil 2: Local Data Setup

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

## API-Endpoints (Daten)

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

## Datenfluss (Detail)

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

## Design-Prinzipien (Daten)

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

## Code-Struktur (Daten)

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

## Status der Implementierung (Daten)

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

---

---

# Teil 3: Fetch-Prozess & Fetch-Queue

Dieses Kapitel beschreibt, wie der Fetch-Prozess funktioniert und wie die Fetch-Queue generiert wird.

---

## Übersicht: Datenfluss

```
Browser Extension (auf Skool.com)
    │
    ▼ (holt Daten über User-Session)
    │
    ▼ Background Script → POST /api/sync
    │
Go-Client (localhost:3000)
    │
    ▼ (speichert in DuckDB)
    │
Queue Builder (analysiert bestehende Daten)
    │
    ▼ (generiert Tasks)
    │
Fetch-Queue
    │
    ▼ (wird im Extension-Popup ausgeführt)
    │
Browser Extension führt Tasks aus
    │
    ▼ (Ergebnisse → /api/sync)
    │
Zurück zu Go-Client
```

---

## Beteiligte Komponenten

| Komponente | Pfad | Aufgabe |
|------------|------|---------|
| Queue Builder | `go-client/fetchqueue/queue.go` | Generiert die Queue basierend auf Datenstand |
| Content Script | `browser-extension/src/content/index.js` | Auto-Fetch beim Seitenbesuch |
| Background Worker | `browser-extension/src/background/index.js` | Routing der Requests zum Go-Client |
| Extension Popup | `browser-extension/src/popup/popup.js` | Queue-Ausführung und UI |
| API Handler | `go-client/server/handlers.go` | Endpunkte für Sync und Queue |
| Frontend Queue View | `frontend-client-ui/src/components/FetchQueueView.tsx` | Queue-Generierung und Anzeige |

---

## 1. Fetch-Queue-Generierung

### Was ist die Fetch-Queue?

Die Fetch-Queue ist eine dynamisch generierte Liste von **FetchTasks**, die basierend auf dem aktuellen Datenstand berechnet wird. Sie bestimmt, welche Daten als nächstes geholt werden sollen.

### Struktur eines FetchTask

```go
type FetchTask struct {
    ID            string    // Eindeutige Task-ID
    Type          string    // Art: about_page, profile, members, community_page, post_details, likes
    Priority      int       // 1=Hoch, 2=Mittel, 3=Niedrig
    CommunityID   string    // Ziel-Community
    EntityID      string    // Optional: Member-ID oder Post-ID
    Page          int       // Optional: Seitennummer
    Reason        string    // Begründung für den Task
    LastFetchedAt time.Time // Letzter Fetch-Zeitpunkt
}
```

### Wie wird die Queue generiert?

Der `QueueBuilder` in `go-client/fetchqueue/queue.go:87-144` durchläuft für jede konfigurierte Community folgende Prüfungen:

#### 1. About-Page prüfen (`checkAboutPage`)
- **Nie geholt?** → HIGH Priority Task erstellen
- **Älter als RefreshInterval (24h)?** → MEDIUM Priority Task

#### 2. Members-Seiten prüfen (`checkMembersPages`)
- Seite 1 fehlt? → HIGH Priority
- Weitere Seiten fehlen? → MEDIUM Priority
- Maximal `MaxTasksPerType` (10) Tasks pro Community

#### 3. Community-Posts prüfen (`checkCommunityPage`)
- Seite 1 fehlt? → HIGH Priority
- Refresh nötig? → MEDIUM Priority

#### 4. Mitglieder-Profile prüfen (`checkProfiles`)
- Extrahiert Member-IDs aus Members-Fetches
- Unbekannte Profile → LOW Priority Tasks
- Limitiert auf `MaxTasksPerType`

#### 5. Post-Details prüfen (`checkPostDetails`)
- Extrahiert Post-IDs aus Community-Page-Fetches
- Neue/veraltete Posts → MEDIUM/LOW Priority

#### 6. Post-Likes prüfen (`checkLikes`)
- Falls `FetchPostLikes` aktiviert
- LOW Priority Tasks

### Konfiguration

```go
type QueueConfig struct {
    CommunityIDs     []string      // Überwachte Communities
    MaxTasksPerType  int           // Default: 10
    RefreshInterval  time.Duration // Default: 24 Stunden
    MembersPageSize  int           // Default: 50
    PostsPageSize    int           // Default: 20
    FetchPostLikes   bool          // Default: true
}
```

### Prioritäten-Übersicht

| Task-Typ | Priorität | Grund |
|----------|-----------|-------|
| about_page (erstmalig) | HIGH (1) | Basis-Community-Infos |
| members Seite 1 | HIGH (1) | Essentielle Member-Liste |
| community_page Seite 1 | HIGH (1) | Essentieller Content |
| about_page (Refresh) | MEDIUM (2) | Periodisches Update |
| members (weitere Seiten) | MEDIUM (2) | Erweiterte Daten |
| post_details | MEDIUM/LOW (2/3) | Detail-Informationen |
| profile | LOW (3) | Optionale Daten |
| likes | LOW (3) | Engagement-Daten |

---

## 2. API-Endpunkte (Queue)

### Queue generieren
```
GET /api/fetch-queue?communityIds=community1,community2
```
- Gibt komplette Queue zurück
- Handler: `GetFetchQueueHandler` in `handlers.go:584-624`

### Nächsten Task holen
```
GET /api/fetch-queue/next?communityIds=community1
```
- Gibt nur den nächsten Task zurück
- Handler: `GetNextFetchHandler` in `handlers.go:628-672`

### Daten synchronisieren
```
POST /api/sync
Body: {
    action: string,
    timestamp: string,
    entityType: string,
    source: string,
    data: object
}
```
- Speichert geholte Daten in DuckDB
- Handler: `SyncHandler` in `handlers.go:122-198`

---

## 3. Fetch-Ausführung im Extension-Popup

Die Queue wird im Extension-Popup (`popup.js:302-352`) ausgeführt:

### Ablauf

1. **Queue laden**: `GET /api/fetch-queue?communityIds={id}`
2. **Tasks sequentiell abarbeiten**:
   - Build-ID von Skool-Seite extrahieren
   - API-URL basierend auf Task-Typ konstruieren
   - Fetch mit User-Cookies (credentials: include)
   - Ergebnis an Go-Client senden
   - 2-5 Sekunden Pause vor nächstem Task
   - Progress-Bar aktualisieren
3. **Weiter bis Queue leer** oder User stoppt

### URL-Mapping nach Task-Typ

| Task-Typ | URL-Pattern |
|----------|-------------|
| about_page | `/_next/data/{buildId}/{communityId}/about.json` |
| members | `/_next/data/{buildId}/{communityId}/-/members.json?t=active&p={page}` |
| community_page | `/_next/data/{buildId}/{communityId}.json?c=&s=newest` |
| profile | `/_next/data/{buildId}/@{memberSlug}.json` |
| post_details | (noch nicht implementiert) |
| likes | (noch nicht implementiert) |

---

## 4. Auto-Fetch beim Seitenbesuch

Das Content-Script (`content/index.js`) führt automatisch Fetches durch:

1. **Community-Slug aus URL extrahieren**
2. **Prüfen ob bereits geholt** (Browser-Storage Cache)
3. **Build-ID von Seite holen**
4. **About-Page fetchen** mit User-Session
5. **An Go-Client senden** via Background-Script
6. **Als geholt markieren**

Dies sorgt für passive Datensammlung während der normalen Skool-Nutzung.

---

## 5. Datenspeicherung (Queue)

### DuckDB (Rohdaten)
- Tabelle: `raw_fetches`
- Felder: `entity_type`, `entity_id`, `raw_json`, `source`, `fetched_at`
- Append-only, versioniert
- Pfad: `catknows_data/raw.duckdb`

### SQLite (App-Daten)
- Settings, Sync-Logs, UI-State
- Pfad: `catknows_data/app.sqlite`

---

## 6. Zusammenfassung (Queue)

Die Fetch-Queue wird **dynamisch generiert** basierend auf:
- Welche Communities überwacht werden sollen
- Welche Daten bereits vorhanden sind
- Wie alt die vorhandenen Daten sind

Der Queue-Builder analysiert den aktuellen Datenstand in DuckDB und erstellt priorisierte Tasks für fehlende oder veraltete Daten. Die Browser-Extension führt diese Tasks dann mit der aktiven User-Session aus und speichert die Ergebnisse zurück im lokalen Go-Client.

**Wichtig**: Alle Daten bleiben lokal beim User. Es werden nur Daten geholt, auf die der User selbst Zugriff hat.

---

---

# Teil 4: Lizenz-Mechanismus

## Übersicht

Der Lizenz-Mechanismus stellt sicher, dass nur zahlende Kunden die Software nutzen können. Er basiert auf **kryptographischen Signaturen**, die eine Manipulation der Lizenz-Prüfung verhindern.

## Warum nicht einfach HTTP?

Ein naiver Ansatz wäre:
1. Client fragt Server: "Ist Lizenz XYZ gültig?"
2. Server antwortet: `{"valid": true}`
3. Client akzeptiert

**Problem**: Ein Angreifer kann:
- `/etc/hosts` manipulieren → eigener Fake-Server
- Immer `{"valid": true}` zurückgeben
- Lizenz umgangen

## Die Lösung: Ed25519 Signaturen

### Grundprinzip

```
┌─────────────────────────────────────────────────────────┐
│                    SERVER (geheim)                      │
│                                                         │
│   Private Key: nur Server kennt ihn                     │
│   signiert: "license valid until 2025-12-31"            │
│   erzeugt: SIGNATUR (nur mit Private Key möglich)       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              { data: "...", signature: "xyz..." }
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 GO-CLIENT (öffentlich)                  │
│                                                         │
│   Public Key: im Binary eingebettet                     │
│   verifiziert: Signatur passt zu Daten?                 │
│   → JA: Lizenz gültig                                   │
│   → NEIN: Manipulation erkannt, ablehnen                │
└─────────────────────────────────────────────────────────┘
```

**Warum funktioniert das?**
- Angreifer kann Fake-Server aufsetzen
- Angreifer kennt Private Key **nicht**
- Kann keine gültige Signatur erstellen
- Client lehnt ungültige Signaturen ab

### Zusätzliche Sicherheit: Nonce & Timestamp

**Nonce** (Number used once):
- Client generiert Zufallszahl bei jedem Request
- Server muss diese in der Antwort zurückgeben
- Verhindert **Replay-Angriffe** (alte gültige Antworten wiederverwenden)

**Timestamp**:
- Server fügt aktuelle Zeit hinzu
- Client akzeptiert nur Antworten < 5 Minuten alt
- Verhindert Nutzung alter abgefangener Antworten

## Kommunikationsfluss

```
┌─────────────┐                              ┌─────────────┐
│  Go-Client  │                              │   Server    │
└──────┬──────┘                              └──────┬──────┘
       │                                            │
       │  1. Generiere Nonce (Zufallszahl)          │
       │                                            │
       │  2. POST /api/license/validate.php         │
       │     {                                      │
       │       license_key: "XXXX-XXXX-...",        │
       │       nonce: "a7f9b2c8...",                │
       │       machine_id: "hash..."                │
       │     }                                      │
       │ ─────────────────────────────────────────► │
       │                                            │
       │                              3. Lizenz prüfen in DB
       │                              4. Payload erstellen
       │                              5. Mit Private Key signieren
       │                                            │
       │     {                                      │
       │       payload: {                           │
       │         valid: true,                       │
       │         expires_at: "2025-12-31",          │
       │         nonce: "a7f9b2c8...",  ← gleich!   │
       │         timestamp: 1702400000              │
       │       },                                   │
       │       signature: "ed25519_sig..."          │
       │     }                                      │
       │ ◄───────────────────────────────────────── │
       │                                            │
       │  6. Signatur verifizieren (Public Key)     │
       │  7. Nonce prüfen (muss übereinstimmen)     │
       │  8. Timestamp prüfen (< 5 min alt)         │
       │  9. Bei Erfolg: Cache lokal speichern      │
       │                                            │
```

## Dateien & Struktur

### Server (PHP)

```
webserver/
├── api/
│   └── license/
│       └── validate.php      # Haupt-API-Endpunkt
├── config/
│   ├── database.php          # DB-Verbindung
│   └── keys.php              # Private/Public Keys laden
├── scripts/
│   ├── generate-keys.php     # Schlüsselpaar generieren
│   └── create-license.php    # Neue Lizenz erstellen
└── setup.sql                 # Datenbank-Schema
```

### Client (Go)

```
go-client/
└── license/
    └── license.go            # Lizenz-Manager mit Verifikation
```

## Setup-Anleitung

### 1. Schlüssel generieren

```bash
cd webserver
php scripts/generate-keys.php --save
```

Output:
```
PRIVATE KEY: a1b2c3d4... (128 hex chars)
PUBLIC KEY:  e5f6a7b8... (64 hex chars)
```

### 2. Server konfigurieren

Environment-Variablen setzen:
```bash
export LICENSE_PRIVATE_KEY="a1b2c3d4..."
export LICENSE_PUBLIC_KEY="e5f6a7b8..."
```

Oder in `.env` Datei (NICHT committen!):
```
LICENSE_PRIVATE_KEY=a1b2c3d4...
LICENSE_PUBLIC_KEY=e5f6a7b8...
```

### 3. Public Key in Go-Client einbetten

In `go-client/license/license.go`:
```go
var ServerPublicKey = mustDecodeHex("e5f6a7b8...") // 64 hex chars
```

### 4. Datenbank einrichten

```bash
mysql -u root -p < webserver/setup.sql
```

### 5. Test-Lizenz erstellen

```bash
php scripts/create-license.php --email="test@example.com" --months=12
```

## Datenbank-Schema (Lizenz)

### licenses

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| id | INT | Primary Key |
| license_key | VARCHAR(64) | Einzigartiger Schlüssel (XXXX-XXXX-XXXX-XXXX) |
| customer_email | VARCHAR(255) | Kunden-Email |
| valid_until | DATE | Ablaufdatum |
| is_active | BOOLEAN | Lizenz aktiv/deaktiviert |
| max_activations | INT | Max. erlaubte Geräte |
| features | JSON | Freigeschaltete Features |

### activations

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| license_id | INT | FK zu licenses |
| machine_id | VARCHAR(255) | Hash der Hardware-ID |
| last_seen | TIMESTAMP | Letzter Check von diesem Gerät |

## Offline-Verhalten

Der Client cached Lizenz-Antworten lokal in SQLite:

1. **Online-Check** alle 24 Stunden
2. **Offline-Grace-Period**: 7 Tage
3. Nach 7 Tagen ohne Server-Kontakt: Lizenz ungültig

```go
// In license.go
checkInterval: 24 * time.Hour  // Normale Prüfung
gracePeriod:   7 * 24 * time.Hour  // Offline erlaubt
```

## Sicherheitsanalyse

| Angriff | Schutz | Status |
|---------|--------|--------|
| Fake-Server aufsetzen | Signatur ungültig ohne Private Key | Geschützt |
| Response manipulieren | Signatur wird ungültig | Geschützt |
| Alte Response wiederverwenden | Nonce stimmt nicht überein | Geschützt |
| Response abfangen & später nutzen | Timestamp zu alt | Geschützt |
| Binary patchen (Public Key ändern) | Schwer zu verhindern | Teilschutz |
| Binary cracken (Check entfernen) | Schwer zu verhindern | Teilschutz |

**Realität**: 100% Schutz gegen Binary-Manipulation gibt es nicht. Aber:
- Erfordert Reverse-Engineering-Kenntnisse
- Muss bei jedem Update wiederholt werden
- Für 99% der Nutzer ausreichender Schutz

## API-Referenz (Lizenz)

### POST /api/license/validate.php

**Request:**
```json
{
  "license_key": "XXXX-XXXX-XXXX-XXXX",
  "nonce": "64_hex_chars_random",
  "machine_id": "sha256_of_hardware_id"
}
```

**Response (Erfolg):**
```json
{
  "payload": {
    "valid": true,
    "expires_at": "2025-12-31",
    "nonce": "64_hex_chars_same_as_request",
    "timestamp": 1702400000,
    "product": "catknows",
    "features": ["basic", "analytics", "ai"]
  },
  "signature": "128_hex_chars_ed25519_signature"
}
```

**Response (Fehler):**
```json
{
  "payload": {
    "valid": false,
    "expires_at": "",
    "nonce": "...",
    "timestamp": 1702400000,
    "error": "invalid_license"
  },
  "signature": "..."
}
```

Mögliche Fehler:
- `invalid_license` - Lizenzschlüssel nicht gefunden
- `license_expired` - Lizenz abgelaufen
- `license_deactivated` - Lizenz deaktiviert

## Entwicklung & Testing (Lizenz)

Für lokale Entwicklung wird `api.cat-knows.com` verwendet, damit immer unter realen Bedingungen getestet wird.

Test-Lizenz in der Datenbank:
```
Schlüssel: DEV-TEST-LICENSE-2024
Email: dev@catknows.local
Gültig: 1 Jahr ab Installation
Features: basic, analytics, ai, dev
```

---

---

# Teil 5: Error Handling und Logging

Diese Dokumentation beschreibt den aktuellen Stand von Error Handling und Logging in der CatKnows-Anwendung.

---

## Übersicht

| Komponente | Logging | Error Handling |
|------------|---------|----------------|
| Go-Backend | Standard `log` Package + SQLite-Logs | Error-Return-Pattern + HTTP-Fehlerantworten |
| Frontend | Browser Console + API-Logs | React State-basiert |
| Browser Extension | Console | Try-Catch |

---

## 1. Logging

### 1.1 Go-Backend Logging

**Standard Go Log Package:**
```go
log.Printf("Server started on %s", addr)
log.Fatal("Could not start server:", err)
```

**SQLite-basiertes Logging (persistiert):**
```go
// db/sqlite/sqlite.go
const (
    LogLevelDebug = "debug"
    LogLevelInfo  = "info"
    LogLevelWarn  = "warn"
    LogLevelError = "error"
)

// Verwendung:
storage.App.LogInfo("sync", "Fetched 150 members")
storage.App.LogError("license", "Validation failed: " + err.Error())
```

**Log-Tabelle Schema:**
```sql
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    category TEXT NOT NULL,
    message TEXT NOT NULL
)
```

### 1.2 Log API Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/logs` | GET | Logs abrufen (mit Filteroptionen) |
| `/api/logs` | POST | Neuen Log-Eintrag erstellen |
| `/api/logs` | DELETE | Logs löschen |

**Query-Parameter für GET:**
- `level` - Filter nach Log-Level (debug, info, warn, error)
- `category` - Filter nach Kategorie
- `limit` - Anzahl der Einträge

### 1.3 Frontend Logging

**Console-basiert (Development):**
```typescript
console.log('Settings loaded')
console.error('Failed to fetch data:', err)
```

**LoggingView Komponente:**
- Zeigt persistierte Logs aus der SQLite-Datenbank
- Ermöglicht Filterung nach Level und Kategorie
- Bulk-Löschung möglich

---

## 2. Error Handling

### 2.1 Go-Backend Error Patterns

**Pattern 1: Error Return**
```go
func (r *RawDB) StoreBulkFetch(...) error {
    tx, err := r.db.Begin()
    if err != nil {
        return err
    }
    // ...
    return tx.Commit()
}
```

**Pattern 2: Error Wrapping mit Kontext**
```go
return nil, fmt.Errorf("failed to connect to DuckDB: %w", err)
```

**Pattern 3: HTTP Error Response**
```go
// server/handlers.go
func writeError(w http.ResponseWriter, message string, status int) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(ErrorResponse{Error: message})
}

// Verwendung:
if err != nil {
    writeError(w, "Failed to store data", http.StatusInternalServerError)
    return
}
```

**Pattern 4: Fatal Errors beim Start**
```go
// main.go - Kritische Initialisierungsfehler
log.Fatal("Storage error:", err)
```

### 2.2 HTTP Status Codes

| Code | Verwendung |
|------|------------|
| 200 | Erfolgreiche Anfrage |
| 400 | Ungültiges JSON, fehlende Parameter |
| 404 | Datei nicht gefunden |
| 500 | Datenbank-Fehler, Storage-Fehler |

### 2.3 Error Response Format

```json
{
    "error": "Fehlerbeschreibung hier"
}
```

### 2.4 Frontend Error Handling

**React State Pattern:**
```typescript
const [error, setError] = useState<string | null>(null)
const [loading, setLoading] = useState(false)

const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
        const response = await fetch('/api/data')
        if (!response.ok) throw new Error('Fetch failed')
        // ...
    } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
        setLoading(false)
    }
}
```

**Error Display:**
```tsx
{error && <div className="error-message">{error}</div>}
```

---

## 3. Panic Recovery

**Chi Middleware:**
```go
r := chi.NewRouter()
r.Use(middleware.Recoverer)  // Fängt Panics ab
```

**Explizite Panics (nur bei unrecoverable Errors):**
- `embedded.go` - Asset-Loading Fehler
- `license/license.go` - Ungültiger Public Key

---

## 4. Sync-Logging (Spezialfall)

Für Sync-Operationen gibt es ein dediziertes Logging:

```go
// Nach erfolgreichem Sync
h.storage.App.LogSync(req.EntityType, len(items), "success", "")

// Bei Fehler
h.storage.App.LogSync(req.EntityType, 0, "error", err.Error())
```

**Sync-Log Tabelle:**
```sql
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    entity_type TEXT NOT NULL,
    count INTEGER,
    status TEXT,
    error_message TEXT
)
```

---

## 5. Lizenz-Error Handling

**Spezielle Behandlung in `license/license.go`:**

| Fehlertyp | Verhalten |
|-----------|-----------|
| Netzwerk-Fehler | Fallback auf gecachte Lizenz (7 Tage Gnadenfrist) |
| Signatur ungültig | Lizenz abgelehnt, Fehlermeldung |
| Nonce Mismatch | Replay-Attack vermutet, Lizenz abgelehnt |
| Zeitstempel zu alt | Lizenz abgelehnt (>5 Min Differenz) |

---

## 6. Bekannte Lücken

### Hohe Priorität
1. **Kein strukturiertes Logging** - Standard `log` Package hat keine Log-Levels, keine strukturierten Felder
2. **Keine React Error Boundary** - Rendering-Fehler können die gesamte App crashen
3. **Keine Request-IDs** - Schwer, Logs über mehrere Komponenten zu korrelieren

### Mittlere Priorität
4. **Keine Retry-Logik** - Transiente Fehler führen direkt zum Abbruch
5. **Frontend-Fehler nicht persistiert** - Console-Errors gehen verloren
6. **Keine Stack Traces** - Schwierige Fehleranalyse

### Niedrige Priorität
7. **Kein Circuit Breaker** - Externe APIs können die App blockieren
8. **Gemischte Sprachen** - Fehlermeldungen teils Deutsch, teils Englisch

---

## 7. Empfehlungen für Weiterentwicklung

### Kurzfristig
- `slog` (Go 1.21+) für strukturiertes Logging einführen
- React Error Boundary implementieren
- Request-ID Header für alle API-Calls

### Mittelfristig
- Frontend-Fehler an Backend senden
- Retry mit Exponential Backoff für externe APIs
- Zentrale Error-Code-Dokumentation

### Langfristig
- Error-Analytics/Monitoring
- Request-Tracing
- Circuit Breaker Pattern

---

## 8. Code-Referenzen

| Datei | Beschreibung |
|-------|--------------|
| `go-client/db/sqlite/sqlite.go` | SQLite Logging-Methoden |
| `go-client/server/handlers.go` | HTTP Error Handling |
| `go-client/license/license.go` | Lizenz-Error Handling |
| `frontend-client-ui/src/components/LoggingView.tsx` | Log-Anzeige UI |

---

---

# Teil 6: Update-Prozess

> Letzte Aktualisierung: 2025-12-19

## Zusammenfassung

Das Update-System hat eine **grundlegende Infrastruktur**, ist aber **noch nicht vollständig implementiert**. Die Download-API und Lizenzverwaltung funktionieren, jedoch fehlen aktive Update-Prüfmechanismen im Go-Client.

---

## Implementierungsstatus

| Komponente | Status | Beschreibung |
|------------|--------|--------------|
| Download API | Implementiert | Stellt Binaries nach Plattform bereit |
| Lizenzvalidierung | Implementiert | Kryptographische Validierung, Offline-Caching |
| Binary-Speicherung | Implementiert | Organisiert in `webserver/downloads/` |
| Versions-Tracking | Fehlt | Keine Versionskonstante im Go-Client |
| Update-Prüfung | Fehlt | Kein Endpoint, kein Background-Checker |
| Update-UI | Fehlt | Keine Update-Benachrichtigung im Frontend |
| Update-Installation | Fehlt | Kein Self-Update-Mechanismus |
| Binary-Versionierung | Teilweise | Dateinamen enthalten keine Version |

---

## Was funktioniert

### 1. Download-API (`/webserver/api/download.php`)

Die Download-API ist vollständig implementiert und bietet:

**Endpunkte:**
- `?info` - Listet verfügbare Plattformen
- `?detect` - Erkennt Plattform automatisch aus User-Agent
- `?platform={name}` - Lädt spezifisches Binary herunter

**Unterstützte Plattformen:**
| Plattform | Dateiname |
|-----------|-----------|
| macOS (Apple Silicon) | `catknows-macos-arm64` |
| macOS (Intel) | `catknows-macos-amd64` |
| Windows | `catknows-windows-amd64.exe` |
| Linux | `catknows-linux-amd64` |

**Speicherort:** `/webserver/downloads/`

### 2. Download-Seite (`/webserver/index.php`)

Die Landing-Page enthält:
- Automatische Plattform-Erkennung
- Plattform-spezifische Download-Buttons
- WebGL-basierte Apple Silicon Erkennung

### 3. Build-Script (`/scripts/build-all.sh`)

Cross-kompiliert Go-Binaries für alle Plattformen:
```bash
./scripts/build-all.sh
```

Platziert die fertigen Binaries automatisch in `/webserver/downloads/`.

### 4. Lizenzverwaltung

**Webserver** (`/webserver/api/license/validate.php`):
- Ed25519 kryptographische Signaturprüfung
- Nonce-basierter Replay-Schutz
- Ablaufprüfung
- Maschinen-Aktivierungstracking
- Feature-Flags

**Go-Client** (`/go-client/license/license.go`):
- Lokale Lizenz-Validierung
- 24-Stunden Prüfintervall
- Offline-Gnadenfrist (max. 7 Tage)
- Cache in SQLite-Datenbank

---

## Was fehlt

### 1. Versionskonstante im Go-Client

**Fehlt in:** `/go-client/main.go`

Es gibt keine definierte Version im Binary:
```go
// NICHT VORHANDEN:
const AppVersion = "0.1.0"
```

### 2. Update-Prüf-Endpoints

**Fehlt in:** `/go-client/server/handlers.go`, `/go-client/server/router.go`

Keine Routes für:
- `GET /api/version` - Aktuelle Version zurückgeben
- `GET /api/check-update` - Auf neue Version prüfen

### 3. Update-Metadaten-API

**Fehlt in:** `/webserver/api/`

Ein Endpoint wie `/webserver/api/updates.php` der zurückgibt:
```json
{
  "latest_version": "1.0.0",
  "download_url": "https://example.com/api/download?platform=auto",
  "changelog": "...",
  "mandatory": false
}
```

### 4. Background-Update-Checker

**Fehlt im Go-Client:**
- Automatische Prüfung alle 24 Stunden
- Versionsnummern-Vergleich (SemVer)
- Cache für letzten Prüfzeitpunkt

### 5. Update-UI im Frontend

**Fehlt in:** `/frontend-client-ui/src/`

Keine Implementierung von:
- "Nach Updates suchen" Button
- Update-Benachrichtigungs-Banner
- Link zur Download-Seite

---

## Aktueller Update-Workflow (manuell)

Da automatische Updates noch nicht implementiert sind, ist der aktuelle Prozess **vollständig manuell**:

```
1. Nutzer besucht die Website (Landing-Page)
2. Website erkennt Plattform automatisch
3. Nutzer klickt auf "Download"
4. Nutzer ersetzt manuell das alte Binary durch das neue
5. Nutzer startet die Anwendung neu
```

---

## Geplanter Update-Workflow (Zielzustand)

```
1. Go-Client startet
2. Background-Task prüft alle 24h auf Updates
   → GET https://server.com/api/updates
3. Bei neuer Version:
   → Frontend zeigt Benachrichtigung
   → "Neue Version verfügbar: 1.2.0"
4. Nutzer klickt "Jetzt aktualisieren"
5. Browser öffnet Download-Seite
6. Nutzer lädt neue Version herunter
7. Nutzer ersetzt Binary und startet neu

(Alternative: Self-Update mit automatischem Binary-Ersatz)
```

---

## Relevante Dateien

### Webserver (Update-Infrastruktur)
- `/webserver/api/download.php` - Download-API
- `/webserver/index.php` - Landing-Page
- `/webserver/downloads/` - Binary-Speicherort
- `/webserver/setup.sql` - Lizenz-Datenbank-Schema

### Go-Client (muss erweitert werden)
- `/go-client/main.go` - Versionskonstante hinzufügen
- `/go-client/server/handlers.go` - Update-Endpoints hinzufügen
- `/go-client/server/router.go` - Routes registrieren
- `/go-client/license/license.go` - Lizenz-Manager (Vorlage für Update-Manager)

### Frontend (muss erweitert werden)
- `/frontend-client-ui/src/App.tsx` - Update-Banner
- `/frontend-client-ui/src/components/SettingsView.tsx` - Update-Button

### Build-Scripts
- `/scripts/build-all.sh` - Multi-Plattform-Build
- `/scripts/build.sh` - Einzel-Build
- `/scripts/build_dev.sh` - Entwicklungs-Build

---

## Nächste Schritte zur Vervollständigung

### Priorität 1: Grundlagen
1. **Versionskonstante** in `/go-client/main.go` hinzufügen
2. **`/api/version`** Endpoint implementieren
3. **`/api/updates`** Endpoint auf Webserver erstellen

### Priorität 2: Update-Prüfung
4. Update-Check-Logik im Go-Client
5. Background-Task für periodische Prüfung
6. Versionsnummern-Vergleich (SemVer)

### Priorität 3: UI
7. Update-Banner-Komponente im Frontend
8. "Nach Updates suchen" Button in Settings
9. Changelog-Anzeige

### Optional: Self-Update
10. Binary-Download-Logik
11. Automatischer Binary-Ersatz
12. Neustart-Mechanismus

---

## Browser-Extension

Die Browser-Extension (`/browser-extension/`) hat derzeit:
- Version: `0.1.0` (in `manifest.json`)
- **Kein eigener Update-Mechanismus** (nutzt Browser-Store-Updates)

Updates der Extension erfolgen über den jeweiligen Browser-Store (Chrome Web Store, Firefox Add-ons, Edge Add-ons).

---

---

# Teil 7: Testing-Konzept

## Übersicht

Das CatKnows-Projekt verfolgt einen **pragmatischen, Demo-Driven Testing-Ansatz**. Anstatt klassische Unit-Tests zu nutzen, bietet die Anwendung **eingebaute Test-UIs** und **API-Endpoints**, die interaktives Testen ermöglichen.

Dieser Ansatz passt zum Konzept einer lokalen Software, bei der Endnutzer und Entwickler direkt mit der Anwendung interagieren.

---

## Test Center – Frontend-UI

Das Frontend enthält mehrere Views, die als **integriertes Test Center** dienen:

### 1. Fetch Queue View

**Pfad:** `frontend-client-ui/src/components/FetchQueueView.tsx`

**Zweck:** Manuelle Generierung und Validierung von Fetch-Queues

**Funktionen:**
- Community-IDs eingeben und Queue generieren
- Task-Statistiken nach Typ anzeigen (About Page, Profiles, Members, Posts, etc.)
- Alle 7 Fetch-Task-Typen mit Priority-Levels visualisieren
- Community-IDs aus Server-Settings laden/speichern

**Test-Workflow:**
1. Community-IDs eingeben oder aus Settings laden
2. "Queue Generieren" klicken
3. Generierte Tasks inspizieren
4. Statistiken prüfen (Anzahl pro Typ, Prioritäten)

---

### 2. Fetches View

**Pfad:** `frontend-client-ui/src/components/FetchesView.tsx`

**Zweck:** Inspektion aller in DuckDB gespeicherten Rohdaten

**Funktionen:**
- Filter nach Entity-Typ und Quelle
- Expandierbare JSON-Detail-Ansicht pro Fetch-Record
- Pagination mit einstellbaren Limits (25, 50, 100, 500)
- Gesamt-Count, Entity-Typen und Data-Sources anzeigen

**Test-Workflow:**
1. Fetches-Tab öffnen
2. Nach gewünschtem Entity-Typ filtern
3. Einzelne Records expandieren und JSON inspizieren
4. Datenqualität und Vollständigkeit prüfen

---

### 3. Logging View

**Pfad:** `frontend-client-ui/src/components/LoggingView.tsx`

**Zweck:** Echtzeit-Logging und Debugging

**Funktionen:**
- Live-Log-Anzeige aus app.sqlite
- Filter nach Log-Level (debug, info, warn, error) und Source
- Expandierbare Detail-Ansicht pro Log-Eintrag
- Logs löschen (Clear)
- Gesamt-Logs und verfügbare Sources anzeigen

**Test-Workflow:**
1. Logging-Tab öffnen
2. Aktion in der Anwendung ausführen
3. Logs beobachten und nach Level filtern
4. Bei Fehlern: Details expandieren und Stack-Trace analysieren

---

### 4. Settings View

**Pfad:** `frontend-client-ui/src/components/SettingsView.tsx`

**Zweck:** Test-Konfiguration verwalten

**Testbare Settings:**
| Setting | Beschreibung |
|---------|--------------|
| `community_ids` | Komma-separierte Liste von Test-Communities |
| `openai_api_key` | API-Key für AI-Feature-Tests |

---

## Browser Extension – Test Center

**Pfad:** `browser-extension/src/popup/popup.js`

Die Browser-Extension enthält ein **eingebautes Test-UI** im Popup:

### Funktionen

| Feature | Beschreibung |
|---------|--------------|
| **Server Status** | Visueller Indikator (online/offline) für lokalen Go-Client |
| **Queue Laden** | Pending Tasks vom Server abrufen und anzeigen |
| **Queue Starten** | Tasks sequentiell mit Progress-Tracking ausführen |
| **Queue Stoppen** | Ausführung pausieren |
| **Cache Löschen** | Fetch-History zurücksetzen |

### Progress-Anzeige

- Progress-Bar (completed/total tasks)
- Task-Liste mit den ersten 5 pending Tasks
- Task-Icons und Priority-Badges
- Statistiken pro Task-Typ

### Test-Workflow

1. Zu einer Skool.com-Community navigieren
2. Extension-Icon klicken (Popup öffnet sich)
3. Community-IDs eingeben oder aus Settings laden
4. "Queue Generieren" klicken → Queue-Logik testen
5. "Start Queue" klicken → Vollständigen Fetch-Workflow simulieren

---

## API-Endpoints für Testing

Der Go-Server bietet Endpoints, die für manuelles Testing genutzt werden können:

| Endpoint | Methode | Zweck |
|----------|---------|-------|
| `/api/hello` | GET | Health-Check, Server-Verfügbarkeit |
| `/api/ping` | POST | Echo-Test, Verbindungs-Verifizierung |
| `/api/stats` | GET | Rohdaten-Statistiken (Datenvolumen) |
| `/api/fetches` | GET | Alle Fetches abfragen (Daten-Inspektion) |
| `/api/fetch-queue` | GET | Queue generieren (Queue-Logik validieren) |
| `/api/logs` | GET | Logs abrufen (Debugging) |
| `/api/logs` | POST | Log-Eintrag schreiben (Log-System testen) |
| `/api/logs` | DELETE | Logs löschen (State zurücksetzen) |
| `/api/settings` | GET | Alle Settings lesen |
| `/api/settings/:key` | GET/POST | Einzelnes Setting lesen/schreiben |

---

## Go-Tests (AI-Integration)

**Pfad:** `go-client/ai/ai_test.go`

### Test-Funktionen

| Test | Beschreibung |
|------|--------------|
| `TestSimpleChat()` | Basis-Interaktion mit AI |
| `TestChatWithMessages()` | Multi-Turn-Conversations mit System-Prompts |
| `TestClientNotConfigured()` | Graceful Failure ohne API-Key |
| `TestAIClientCreation()` | Client-Instantiierung (läuft ohne API-Key) |

### Conditional Test Execution

Tests werden **übersprungen**, wenn kein `OPENAI_API_KEY` gesetzt ist:

```bash
# Ohne API-Key (Tests werden geskippt)
go test -v ./ai/...

# Mit API-Key (vollständige Tests)
export OPENAI_API_KEY="sk-..."
go test -v ./ai/...
```

### Logging

Alle Tests nutzen `[AI_TEST]`-Prefixes für einfaches Debugging:
- Request-Dauer
- Token-Verbrauch
- Response-Details

---

## Vollständiger Test-Workflow

### Development-Testing

```bash
# 1. Build und Server starten
./scripts/build_dev.sh

# 2. Browser öffnet automatisch http://localhost:3000
# 3. Zu den Test-Tabs navigieren:
#    - Fetch Queue → Queue-Generierung testen
#    - Fetches → Gespeicherte Daten inspizieren
#    - Logs → Anwendungs-Verhalten monitoren
#    - Settings → Test-Konfiguration anpassen
```

### Extension-Testing

1. Extension in Chrome/Firefox laden (Developer Mode)
2. Zu einer Skool.com-Community navigieren
3. Extension-Popup öffnen
4. Server-Status prüfen (sollte "online" sein)
5. Queue generieren und starten
6. Progress in Extension und Frontend-Logs beobachten

### API-Testing (curl)

```bash
# Health-Check
curl http://localhost:3000/api/hello

# Stats abrufen
curl http://localhost:3000/api/stats

# Fetches inspizieren
curl "http://localhost:3000/api/fetches?limit=10"

# Queue generieren
curl "http://localhost:3000/api/fetch-queue?communityIds=test-community"
```

---

## Zusammenfassung

| Komponente | Test-Methode |
|------------|--------------|
| **Frontend** | Eingebaute Test-UIs (Fetch Queue, Fetches, Logs, Settings) |
| **Browser Extension** | Popup als funktionales Test-Harness |
| **Go-Server** | API-Endpoints für manuelle Tests + Go-Tests für AI |
| **Datenfluss** | Logging-View für End-to-End-Tracing |

**Vorteile dieses Ansatzes:**
- Kein komplexes Test-Framework erforderlich
- Interaktives Testen während der Entwicklung
- Gleiche UI, die Endnutzer sehen werden
- Einfaches Debugging durch integriertes Logging
- Schnelle Feedback-Loops durch Live-Daten-Inspektion
