# Fetch-Prozess & Fetch-Queue

Dieses Dokument beschreibt, wie der Fetch-Prozess funktioniert und wie die Fetch-Queue generiert wird.

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

## 2. API-Endpunkte

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

## 5. Datenspeicherung

### DuckDB (Rohdaten)
- Tabelle: `raw_fetches`
- Felder: `entity_type`, `entity_id`, `raw_json`, `source`, `fetched_at`
- Append-only, versioniert
- Pfad: `catknows_data/raw.duckdb`

### SQLite (App-Daten)
- Settings, Sync-Logs, UI-State
- Pfad: `catknows_data/app.sqlite`

---

## 6. Zusammenfassung

Die Fetch-Queue wird **dynamisch generiert** basierend auf:
- Welche Communities überwacht werden sollen
- Welche Daten bereits vorhanden sind
- Wie alt die vorhandenen Daten sind

Der Queue-Builder analysiert den aktuellen Datenstand in DuckDB und erstellt priorisierte Tasks für fehlende oder veraltete Daten. Die Browser-Extension führt diese Tasks dann mit der aktiven User-Session aus und speichert die Ergebnisse zurück im lokalen Go-Client.

**Wichtig**: Alle Daten bleiben lokal beim User. Es werden nur Daten geholt, auf die der User selbst Zugriff hat.
