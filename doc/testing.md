# Testing-Konzept – Test Center & Frontend-UI

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
