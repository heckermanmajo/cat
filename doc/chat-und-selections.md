# Chat, Selections und Reports

Diese Dokumentation beschreibt das Chat-Feature und wie es mit Selections und Reports zusammenhaengt.

---

## Uebersicht

Das Chat-System ermoeglicht es Nutzern, in natuerlicher Sprache mit den Community-Daten zu interagieren. Der AI-Assistent "CatNose" analysiert Anfragen und erstellt automatisch **Selections** (strukturierte Datenabfragen), die dann in **Reports** zusammengefasst werden koennen.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Chat (ChatView)                            │
│  ┌────────────┐     ┌────────────────────┐     ┌────────────────┐  │
│  │  Sidebar   │     │   Messages Area    │     │  Report Panel  │  │
│  │  (Chats)   │     │                    │     │                │  │
│  │            │     │  User: "Zeige mir  │     │  Zusammenfass. │  │
│  │  - Chat 1  │     │        aktive..."  │     │  von Selections│  │
│  │  - Chat 2  │     │                    │     │                │  │
│  │            │     │  CatNose: "Hier    │     │                │  │
│  │            │     │  ist eine..."      │     │                │  │
│  │            │     │                    │     │                │  │
│  │            │     │  [SelectionCard]   │     │                │  │
│  │            │     │   - Name/Titel     │     │                │  │
│  │            │     │   - Filter         │     │                │  │
│  │            │     │   - Ergebnisse     │     │                │  │
│  └────────────┘     └────────────────────┘     └────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Konzepte

### 1. Chat

Ein **Chat** ist eine Konversation zwischen Nutzer und AI-Assistent.

**Datenbankschema (SQLite: `chats`):**
```sql
CREATE TABLE chats (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    report_id INTEGER,          -- Verknuepfter Report (lazy created)
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

**Eigenschaften:**
- Jeder Chat kann einen verknuepften Report haben (1:1 Beziehung)
- Der Report wird lazy erstellt beim ersten "In Report uebernehmen"
- Chat-Titel wird initial als "New Chat" gesetzt

### 2. Message

Eine **Message** ist eine einzelne Nachricht in einem Chat.

**Datenbankschema (SQLite: `messages`):**
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL,         -- 'user' oder 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP
)
```

**Rollen:**
- `user`: Nachricht vom Nutzer
- `assistant`: Antwort von CatNose (AI)

### 3. Selection

Eine **Selection** ist eine strukturierte Datenabfrage mit Filtern.

**Datenbankschema (SQLite: `selections`):**
```sql
CREATE TABLE selections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,         -- Titel/Name der Selection (vom Bot gesetzt)
    output_type TEXT NOT NULL,  -- 'member', 'post', oder 'community'
    filters_json TEXT NOT NULL, -- JSON mit Filterkriterien
    result_count INTEGER,       -- Anzahl der Ergebnisse
    result_ids_json TEXT,       -- IDs der gefundenen Entities
    created_by TEXT NOT NULL,   -- 'assistant' oder 'user'
    message_id INTEGER,         -- Verknuepfung zur Nachricht (wenn vom Bot)
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

**Output-Typen:**
| Typ | Beschreibung | Verfuegbare Filter |
|-----|--------------|-------------------|
| `member` | Mitglieder | `community_ids`, `joined_after`, `joined_before`, `post_count_min`, `post_count_max` |
| `post` | Posts | `community_ids`, `created_after`, `created_before`, `likes_min`, `author_id`, `limit` |
| `community` | Communities | (keine Filter) |

**Beispiel Selection JSON:**
```json
{
  "name": "Aktive Mitglieder",
  "outputType": "member",
  "filters": {
    "post_count_min": 5,
    "community_ids": ["community-123"]
  }
}
```

### 4. Report

Ein **Report** sammelt Selections mit AI-generierten Zusammenfassungen.

**Datenbankschema (SQLite: `reports`, `report_blocks`):**
```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,  -- 'chat' oder 'analysis'
    data_json TEXT,
    created_at TIMESTAMP
)

CREATE TABLE report_blocks (
    id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    block_type TEXT NOT NULL,   -- 'text' oder 'selection'
    position INTEGER NOT NULL,
    content TEXT,               -- Zusammenfassung (bei 'text')
    selection_id INTEGER,       -- Verknuepfte Selection (bei 'selection')
    view_type TEXT,             -- 'list', 'table', 'cards', 'condensed'
    created_at TIMESTAMP
)
```

---

## Datenfluss

### Chat-Nachricht senden

```
1. Nutzer tippt Nachricht
   ↓
2. POST /api/messages?chatId=X
   Body: { "content": "Zeige aktive Mitglieder" }
   ↓
3. Backend:
   a) Speichert User-Nachricht
   b) Ruft AI mit System-Prompt auf
   c) AI antwortet mit JSON: { "message": "...", "selection": {...} }
   d) Speichert Assistant-Nachricht
   e) Falls Selection: erstellt Selection-Eintrag
   ↓
4. Frontend zeigt Nachricht + SelectionCard
```

### Selection zu Report hinzufuegen

```
1. Nutzer klickt "In Report uebernehmen"
   ↓
2. POST /api/chat/add-to-report
   Body: { "chatId": X, "selectionId": Y }
   ↓
3. Backend:
   a) Prueft ob Chat Report hat, sonst: erstellt Report
   b) Holt Chat-Historie und bestehende Report-Blocks
   c) Generiert AI-Zusammenfassung (Condensation)
   d) Erstellt Report-Block mit Zusammenfassung
   ↓
4. Frontend aktualisiert Report-Panel
```

### Selection duplizieren und bearbeiten

```
1. Nutzer klickt "Duplizieren & Bearbeiten"
   ↓
2. POST /api/selection/duplicate?id=X
   ↓
3. Backend erstellt Kopie mit Name + " (Kopie)"
   ↓
4. Frontend:
   a) Fuegt Duplikat zur Liste hinzu
   b) Oeffnet Edit-Modal mit dem Duplikat
   ↓
5. Nutzer aendert Filter/Name
   ↓
6. PUT /api/selection?id=Y
   ↓
7. Selection aktualisiert
```

---

## API-Endpoints

### Chat-Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/chats` | GET | Alle Chats auflisten |
| `/api/chats` | POST | Neuen Chat erstellen |
| `/api/chat?id=X` | GET | Einzelnen Chat holen |
| `/api/chat?id=X` | DELETE | Chat loeschen |
| `/api/messages?chatId=X` | GET | Alle Nachrichten eines Chats |
| `/api/messages?chatId=X` | POST | Nachricht senden (triggert AI) |
| `/api/chat/report?chatId=X` | GET | Report eines Chats holen |
| `/api/chat/add-to-report` | POST | Selection zu Chat-Report hinzufuegen |

### Selection-Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/selections` | GET | Alle Selections auflisten |
| `/api/selection?id=X` | GET | Einzelne Selection holen |
| `/api/selection` | POST | Neue Selection erstellen |
| `/api/selection?id=X` | PUT | Selection aktualisieren |
| `/api/selection?id=X` | DELETE | Selection loeschen |
| `/api/selection/duplicate?id=X` | POST | Selection duplizieren |
| `/api/selection/execute?id=X` | GET | Selection ausfuehren (Daten holen) |

### Report-Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/reports` | GET | Alle Reports auflisten |
| `/api/report?id=X` | GET | Report mit Blocks holen |
| `/api/report` | POST | Neuen Report erstellen |
| `/api/report?id=X` | DELETE | Report loeschen |
| `/api/report-blocks?reportId=X` | POST | Block zu Report hinzufuegen |
| `/api/report-block?id=X` | DELETE | Block loeschen |

---

## Frontend-Komponenten

### ChatView (`ChatView.tsx`)

Hauptkomponente fuer Chat-Interaktion.

**Struktur:**
- **Sidebar (links)**: Liste aller Chats, "New Chat" Button
- **Messages Area (mitte)**: Chat-Verlauf mit SelectionCards
- **Report Panel (rechts)**: Zusammenfassungen des Chat-Reports

**State:**
```typescript
const [chats, setChats] = useState<Chat[]>([])
const [activeChat, setActiveChat] = useState<Chat | null>(null)
const [messages, setMessages] = useState<Message[]>([])
const [chatReport, setChatReport] = useState<Report | null>(null)
```

### SelectionCard (`SelectionCard.tsx`)

Zeigt eine Selection mit expandierbaren Details.

**Features:**
- Expandierbar (Klick auf Header)
- Zeigt Filter und Ergebnisse
- View-Type Wechsel (Liste/Tabelle/Karten)
- Aktionen: "Duplizieren & Bearbeiten", "In Report uebernehmen"

**Props:**
```typescript
interface SelectionCardProps {
  selection: Selection
  onAddToReport?: () => void
  onSelectionUpdate?: (updated: Selection) => void
  onSelectionDuplicated?: (duplicate: Selection) => void
  showActions?: boolean
  isAddingToReport?: boolean
}
```

### SelectionEditModal (`SelectionEditModal.tsx`)

Modal zum Bearbeiten einer Selection.

**Features:**
- Name aendern
- Output-Type aendern
- Filter bearbeiten (typ-spezifische Felder)
- JSON-Vorschau der Filter

### ReportView (`ReportView.tsx`)

Zeigt alle Selections und Reports.

**Struktur:**
- **Sidebar (links)**: Liste aller Selections und Reports
- **Main Area (rechts)**: Ausgewaehlter Report mit Blocks

---

## AI-Integration

### System-Prompt (CatNose)

Der AI-Assistent erhaelt folgenden System-Prompt:

```
Du bist CatNose, ein Analyseassistent fuer Community-Daten von Skool.com.
Deine Aufgabe ist es, dem Nutzer bei der Exploration seiner Community-Daten zu helfen.

Wenn der Nutzer nach Daten fragt (z.B. "aktive Mitglieder", "beliebte Posts"),
erstelle eine Selektion. Eine Selektion ist eine strukturierte Datenabfrage.

Antworte IMMER im JSON-Format:
{
  "message": "Deine Erklaerung fuer den Nutzer",
  "selection": null oder {
    "name": "Beschreibender Name",
    "outputType": "member" oder "post" oder "community",
    "filters": { ... }
  }
}
```

### Selection-Namen (Titel)

Der AI-Assistent setzt automatisch den `name` der Selection basierend auf der Anfrage:
- "Zeige aktive Mitglieder" → `name: "Aktive Mitglieder"`
- "Posts mit vielen Likes" → `name: "Beliebte Posts"`

Der Name wird in der SelectionCard als Titel angezeigt.

### Condensation (Report-Zusammenfassung)

Beim Hinzufuegen einer Selection zum Report generiert die AI eine Zusammenfassung:
- Beruecksichtigt Chat-Kontext (warum wurde Selection erstellt?)
- Fasst Erkenntnisse zusammen
- 2-4 Saetze, professioneller Stil

---

## Warum "Duplizieren & Bearbeiten"?

Selections die vom Bot erstellt wurden, werden als "Original" behandelt:
- Sie bleiben unveraendert als Referenz
- Die Message-ID verknuepft sie mit der Bot-Antwort

Wenn der Nutzer Filter aendern will:
1. Selection wird dupliziert
2. Duplikat erhaelt `created_by: "user"`, `parent_id` verweist auf Original
3. Nutzer kann das Duplikat frei bearbeiten
4. Original bleibt erhalten

**Vorteile:**
- Audit-Trail: Man sieht was der Bot urspruenglich vorgeschlagen hat
- Vergleichbarkeit: Original vs. angepasste Version
- Keine versehentlichen Aenderungen an Bot-Selections

---

## Abgeleitete Selektionen (Baumstruktur)

Jede Selection kann abgeleitete Selektionen haben (durch Duplizieren entstanden).

**Datenbankschema:**
```sql
parent_id INTEGER REFERENCES selections(id) ON DELETE SET NULL
```

**Anzeige im Chat:**
```
┌─ CatNose-Nachricht ────────────────────────────────────┐
│                                                         │
│  "Hier ist eine Selektion fuer aktive Mitglieder..."   │
│                                                         │
│  ┌─ Original-Selection ─────────────────────────────┐  │
│  │  [Posts] Aktive Mitglieder (23 Ergebnisse)       │  │
│  │                                                   │  │
│  │  Filter: post_count_min: 5                        │  │
│  │  [Duplizieren & Bearbeiten] [In Report]          │  │
│  │                                                   │  │
│  │  Abgeleitete Selektionen (2)                     │  │
│  │  │                                                │  │
│  │  ├── Aktive Mitglieder (Kopie) - 15 Ergebnisse   │  │
│  │  │   Filter: post_count_min: 10                  │  │
│  │  │                                                │  │
│  │  └── Aktive Mitglieder (Kopie) - 5 Ergebnisse    │  │
│  │       Filter: post_count_min: 20                 │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**API-Response:**
```json
{
  "id": 1,
  "name": "Aktive Mitglieder",
  "outputType": "member",
  "parentId": null,
  "derivedSelections": [
    {
      "id": 2,
      "name": "Aktive Mitglieder (Kopie)",
      "parentId": 1,
      "derivedSelections": []
    }
  ]
}
```

**Wichtig:**
- Duplikate von Duplikaten verweisen immer auf das **Original** (nicht auf das direkte Parent)
- Nur Top-Level Selektionen (ohne `parent_id`) zeigen ihre abgeleiteten an
- Abgeleitete Selektionen werden eingerueckt dargestellt

---

## Views

| View | Pfad | Beschreibung |
|------|------|--------------|
| ChatView | `/` (Tab: Chat) | Hauptinteraktion mit AI |
| ReportView | `/reports` (Tab: Reports) | Alle Selections und Reports verwalten |
| FetchQueueView | `/queue` (Tab: Fetch Queue) | Daten-Fetching steuern |
| FetchesView | `/fetches` (Tab: Fetches) | Rohdaten inspizieren |
| LoggingView | `/logs` (Tab: Logs) | System-Logs |
| SettingsView | `/settings` (Tab: Settings) | Einstellungen |

---

## Beispiel-Workflow

```
1. Nutzer oeffnet Chat, tippt: "Welche Posts haben die meisten Likes?"

2. CatNose antwortet:
   "Ich habe eine Selektion fuer die beliebtesten Posts erstellt.
    Du kannst die Filter anpassen oder sie in deinen Report uebernehmen."

   [SelectionCard: "Beliebteste Posts"]
   - Typ: Posts
   - Filter: likes_min: 10
   - Ergebnisse: 23

3. Nutzer expandiert SelectionCard, sieht Posts-Liste

4. Nutzer klickt "Duplizieren & Bearbeiten"
   → Modal oeffnet sich mit dem Duplikat
   → Nutzer aendert likes_min auf 50
   → Speichert

5. Neue SelectionCard erscheint: "Beliebteste Posts (Kopie)"
   - Ergebnisse: 5

6. Nutzer klickt "In Report uebernehmen"
   → AI generiert Zusammenfassung
   → Report-Panel zeigt: "Die Top-5 Posts mit ueber 50 Likes zeigen..."
```
