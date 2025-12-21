# Lizenz-Mechanismus

## Übersicht

Der Lizenz-Mechanismus stellt sicher, dass nur zahlende Kunden die Software nutzen können. Er basiert auf **kryptographischen Signaturen**, die eine Manipulation der Lizenz-Prüfung verhindern.

## Warum nicht einfach HTTP?

Ein naiver Ansatz wäre:
1. Client fragt Server: "Ist Lizenz XYZ gültig?"
2. Server antwortet: `{"valid": true}`
3. Client akzeptiert

**Problem**: Ein Angreifer kann:
- `/etc/hosts` manipulieren → eigener Fake-Server
- Immer `{"valid": true}` zurückgeben
- Lizenz umgangen

## Die Lösung: Ed25519 Signaturen

### Grundprinzip

```
┌─────────────────────────────────────────────────────────┐
│                    SERVER (geheim)                      │
│                                                         │
│   Private Key: nur Server kennt ihn                     │
│   signiert: "license valid until 2025-12-31"            │
│   erzeugt: SIGNATUR (nur mit Private Key möglich)       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              { data: "...", signature: "xyz..." }
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 GO-CLIENT (öffentlich)                  │
│                                                         │
│   Public Key: im Binary eingebettet                     │
│   verifiziert: Signatur passt zu Daten?                 │
│   → JA: Lizenz gültig                                   │
│   → NEIN: Manipulation erkannt, ablehnen                │
└─────────────────────────────────────────────────────────┘
```

**Warum funktioniert das?**
- Angreifer kann Fake-Server aufsetzen
- Angreifer kennt Private Key **nicht**
- Kann keine gültige Signatur erstellen
- Client lehnt ungültige Signaturen ab

### Zusätzliche Sicherheit: Nonce & Timestamp

**Nonce** (Number used once):
- Client generiert Zufallszahl bei jedem Request
- Server muss diese in der Antwort zurückgeben
- Verhindert **Replay-Angriffe** (alte gültige Antworten wiederverwenden)

**Timestamp**:
- Server fügt aktuelle Zeit hinzu
- Client akzeptiert nur Antworten < 5 Minuten alt
- Verhindert Nutzung alter abgefangener Antworten

## Kommunikationsfluss

```
┌─────────────┐                              ┌─────────────┐
│  Go-Client  │                              │   Server    │
└──────┬──────┘                              └──────┬──────┘
       │                                            │
       │  1. Generiere Nonce (Zufallszahl)          │
       │                                            │
       │  2. POST /api/license/validate.php         │
       │     {                                      │
       │       license_key: "XXXX-XXXX-...",        │
       │       nonce: "a7f9b2c8...",                │
       │       machine_id: "hash..."                │
       │     }                                      │
       │ ─────────────────────────────────────────► │
       │                                            │
       │                              3. Lizenz prüfen in DB
       │                              4. Payload erstellen
       │                              5. Mit Private Key signieren
       │                                            │
       │     {                                      │
       │       payload: {                           │
       │         valid: true,                       │
       │         expires_at: "2025-12-31",          │
       │         nonce: "a7f9b2c8...",  ← gleich!   │
       │         timestamp: 1702400000              │
       │       },                                   │
       │       signature: "ed25519_sig..."          │
       │     }                                      │
       │ ◄───────────────────────────────────────── │
       │                                            │
       │  6. Signatur verifizieren (Public Key)     │
       │  7. Nonce prüfen (muss übereinstimmen)     │
       │  8. Timestamp prüfen (< 5 min alt)         │
       │  9. Bei Erfolg: Cache lokal speichern      │
       │                                            │
```

## Dateien & Struktur

### Server (PHP)

```
webserver/
├── api/
│   └── license/
│       └── validate.php      # Haupt-API-Endpunkt
├── config/
│   ├── database.php          # DB-Verbindung
│   └── keys.php              # Private/Public Keys laden
├── scripts/
│   ├── generate-keys.php     # Schlüsselpaar generieren
│   └── create-license.php    # Neue Lizenz erstellen
└── setup.sql                 # Datenbank-Schema
```

### Client (Go)

```
go-client/
└── license/
    └── license.go            # Lizenz-Manager mit Verifikation
```

## Setup-Anleitung

### 1. Schlüssel generieren

```bash
cd webserver
php scripts/generate-keys.php --save
```

Output:
```
PRIVATE KEY: a1b2c3d4... (128 hex chars)
PUBLIC KEY:  e5f6a7b8... (64 hex chars)
```

### 2. Server konfigurieren

Environment-Variablen setzen:
```bash
export LICENSE_PRIVATE_KEY="a1b2c3d4..."
export LICENSE_PUBLIC_KEY="e5f6a7b8..."
```

Oder in `.env` Datei (NICHT committen!):
```
LICENSE_PRIVATE_KEY=a1b2c3d4...
LICENSE_PUBLIC_KEY=e5f6a7b8...
```

### 3. Public Key in Go-Client einbetten

In `go-client/license/license.go`:
```go
var ServerPublicKey = mustDecodeHex("e5f6a7b8...") // 64 hex chars
```

### 4. Datenbank einrichten

```bash
mysql -u root -p < webserver/setup.sql
```

### 5. Test-Lizenz erstellen

```bash
php scripts/create-license.php --email="test@example.com" --months=12
```

## Datenbank-Schema

### licenses

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| id | INT | Primary Key |
| license_key | VARCHAR(64) | Einzigartiger Schlüssel (XXXX-XXXX-XXXX-XXXX) |
| customer_email | VARCHAR(255) | Kunden-Email |
| valid_until | DATE | Ablaufdatum |
| is_active | BOOLEAN | Lizenz aktiv/deaktiviert |
| max_activations | INT | Max. erlaubte Geräte |
| features | JSON | Freigeschaltete Features |

### activations

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| license_id | INT | FK zu licenses |
| machine_id | VARCHAR(255) | Hash der Hardware-ID |
| last_seen | TIMESTAMP | Letzter Check von diesem Gerät |

## Offline-Verhalten

Der Client cached Lizenz-Antworten lokal in SQLite:

1. **Online-Check** alle 24 Stunden
2. **Offline-Grace-Period**: 7 Tage
3. Nach 7 Tagen ohne Server-Kontakt: Lizenz ungültig

```go
// In license.go
checkInterval: 24 * time.Hour  // Normale Prüfung
gracePeriod:   7 * 24 * time.Hour  // Offline erlaubt
```

## Sicherheitsanalyse

| Angriff | Schutz | Status |
|---------|--------|--------|
| Fake-Server aufsetzen | Signatur ungültig ohne Private Key | ✅ Geschützt |
| Response manipulieren | Signatur wird ungültig | ✅ Geschützt |
| Alte Response wiederverwenden | Nonce stimmt nicht überein | ✅ Geschützt |
| Response abfangen & später nutzen | Timestamp zu alt | ✅ Geschützt |
| Binary patchen (Public Key ändern) | Schwer zu verhindern | ⚠️ Teilschutz |
| Binary cracken (Check entfernen) | Schwer zu verhindern | ⚠️ Teilschutz |

**Realität**: 100% Schutz gegen Binary-Manipulation gibt es nicht. Aber:
- Erfordert Reverse-Engineering-Kenntnisse
- Muss bei jedem Update wiederholt werden
- Für 99% der Nutzer ausreichender Schutz

## API-Referenz

### POST /api/license/validate.php

**Request:**
```json
{
  "license_key": "XXXX-XXXX-XXXX-XXXX",
  "nonce": "64_hex_chars_random",
  "machine_id": "sha256_of_hardware_id"
}
```

**Response (Erfolg):**
```json
{
  "payload": {
    "valid": true,
    "expires_at": "2025-12-31",
    "nonce": "64_hex_chars_same_as_request",
    "timestamp": 1702400000,
    "product": "catknows",
    "features": ["basic", "analytics", "ai"]
  },
  "signature": "128_hex_chars_ed25519_signature"
}
```

**Response (Fehler):**
```json
{
  "payload": {
    "valid": false,
    "expires_at": "",
    "nonce": "...",
    "timestamp": 1702400000,
    "error": "invalid_license"
  },
  "signature": "..."
}
```

Mögliche Fehler:
- `invalid_license` - Lizenzschlüssel nicht gefunden
- `license_expired` - Lizenz abgelaufen
- `license_deactivated` - Lizenz deaktiviert

## Entwicklung & Testing

Für lokale Entwicklung wird `api.cat-knows.com` verwendet, damit immer unter realen Bedingungen getestet wird.

Test-Lizenz in der Datenbank:
```
Schlüssel: DEV-TEST-LICENSE-2024
Email: dev@catknows.local
Gültig: 1 Jahr ab Installation
Features: basic, analytics, ai, dev
```
