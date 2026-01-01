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
    ▼ (generiert Tasks nach Hierarchie)
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
| Queue Builder | `go-client/fetchqueue/queue.go` | Generiert die Queue basierend auf Datenstand und Hierarchie |
| Content Script | `browser-extension/src/content/index.js` | Auto-Fetch beim Seitenbesuch |
| Background Worker | `browser-extension/src/background/index.js` | Routing der Requests zum Go-Client |
| Extension Popup | `browser-extension/src/popup/popup.js` | Queue-Ausführung und UI |
| API Handler | `go-client/server/handlers.go` | Endpunkte für Sync und Queue |
| Frontend Queue View | `frontend-client-ui/src/components/FetchQueueView.tsx` | Queue-Generierung und Anzeige |

---

## 1. Fetch-Hierarchie (NEU)

Die Fetch-Queue folgt einer klaren **4-Phasen-Hierarchie**:

### Phase 1: PRIMÄR - Members & Posts (CRITICAL/HIGH Priority)

Zuerst werden immer die Grunddaten geholt:

| Fetch-Typ | Beschreibung |
|-----------|--------------|
| `members` | Member-Listen (paginiert) - Basis für alle weiteren Member-bezogenen Fetches |
| `community_page` | Posts-Übersicht (paginiert) - Basis für Post-Details und Likes |

**Strategie:**
- Initial: CRITICAL Priority (ohne diese Daten geht nichts)
- Refresh: HIGH Priority (wenn älter als RefreshInterval)
- Paginiert alle verfügbaren Seiten

### Phase 2: SEKUNDÄR - Post Details & Likes (MEDIUM Priority)

Für jeden **neuen Post** (der noch keine Details hat):

| Fetch-Typ | Beschreibung |
|-----------|--------------|
| `post_details` | Post-Inhalt + Kommentare |
| `likes` | Wer hat den Post geliked |

### Phase 3: TERTIÄR - Member Profile (LOW Priority)

Für jedes **neue Member** (das noch kein Profil hat):

| Fetch-Typ | Beschreibung |
|-----------|--------------|
| `profile` | Vollständiges Member-Profil inkl. Communities |

### Phase 4: ERWEITERT - Shared Communities (LOWEST Priority)

Basierend auf den Member-Profilen werden **gemeinsame Communities** identifiziert:

| Fetch-Typ | Beschreibung |
|-----------|--------------|
| `shared_communities` | Communities, in denen viele unserer Members aktiv sind |

**Logik:**
1. Aus den gefetchten Profilen werden alle Communities extrahiert
2. Gezählt wird, wie viele unserer Members in jeder Community sind
3. Communities mit `MinSharedMembersForFetch` (default: 3) oder mehr werden als Tasks hinzugefügt
4. Sortierung nach Anzahl gemeinsamer Members (absteigend)

---

## 2. Wasserzeichen-Mechanismus

Der Queue-Builder nutzt ein **Wasserzeichen** (Watermark), um zu bestimmen, welche Daten "neu" sind:

```go
func (qb *QueueBuilder) getLastFetchWatermark(communityID string) time.Time
```

- Das Wasserzeichen ist der **ältere Zeitpunkt** von:
  - Letztem Members-Fetch (Page 1)
  - Letztem Community-Page-Fetch (Page 1)
- Daten, die nach diesem Zeitpunkt nicht mehr gefetcht wurden, gelten als "neu"

---

## 3. Fetch-Queue-Generierung

### Struktur eines FetchTask

```go
type FetchTask struct {
    ID            string    // Eindeutige Task-ID
    Type          string    // Fetch-Typ (siehe Hierarchie)
    Priority      int       // 0=Critical, 1=High, 2=Medium, 3=Low, 4=Lowest
    CommunityID   string    // Ziel-Community
    EntityID      string    // Optional: Member-ID oder Post-ID
    Page          int       // Optional: Seitennummer
    Params        map       // Zusätzliche Parameter
    Reason        string    // Begründung für den Task
    LastFetchedAt time.Time // Letzter Fetch-Zeitpunkt
}
```

### Prioritäten-Übersicht

| Priorität | Wert | Anwendung |
|-----------|------|-----------|
| CRITICAL | 0 | Initiale Fetches (Members/Posts Page 1 wenn noch nie gefetcht) |
| HIGH | 1 | Primäre Refreshes (Members/Posts Refresh fällig) |
| MEDIUM | 2 | Sekundäre Fetches (Post-Details, Likes) |
| LOW | 3 | Tertiäre Fetches (Member-Profile) |
| LOWEST | 4 | Erweiterte Fetches (Shared Communities) |

### Konfiguration

```go
type QueueConfig struct {
    CommunityIDs               []string      // Überwachte Communities
    MaxTasksPerType            int           // Max Tasks pro Typ (0 = unbegrenzt)
    RefreshInterval            time.Duration // Default: 24 Stunden
    MembersPageSize            int           // Default: 50
    PostsPageSize              int           // Default: 20
    FetchPostLikes             bool          // Default: true
    FetchPostComments          bool          // Default: true
    FetchMemberProfiles        bool          // Default: true
    FetchSharedCommunities     bool          // Default: true
    MinSharedMembersForFetch   int           // Default: 3
    StopOnOldData              bool          // Default: true
}
```

---

## 4. API-Endpunkte

### Queue generieren
```
GET /api/fetch-queue?communityIds=community1,community2
```
- Gibt komplette Queue zurück (nach Hierarchie sortiert)

### Nächsten Task holen
```
GET /api/fetch-queue/next?communityIds=community1
```
- Gibt nur den nächsten Task zurück

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

---

## 5. Fetch-Ausführung im Extension-Popup

### Ablauf

1. **Queue laden**: `GET /api/fetch-queue?communityIds={id}`
2. **Tasks nach Priorität abarbeiten**:
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
| members | `/_next/data/{buildId}/{communityId}/-/members.json?t=active&p={page}` |
| community_page | `/_next/data/{buildId}/{communityId}.json?c=&s=newest` |
| profile | `/_next/data/{buildId}/@{memberSlug}.json` |
| post_details | `/_next/data/{buildId}/{communityId}/post/{postId}.json` |
| likes | (via API) |
| about_page | `/_next/data/{buildId}/{communityId}/about.json` |

---

## 6. Shared Communities Feature

### Wie es funktioniert

1. **Voraussetzung**: Member-Profile müssen bereits gefetcht sein
2. **Analyse**: Aus jedem Profil werden die Communities extrahiert (`user.groups`)
3. **Aggregation**: Zählung wie viele unserer Members in welcher Community sind
4. **Filterung**: Nur Communities mit >= `MinSharedMembersForFetch` Members
5. **Priorisierung**: Nach Anzahl gemeinsamer Members sortiert

### Datenstruktur

```go
type CommunityWithSharedMembers struct {
    CommunityID   string   // ID/Slug der Community
    CommunityName string   // Name der Community
    SharedCount   int      // Anzahl gemeinsamer Members
    MemberIDs     []string // IDs der gemeinsamen Members
}
```

### API

Der Queue-Builder bietet eine öffentliche Methode:

```go
func (qb *QueueBuilder) GetSharedCommunities(communityID string) ([]CommunityWithSharedMembers, error)
```

Diese kann vom Handler genutzt werden, um dem User die Analyse anzuzeigen.

---

## 7. Datenspeicherung

### DuckDB (Rohdaten)
- Tabelle: `raw_fetches`
- Felder: `entity_type`, `entity_id`, `raw_json`, `source`, `fetched_at`
- Append-only, versioniert
- Pfad: `catknows_data/raw.duckdb`

### SQLite (App-Daten)
- Settings, Sync-Logs, UI-State
- Pfad: `catknows_data/app.sqlite`

---

## 8. Beispiel: Typischer Fetch-Ablauf

**Szenario**: Neue Community "my-community" wird hinzugefügt

```
Queue-Generation:
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: PRIMÄR (CRITICAL)                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. members_my-community_page_1     - Initiales Members-Fetch│
│ 2. community_page_my-community_page_1 - Initiales Posts-Fetch│
└─────────────────────────────────────────────────────────────┘

Nach Ausführung von Phase 1 (beim nächsten Queue-Build):
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: PRIMÄR (HIGH)                                      │
├─────────────────────────────────────────────────────────────┤
│ 1. members_my-community_page_2     - Weitere Members Pages  │
│ 2. members_my-community_page_3                              │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: SEKUNDÄR (MEDIUM)                                  │
├─────────────────────────────────────────────────────────────┤
│ 3. post_details_my-community_post1 - Details für Post 1     │
│ 4. likes_my-community_post_post1   - Likes für Post 1       │
│ 5. post_details_my-community_post2 - Details für Post 2     │
│ ...                                                         │
├─────────────────────────────────────────────────────────────┤
│ Phase 3: TERTIÄR (LOW)                                      │
├─────────────────────────────────────────────────────────────┤
│ 10. profile_my-community_user1     - Profil User 1          │
│ 11. profile_my-community_user2     - Profil User 2          │
│ ...                                                         │
└─────────────────────────────────────────────────────────────┘

Nach Profil-Fetches (beim nächsten Queue-Build):
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: ERWEITERT (LOWEST)                                 │
├─────────────────────────────────────────────────────────────┤
│ 1. shared_communities_..._other-community-1                 │
│    → 15 gemeinsame Members                                  │
│ 2. shared_communities_..._other-community-2                 │
│    → 8 gemeinsame Members                                   │
│ 3. shared_communities_..._other-community-3                 │
│    → 5 gemeinsame Members                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Zusammenfassung

Die Fetch-Queue folgt einer **strikten Hierarchie**:

1. **Primär**: Members + Posts (Grunddaten für alles weitere)
2. **Sekundär**: Post-Details + Likes (für jeden neuen Post)
3. **Tertiär**: Member-Profile (für jedes neue Member)
4. **Erweitert**: Shared Communities (basierend auf Profil-Analyse)

Diese Hierarchie stellt sicher, dass:
- Zuerst die wichtigsten Daten geholt werden
- Neue Posts und Members automatisch erkannt werden
- Profile nur für relevante Members gefetcht werden
- Interessante Communities (mit vielen gemeinsamen Members) identifiziert werden

**Wichtig**: Alle Daten bleiben lokal beim User. Es werden nur Daten geholt, auf die der User selbst Zugriff hat.
