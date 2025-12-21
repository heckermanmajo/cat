Alles klar 👍
Ich schreibe das jetzt so, **dass es direkt als Markdown-Dokument ins Repository kann** und eine andere Person damit **ohne Rückfragen** arbeiten kann.

Ich halte es:

* **konzeptionell klar**
* **technisch konkret**
* **ohne unnötigen Overengineering**
* **ohne vollständige Implementierung**

---

# Self-Update-Mechanismus für die Go-Executable

## 1. Ziel & Kontext

### 1.1 Ausgangssituation

Unsere Anwendung ist:

* ein **kleines SaaS**
* implementiert als **eine einzelne Go-Executable**
* inklusive:

  * Backend-Logik
  * eingebettetem Webfrontend
* wird **direkt an Kunden distribuiert** (kein Installer, kein App Store)

Die Anwendung läuft lokal beim Kunden und kommuniziert mit einem Server.

### 1.2 Problemstellung

Da die Anwendung als einzelne Executable ausgeliefert wird, benötigen wir einen Mechanismus, um:

* neue Versionen auszurollen
* Updates einfach und zuverlässig beim Kunden zu installieren
* ohne Installer
* ohne externe Update-Frameworks
* ohne komplexe Infrastruktur

Gleichzeitig soll das Update-System:

* **robust**
* **plattformübergreifend (Windows, Linux, macOS)**
* **einfach verständlich**
* **leicht wartbar**

sein.

---

## 2. Ziel des Update-Systems

Das Update-System soll:

1. prüfen, ob eine neue Version verfügbar ist
2. dem Nutzer anzeigen, dass ein Update existiert
3. die neue Version im Hintergrund herunterladen
4. das Update **erst beim Neustart anwenden**
5. alte Versionen optional sichern (Rollback-Möglichkeit)
6. zwischen **Stable**- und **Nightly**-Versionen unterscheiden

Wichtig:

* Die aktuell laufende Anwendung darf **nicht abrupt beendet oder ersetzt** werden
* Das System muss **auch unter Windows** zuverlässig funktionieren

---

## 3. Grundidee des Update-Ansatzes

### 3.1 Prinzip: Zwei-Phasen-Update

Der Update-Prozess wird in **zwei klar getrennte Phasen** unterteilt:

#### Phase 1 – Update vorbereiten

* läuft während die App normal genutzt wird
* lädt die neue Version herunter
* ersetzt **noch nichts**

#### Phase 2 – Update anwenden

* erfolgt beim Neustart der Anwendung
* alte Version wird ersetzt
* neue Version wird gestartet

Dieses Vorgehen ist:

* einfach
* robust
* plattformunabhängig
* Standard in vielen Self-Updating-Systemen

---

## 4. Versionierung & Release-Kanäle

### 4.1 Release-Kanäle

Es gibt zwei Release-Kanäle:

* **stable**

  * für normale Nutzer
  * seltene, getestete Updates
* **nightly**

  * für Tester
  * häufige, experimentelle Updates

### 4.2 Kanal-Auswahl

* Die Entscheidung für einen Kanal wird **nicht serverseitig pro Nutzer getroffen**
* Stattdessen:

  * Es existieren zwei unterschiedliche Distributionsvarianten
  * Der Nutzer entscheidet selbst, ob er Stable oder Nightly nutzt
* Jede Variante fragt **ausschließlich ihren eigenen Kanal** ab

Beispiel:

* Stable-App → fragt `/updates/stable`
* Nightly-App → fragt `/updates/nightly`

---

## 5. Update-Server (Backend)

### 5.1 Server-Typ

* einfacher **Vanilla-PHP-Server**
* kein Framework
* kein Authentifizierungssystem nötig

### 5.2 Aufgabe des Servers

Der Server liefert:

* die aktuellste Version pro Kanal
* eine Download-URL zur neuen Executable
* optionale Metadaten (z. B. Hash, Changelog)

### 5.3 Beispielhafte Server-Antwort

```json
{
  "channel": "stable",
  "latest_version": "1.4.3",
  "download_url": "https://example.com/downloads/myapp-1.4.3.exe",
  "sha256": "…",
  "changelog": "Bugfixes und Performance-Verbesserungen"
}
```

---

## 6. Ablauf im Detail

### 6.1 Update-Prüfung

Beim Start der Anwendung (oder periodisch):

1. Die App kennt:

   * ihre aktuelle Version
   * ihren Release-Kanal (stable / nightly)
2. Sie sendet eine Anfrage an den Update-Endpunkt
3. Der Server antwortet mit der neuesten Version
4. Die App vergleicht:

   * lokale Version vs. Server-Version

---

### 6.2 Nutzerinteraktion

Wenn eine neue Version verfügbar ist:

* Anzeige im Webfrontend:

  * „Neue Version verfügbar“
  * Version
  * Changelog (optional)
* Nutzer kann:

  * Update jetzt herunterladen
  * oder ignorieren

---

### 6.3 Phase 1 – Update vorbereiten

Nach Zustimmung des Nutzers:

1. Die neue Executable wird heruntergeladen
2. Sie wird **nicht direkt installiert**
3. Sie wird z. B. gespeichert als:

```
myapp.new
```

oder in einem Update-Verzeichnis:

```
updates/myapp_1.4.3
```

Optional:

* Überprüfung des Hashes zur Integritätskontrolle

Ergebnis dieser Phase:

* Die neue Version liegt lokal bereit
* Die aktuell laufende Version bleibt unverändert aktiv

---

## 7. Phase 2 – Update anwenden (beim Neustart)

### 7.1 Problem: Selbst-Ersetzung

* Eine laufende Executable kann sich **nicht selbst ersetzen**
* Besonders unter Windows ist die Datei gesperrt

### 7.2 Lösung: Neustart mit Update-Modus

Die Anwendung enthält eine spezielle Start-Option:

```
--apply-update
```

Die Logik ist Teil derselben Executable.

---

### 7.3 Ablauf beim Anwenden des Updates

1. Die laufende Anwendung startet **sich selbst erneut** mit `--apply-update`
2. Die Hauptanwendung beendet sich
3. Der neue Prozess läuft ohne File-Lock
4. Dieser Prozess:

   * verschiebt die aktuelle Version nach `myapp.old`
   * verschiebt die neue Version an die ursprüngliche Position
5. Danach startet er die neue Version normal
6. Der Update-Prozess beendet sich

---

## 8. Dateistruktur & Rollback

### 8.1 Empfohlene Struktur

```
myapp.exe
myapp.old
myapp.new
```

oder plattformneutral:

```
myapp
myapp.old
myapp.new
```

### 8.2 Rollback-Idee

* Falls die neue Version nicht startet:

  * beim nächsten Start kann erkannt werden:

    * neue Version fehlerhaft
  * alte Version (`.old`) kann wiederhergestellt werden

Rollback ist optional, aber einfach möglich.

---

## 9. Was wir mit diesem Ansatz erreichen

✔ sehr simples Update-System
✔ keine externen Abhängigkeiten
✔ funktioniert auf allen Betriebssystemen
✔ kein Installer notwendig
✔ kontrollierte Updates
✔ klare Trennung zwischen Stable & Nightly
✔ leicht verständlich für neue Entwickler

---

## 10. Bewusst nicht Teil dieses Konzepts

Dieses Dokument behandelt **nicht**:

* Delta-Updates
* Installer / MSI / DMG
* Benutzer-spezifische Update-Freigaben
* Auto-Rollouts oder Staged Deployments
* Komplexe Signatur-Infrastrukturen

Diese Dinge sind **bewusst ausgeschlossen**, um das System einfach und robust zu halten.

---

## 11. Zusammenfassung

Das Update-System basiert auf:

* einer einzelnen Go-Executable
* einem simplen Server-Endpunkt
* einem Zwei-Phasen-Update-Prozess
* klar getrennten Release-Kanälen

Es ist **minimal**, **robust** und **leicht wartbar** – ideal für ein kleines SaaS mit direkter Distribution.
