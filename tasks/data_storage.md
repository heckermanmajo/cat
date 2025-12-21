```md
# Architektur-Entscheidung: Datenhaltung (Rohdaten vs. Anwendungsdaten)

## Kontext / Problemstellung

Die Anwendung läuft vollständig **lokal beim Endnutzer** und verarbeitet Daten, die über eine Browser-Extension aus externen Web-Quellen (z. B. Skool) geladen werden.  
Diese Daten liegen **roh, groß, stark genestet und JSON-basiert** vor und können sich über die Zeit mehrfach aktualisieren (Fetch-Historie).

Gleichzeitig erzeugt die Anwendung **eigene Daten**, z. B.:

- UI-State (Tabs, letzte Auswahl, etc.)
- User-Settings
- Lizenz- und App-Metadaten
- Analyse-Ergebnisse / Reports
- gespeicherte Filter, Suchanfragen, Quicklinks
- Pro-User-Features

Bisherige Überlegungen zeigten:
- Das Extrahieren und Synchronisieren von Rohdaten in eigene Tabellen (z. B. `members`, `posts`) erzeugt hohe Komplexität, Fehleranfälligkeit und Wartungsaufwand.
- Viele „abgeleitete“ Strukturen werden eigentlich nur benötigt, um aktuelle Zustände abzufragen – was auch direkt aus den Rohdaten möglich ist.

Ziel ist:
- **Komplexität reduzieren**
- **Stabilität erhöhen**
- **Flexibilität für zukünftige Analysen behalten**
- Performance lokal (bis ca. 10.000 Nutzer / Events sicherstellen)

---

## Entscheidung

Wir trennen die Datenhaltung **konsequent nach Verantwortung**:

### 1. DuckDB → Rohdaten & direkte Abfragen

**DuckDB wird verwendet für:**
- alle roh geladenen Daten (Fetches)
- Speicherung als **JSON, unverändert**
- Append-only / versioniert (mehrere Fetches pro Entität erlaubt)
- direkte Abfragen auf Rohdaten (inkl. tiefem JSON-Nesting)

Beispiele:
- neuester Member-Fetch pro Member-ID
- Aggregationen über Posts / Kommentare
- Analysen direkt auf Rohdaten ohne vorherige Extraktion

DuckDB ist dabei **nicht nur Archiv**, sondern aktive Query-Engine.

---

### 2. SQLite → Anwendungs- & Produktdaten

**SQLite wird verwendet für alles, was die Anwendung selbst erzeugt oder verwaltet**, insbesondere:

- UI-State
- User- & App-Settings
- Lizenz- und Meta-Informationen
- Analyse-Ergebnisse / Reports (Snapshots)
- gespeicherte Filter, Suchanfragen, Quicklinks
- Feature-spezifische, mutable Daten

Diese Daten sind:
- stark UI-nah
- häufig geändert
- klar strukturiert
- nicht Teil der „Rohdaten-Wahrheit“

---

## Leitprinzip

> **Rohdaten bleiben roh und unverändert.  
Der „aktuelle Zustand“ wird abgefragt, nicht synchronisiert.  
Persistiert wird nur, was ein bewusstes Produkt-Artefakt ist.**

---

## Auftrag / Implementierungsanweisung (für AI-Agenten)

Bei Aufbau und Weiterentwicklung der Kernanwendung ist folgendes umzusetzen:

1. **DuckDB integrieren**
   - als lokale, embedded Datenbank
   - für alle Fetches und Rohdaten
   - JSON-first, keine erzwungene Extraktion in eigene Entitätstabellen

2. **SQLite integrieren**
   - für App-State, Settings, Reports, gespeicherte Nutzerinteraktionen
   - klassische relationale Nutzung

3. **Keine redundanten Datenmodelle**
   - keine dauerhafte Ableitung von `Member`, `Post`, etc. aus Rohdaten
   - aktueller Zustand = Query auf DuckDB

4. **Dokumentation aktualisieren**
   - klare Trennung: *Raw Data Layer (DuckDB)* vs. *App Data Layer (SQLite)*
   - Begründung dieser Entscheidung festhalten

5. **Architektur & Code darauf ausrichten**
   - Analyse-Logik bevorzugt auf Rohdaten
   - Persistenz nur dort, wo sie fachlich notwendig ist

Diese Entscheidung ist **bewusst, final und grundlegend** für die weitere Infrastruktur- und Feature-Entwicklung.
```
