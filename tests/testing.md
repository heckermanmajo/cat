# Testing

## Übersicht

Die Test-Suite testet die API-Logik (Filter, Queries, Export) gegen den laufenden Server.
Tests werden via `pytest` ausgeführt und kommunizieren mit der App über HTTP-Requests.

## Test-Scripts

```bash
./test_fast.sh          # Schnell: Tests gegen Python-Source
./test_fast.sh -v       # Verbose output
./test_fast.sh -k "role" # Nur Tests mit "role" im Namen

./test.sh               # Voll: Nuitka-Build + Tests gegen Executable
./test.sh --skip-build  # Build überspringen, existierende Binary nutzen
```

## Struktur

```
tests/
├── conftest.py           # Fixtures: API-Client, Server-Wait, DB-Reset
├── data_builder.py       # Synthetische Testdaten generieren
├── requirements.txt      # pytest, requests
├── test_filter_basic.py  # Grundlegende Include/Exclude Tests
├── test_filter_role.py   # member_role Filter
├── test_filter_dates.py  # active_since, inactive_since, joined_*
├── test_filter_points.py # points_min, points_max
├── test_filter_search.py # searchTerm Funktionalität
├── test_filter_sort.py   # sortBy Varianten
└── test_export.py        # CSV Export
```

## Test-Endpunkte

Die App stellt Test-Endpunkte bereit (`myversion/routes/test_routes.py`):

| Endpoint | Beschreibung |
|----------|--------------|
| `POST /api/test/reset` | Löscht alle Daten (für Test-Setup) |
| `POST /api/test/bulk-users` | Mehrere User auf einmal einfügen |
| `POST /api/test/bulk-posts` | Mehrere Posts auf einmal einfügen |
| `POST /api/test/bulk-likes` | Mehrere Likes auf einmal einfügen |
| `POST /api/test/bulk-profiles` | Mehrere Profile auf einmal einfügen |
| `POST /api/test/bulk-fetches` | Mehrere Fetch-Records einfügen |
| `POST /api/test/set-community` | Aktuelle Community setzen |

## Neue Tests schreiben

1. **Test-Datei erstellen** in `tests/test_*.py`
2. **DataBuilder nutzen** für Testdaten:

```python
from data_builder import DataBuilder

def test_example(api, clean_db):
    # Setup
    builder = DataBuilder(api)
    builder.with_community('test-comm')
    builder.with_fetch('members')
    builder.with_specific_user(role='admin', points=1000)
    builder.with_users(10)  # 10 random users
    builder.build()

    # Test
    users = api.filter_users({
        'communitySlug': 'test-comm',
        'include': {'member_role': 'admin'},
        'exclude': {}
    })

    # Assert
    assert len(users) == 1
    assert users[0]['member_role'] == 'admin'
```

3. **Fixtures nutzen**:
   - `api` - API-Client mit Helper-Methoden
   - `clean_db` - Resettet DB vor jedem Test

## DataBuilder Methoden

```python
builder = DataBuilder(api)
builder.with_community('slug')           # Community setzen
builder.with_fetch('members')            # Fetch-Record erstellen
builder.with_users(count)                # N zufällige User
builder.with_specific_user(              # User mit spezifischen Attributen
    role='admin',
    points=1000,
    last_active_days_ago=5,
    joined_days_ago=30,
    skool_id='custom_id'
)
builder.build()                          # Alles in DB einfügen
```

## API-Client Methoden

```python
api.reset()                              # DB leeren
api.set_community('slug')                # Community setzen
api.filter_users(filter_state)           # User filtern
api.bulk_users([...])                    # User einfügen
api.get('/api/endpoint')                 # GET Request
api.post('/api/endpoint', json={...})    # POST Request
```
