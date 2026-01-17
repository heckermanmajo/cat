# Card View vs List View - Ideen

## Aktueller Stand
- `list` view: Kompakte `<article>` Elemente - Name, Role, Points, Dates
- `card` view: Das gleiche, aber mit Raw JSON (minimal anders)
- `graph` view: Vis.js Netzwerk-Visualisierung

Der Unterschied zwischen List und Card ist aktuell minimal.

---

## List View - kompakt, scanbar

**Ideal für:** Schnelles Durchscrollen großer Mengen

- Einzeilig/zweizeilig pro Member
- Nur Kerninfos: Name, Role, Points, Last Active
- Kleine/keine Profilbilder
- Tabellenartig oder sehr schmale Karten
- Checkbox-Selektion für Bulk-Aktionen

---

## Card View - visuell, detailreich

**Ideal für:** Tiefere Analyse einzelner Personen

### 1. Profilbild prominent
- Größeres Bild, evtl. von Skool-Profil gefetcht
- Visuelles Erkennen von Personen

### 2. Quick-Stats als Mini-Charts
- Kleiner Activity-Sparkline (Posts letzte 30 Tage)
- Engagement-Score als farbiger Balken
- "Trend" Pfeil (aktiver/weniger aktiv als vorher)

### 3. Community-Badges
- Zeige andere Communities als kleine Icons/Chips
- Schneller Überblick wo die Person noch aktiv ist

### 4. Social Proof Indikatoren
- "Top 10% Points"
- "Aktiv in 5 Communities"
- "Posted this week"

### 5. Action-Buttons direkt auf der Karte
- "View Posts"
- "Add to List"
- "View Profile on Skool" (External Link)

### 6. Grid-Layout statt vertikale Liste
- 2-4 Cards nebeneinander
- Pinterest-Style Masonry wenn Inhalte unterschiedlich groß

### 7. "Highlight" Karten
- Besondere Members farblich hervorheben
- z.B. Admins golden, Neue grün, Inaktive grau

### 8. Bio/About Snippet
- Kurze Preview der Skool-Bio wenn vorhanden

---

## Weitere View-Ideen

- **Table View**: Echte Tabelle, sortierbar durch Klick auf Spalten
- **Kanban View**: Members gruppiert nach Status (z.B. nach Role oder Activity-Level)
- **Timeline View**: Members nach Join-Datum auf Zeitstrahl

---

## Empfehlung

Card View mit Grid-Layout + Profilbild + Community-Badges würde den größten praktischen Unterschied zum List View bieten.
