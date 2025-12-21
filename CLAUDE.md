# Projektübersicht – CatKnows

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
Siehe `doc/lizenz-mechanism.md` für Details.

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

## Dokumentation

Detaillierte Dokumentation in `doc/`:

| Datei | Inhalt |
|-------|--------|
| `local-data-setup.md` | DuckDB/SQLite Schema, Storage API, Datentypen |
| `fetch-prozess-und-queue.md` | Queue-Generierung, Task-Typen, Prioritäten |
| `lizenz-mechanism.md` | Ed25519 Signaturen, Nonce, Offline-Grace-Period |
| `error-handling-und-logging.md` | Error-Patterns, Log-Levels, bekannte Lücken |
| `update-prozess.md` | Download-API, Binary-Versionierung, Update-Status |
| `testing.md` | Test-Center, API-Testing, Demo-Driven-Ansatz |

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
