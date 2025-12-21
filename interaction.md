Alles klar — ich fasse das jetzt **strukturiert, präzise und anschlussfähig an eure bestehende Architektur** zusammen.
Ich mache drei Dinge:

1. **Ein sauberes Markdown-Konzeptdokument** (so, dass du es direkt ins Repo legen kannst)
2. **Eine visuelle Architektur-Grafik (als Diagramm in Markdown/ASCII + Beschreibung für spätere Visualisierung)**
3. **Eine explizite Liste offener Fragen & Risiken**, technisch und produktseitig

Ich bleibe dabei **streng im CatKnows-Kontext** (lokal, DuckDB/SQLite, AI als Assistenz, nicht als Wahrheit).

---

# 📘 CatKnows – Chat-, Selections- & Report-Konzept

## 1. Ziel des Features

Dieses Feature erweitert CatKnows um eine **konversationsbasierte Analyseoberfläche**, die:

* den Nutzer über einen **AI-Chat** bei der Exploration seiner Community-Daten unterstützt
* **persistente Selektionen** (Posts, Members, Communities, …) erzeugt
* diese Selektionen **explizit sichtbar, nachvollziehbar und editierbar** macht
* aus explorativen Chats **strukturierte Reports** entstehen lässt

> **Der Chat ist der Weg.
> Der Report ist das Ergebnis.**

---

## 2. Zentrale Konzepte (Begriffsdefinitionen)

### 2.1 Chat

Ein **Chat** ist eine persistierte Konversation zwischen:

* Nutzer
* AI-Bot (CatNose / CatKnows-Context)

Eigenschaften:

* Mehrere Messages (User ↔ Bot)
* Jede Bot-Message **kann**:

  * keine Selektion erzeugen
  * **eine oder mehrere Selektionen erzeugen**
* Ein Chat ist immer **einem Report zugeordnet**

> Der Chat ist *explorativ*, nicht final.

---

### 2.2 Message

Eine **Message** ist ein einzelner Chat-Beitrag.

Typen:

* `user`
* `assistant`

Zusätzliche Eigenschaften bei `assistant`:

* optionale Referenzen auf:

  * erzeugte Selektionen
  * vorgeschlagene Views

---

### 2.3 Selektion (核心-Konzept)

Eine **Selektion** ist eine **persistierte, explizite Datenabfrage**.

#### Eigenschaften

* bezieht sich auf **genau einen Output-Typ**

  * `community`
  * `member`
  * `post`
  * (später erweiterbar)
* speichert:

  * **Filter-Definition (JSON)**
  * **Result-Snapshot**
  * **Metadaten**
* kann:

  * neu berechnet werden
  * dupliziert werden
  * manuell editiert werden
* ist **unabhängig vom Chat weiterverwendbar**

#### Konzeptuell:

```json
{
  "id": "selection_123",
  "output_type": "member",
  "filters": {
    "community_ids": ["abc"],
    "joined_after": "2024-01-01",
    "post_count_min": 3,
    "engagement_score_gt": 0.7
  },
  "result_snapshot": {
    "count": 42,
    "entity_ids": ["u1", "u2", "u3"]
  },
  "created_by": "assistant | user",
  "created_at": "..."
}
```

> **Die Selektion ist die Wahrheit, nicht der Prompt.**

---

### 2.4 View

Ein **View** definiert, **wie eine Selektion dargestellt wird**.

Eigenschaften:

* bezieht sich **immer auf genau eine Selektion**
* ist **persistiert**
* beschreibt **Darstellung, nicht Daten**
* benötigt bestimmte **Output-Typen**

Beispiele:

* `list_view` → `member | post | community`
* `table_view` → `member | post`
* `heatmap_view` → `member`
* `topic_cluster_view` → `post`

#### View-Validierung

Ein View ist nur auswählbar, wenn:

```
selection.output_type ∈ view.supported_output_types
```

---

### 2.5 Report

Ein **Report** ist ein **kuratierter, linearer Ergebnisraum**.

Er besteht aus einer Abfolge von **Blöcken**:

* Text / Beschreibung
* Selektion (+ ein oder mehrere Views)
* Text
* Selektion
* …

> **Mental Model: Jupyter Notebook, nicht Dashboard**

Eigenschaften:

* wird **manuell** vom Nutzer aufgebaut
* Chat-Selektionen können **explizit übernommen** werden
* Reihenfolge ist bedeutungsvoll
* vollständig persistiert

---

## 3. User Flow (End-to-End)

1. Nutzer startet einen neuen Chat
2. Nutzer stellt eine explorative Frage
   *„Welche Mitglieder sind besonders aktiv?“*
3. Bot antwortet:

   * erklärt kurz
   * **erzeugt eine Selektion**
4. UI zeigt:

   * Bot-Message
   * darunter: **Selection Card**
5. Nutzer kann:

   * Selektion inspizieren
   * View wechseln
   * Selektion duplizieren & editieren
6. Nutzer klickt:

   * **„In Report übernehmen“**
7. Report wächst schrittweise
8. Ergebnis:

   * Chat = Nachvollziehbarer Denkweg
   * Report = Verdichtete Antwort

---

## 4. Architektur – logisch

### 4.1 Komponenten-Übersicht

```
┌────────────┐
│   Chat UI  │
└─────┬──────┘
      │ Messages
      ▼
┌────────────┐        creates
│  AI Layer  │ ──────────────┐
└─────┬──────┘               │
      │                      ▼
      │              ┌────────────┐
      │              │ Selection  │◄──────┐
      │              └─────┬──────┘       │
      │                    │              │
      │                    ▼              │
      │              ┌────────────┐       │
      │              │   View     │       │
      │              └────────────┘       │
      │                                   │
      │         manual adopt              │
      └───────────────────────────────►┌────────────┐
                                        │   Report   │
                                        └────────────┘
```

---

### 4.2 Datenhaltung (konkret)

**SQLite (App-DB)**

Neue Tabellen (konzeptionell):

* `chats`
* `messages`
* `selections`
* `views`
* `reports`
* `report_blocks`

**DuckDB (Raw-DB)**

* bleibt **unverändert**
* wird von Selektionen gelesen
* keine Reports / Views / Chat-Artefakte

---

## 5. Rolle der AI

Die AI ist:

* **kein magischer Query-Layer**
* **kein Ersatz für explizite Modelle**

Sondern:

* Übersetzer von:

  * natürlicher Sprache → Selektion-JSON
* Erklärer von:

  * *warum* diese Selektion sinnvoll ist
* Vorschläger von:

  * passenden Views
  * nächsten Analyse-Schritten

> **Alle Ergebnisse müssen ohne AI reproduzierbar sein.**

---

## 6. Zentrale Design-Prinzipien

1. **Explizit > Implizit**
2. **Persistenz > Ephemerität**
3. **Editierbarkeit > Autorität**
4. **Chat erklärt – Selektion entscheidet**
5. **Report ist Produkt, Chat ist Prozess**
