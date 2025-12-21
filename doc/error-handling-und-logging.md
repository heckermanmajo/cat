# Error Handling und Logging

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
