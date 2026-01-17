Perfekt – dann hier etwas, das du **1:1 einem Coding-Agent (oder Entwickler)** geben kannst:
eine **klare Checkliste** + ein **konkreter, umsetzbarer Arbeitsplan** für Chrome & Firefox.

---

# ✅ CHECKLISTE — „Extension ready für Beta & Release“

Diese Liste ist so formuliert, dass ein Agent sie **abhaken** kann.

---

## 🔒 A. Technische & Architektur-Checks

* [ ] Manifest ist valide (Chrome & Firefox)
* [ ] Manifest V3 kompatibel
* [ ] Nur notwendige Permissions definiert
* [ ] Keine toten Dateien / Testcodes
* [ ] Keine `eval`, keine remote Scripts
* [ ] Service Worker / Background stabil
* [ ] Fehler-Logging eingebaut
* [ ] Extension startet ohne Console Errors
* [ ] Funktioniert im frischen Browser-Profil

---

## 🌍 B. Cross-Browser-Kompatibilität

* [ ] Getestet in aktuellem Chrome
* [ ] Getestet in aktuellem Firefox
* [ ] `browser.*` API oder Polyfill genutzt
* [ ] Storage, Messaging, Injects geprüft
* [ ] Keine Chrome-only APIs (oder sauber gefallbackt)
* [ ] Build-Unterschiede dokumentiert

---

## 🧪 C. Beta-Readiness

* [ ] Versionsschema definiert (z. B. 0.1.x-beta)
* [ ] Logging aktivierbar
* [ ] Feature-Flags optional
* [ ] Feedback-Kanal definiert
* [ ] Installationsanleitung für Tester

---

## 🧹 D. Review- & Security-Readiness

* [ ] Unnötige Permissions entfernt
* [ ] Datenschutzerklärung geschrieben
* [ ] Klartext-Beschreibung der Funktionen
* [ ] Datenflüsse dokumentiert
* [ ] Kein Tracking ohne Offenlegung
* [ ] Keine irreführenden Claims

---

## 🏪 E. Store-Assets

* [ ] Name final
* [ ] Kurzbeschreibung (1–2 Sätze)
* [ ] Lange Beschreibung (klar & technisch korrekt)
* [ ] Icons: 16, 48, 128 px
* [ ] Mind. 2 Screenshots
* [ ] Privacy-Policy-URL
* [ ] Support-Kontakt

---

## 🚀 F. Release-Prozess

* [ ] Chrome-ZIP-Build
* [ ] Firefox-ZIP/XPI-Build
* [ ] Unlisted in beiden Stores hochgeladen
* [ ] Beta-Link getestet
* [ ] Update-Workflow definiert
* [ ] Public-Release-Kriterien festgelegt

---

# 🗺️ UMSETZUNGSPLAN — „Agenten-Arbeitsauftrag“

Den folgenden Block kannst du praktisch direkt weitergeben.

---

## 🎯 Ziel

Das bestehende Browser-Plugin soll:

1. Chrome & Firefox-kompatibel sein
2. als **Unlisted Beta** in beiden Stores verfügbar sein
3. technisch, sicherheitlich und formal **review-ready** sein

---

## 🧩 Phase 1 — Audit & Stabilisierung (Pflicht)

**Deliverables:**

* Audit-Dokument
* Bereinigtes Plugin
* Fix-Liste

**Tasks:**

* Codebase prüfen
* Manifest validieren
* Permissions minimieren
* Console-Errors eliminieren
* Dead Code entfernen
* Fehler-Logging einbauen
* Frisches Profil testen

---

## 🌍 Phase 2 — Cross-Browser-Fixes

**Deliverables:**

* Chrome-Build
* Firefox-Build
* Kompatibilitätsnotizen

**Tasks:**

* Firefox-Tests durchführen
* API-Unterschiede beheben
* browser/chrome Abstraction einbauen
* Storage & Messaging absichern
* CSP-Fehler beheben

---

## 🧪 Phase 3 — Beta-Build & Testpakete

**Deliverables:**

* Version 0.x-beta
* Install-Guide
* Changelog

**Tasks:**

* Versionierung setzen
* Build-Skripte anlegen (Chrome/Firefox)
* ZIP-Pakete erzeugen
* Beta-Feedback-Hooks einbauen

---

## 🧹 Phase 4 — Review-Vorbereitung

**Deliverables:**

* Privacy-Policy-Text
* Store-Texte
* Bereinigtes Manifest

**Tasks:**

* Datenflüsse dokumentieren
* Store-konforme Beschreibung schreiben
* Screenshots anfordern/erstellen
* Permission-Begründungen formulieren

---

## 🏪 Phase 5 — Store-Submission (Unlisted)

**Deliverables:**

* Chrome-Store-Eintrag (unlisted)
* Firefox-Add-on-Eintrag (unlisted)
* Install-Links

**Tasks:**

* Developer-Dashboards einrichten
* Builds hochladen
* Unlisted-Status setzen
* Review-Feedback verarbeiten

---

## 🔁 Phase 6 — Beta-Iteration

**Deliverables:**

* Bugfix-Releases
* Stabiler Release-Kandidat

**Tasks:**

* Feedback auswerten
* Crash-Fixes priorisieren
* Permissions weiter reduzieren
* Performance prüfen

---

## 🚀 Phase 7 — Public Release

**Deliverables:**

* Version 1.0
* Public-Store-Einträge
* Wartungsplan

**Tasks:**

* Beschreibungen finalisieren
* Visibility auf Public setzen
* Monitoring einrichten
* Update-Roadmap definieren

---

# ⚠️ Kritische Review-No-Gos (für Agent sehr wichtig)

* ❌ Remote nachgeladener Code
* ❌ Irreführende Beschreibung
* ❌ Zu breite Permissions
* ❌ Obfuskierter Kerncode
* ❌ Undokumentierte Datensammlung

---

# 🧠 Optionaler Zusatzauftrag an den Agenten

* Automatischer Build (npm script)
* Manifest-Splitter (Chrome/Firefox)
* Minimal-Telemetry (opt-in)
* Crash-Reporter

---

Wenn du willst, kann ich dir das auch noch als:

* 📄 **saubere Projekt-Spec (PDF-artig)**
* 🧑‍💻 **Prompt für einen AI-Coding-Agent**
* ✅ **Notion/Jira-Ticket-Struktur**

formulieren.
