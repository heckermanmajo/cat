# Update-Prozess - Aktueller Stand

> Letzte Aktualisierung: 2025-12-19

## Zusammenfassung

Das Update-System hat eine **grundlegende Infrastruktur**, ist aber **noch nicht vollständig implementiert**. Die Download-API und Lizenzverwaltung funktionieren, jedoch fehlen aktive Update-Prüfmechanismen im Go-Client.

---

## Implementierungsstatus

| Komponente | Status | Beschreibung |
|------------|--------|--------------|
| Download API | ✅ Implementiert | Stellt Binaries nach Plattform bereit |
| Lizenzvalidierung | ✅ Implementiert | Kryptographische Validierung, Offline-Caching |
| Binary-Speicherung | ✅ Implementiert | Organisiert in `webserver/downloads/` |
| Versions-Tracking | ❌ Fehlt | Keine Versionskonstante im Go-Client |
| Update-Prüfung | ❌ Fehlt | Kein Endpoint, kein Background-Checker |
| Update-UI | ❌ Fehlt | Keine Update-Benachrichtigung im Frontend |
| Update-Installation | ❌ Fehlt | Kein Self-Update-Mechanismus |
| Binary-Versionierung | ❌ Teilweise | Dateinamen enthalten keine Version |

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
