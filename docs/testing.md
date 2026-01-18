# Testing Guide

This document describes how the testing system works and how to write tests.

## Overview

The test suite uses **API-based testing**: tests communicate with the running Flask server via HTTP requests. This approach tests the full stack (routes, models, database) without mocking.

```
┌──────────────────────────────────────────────────────────────────┐
│                          Test Process                             │
│                                                                   │
│  ┌──────────────┐        HTTP        ┌──────────────────────┐    │
│  │   pytest     │ ──────────────────▶│   Flask Server       │    │
│  │              │                    │   (Python or Binary) │    │
│  │  - conftest  │ ◀────────────────  │                      │    │
│  │  - fixtures  │        JSON        │   ┌──────────────┐   │    │
│  │  - tests     │                    │   │   SQLite     │   │    │
│  └──────────────┘                    │   │  (test.db)   │   │    │
│                                      │   └──────────────┘   │    │
│                                      └──────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Run all tests (fast, against Python source)
./test_fast.sh

# Run with verbose output
./test_fast.sh -v

# Run specific tests
./test_fast.sh -k "role"           # tests with "role" in name
./test_fast.sh tests/test_filter_basic.py  # specific file

# Run full tests (build Nuitka binary first)
./test.sh

# Skip build, use existing binary
./test.sh --skip-build
```

## Test Scripts

### `test_fast.sh` - Development Testing

Fast iteration during development:

1. Creates Python venv in `tests/.venv`
2. Installs pytest + requests
3. Starts Flask server from Python source on port 3099
4. Runs pytest against the server
5. Cleans up (kills server, removes test DB)

### `test.sh` - Full Integration Testing

Tests against compiled binary:

1. Builds executable with Nuitka (`myversion/build.py`)
2. Starts compiled binary
3. Runs pytest
4. Cleans up

## Test Structure

```
tests/
├── conftest.py            # Fixtures: api client, clean_db
├── data_builder.py        # Test data generator
├── requirements.txt       # pytest, requests
│
├── test_filter_basic.py   # Include/exclude filter tests
├── test_filter_role.py    # member_role filter
├── test_filter_dates.py   # active_since, joined_* filters
├── test_filter_points.py  # points_min, points_max
├── test_filter_search.py  # searchTerm filter
├── test_filter_sort.py    # sortBy options
└── test_export.py         # CSV export
```

## Fixtures

### `api` - API Client

Session-scoped fixture providing HTTP methods:

```python
def test_example(api):
    # HTTP methods
    api.get('/api/user')
    api.post('/api/user', json={'name': 'test'})
    api.put('/api/user/1', json={'name': 'updated'})
    api.delete('/api/user/1')

    # Helper methods
    api.reset()                    # Clear all test data
    api.set_community('slug')      # Set current community
    api.filter_users(filter_state) # Filter users
    api.bulk_users([...])          # Insert multiple users
```

### `clean_db` - Database Reset

Function-scoped fixture that resets DB before each test:

```python
def test_example(api, clean_db):
    # Database is empty here
    # ... create test data ...
```

## Test Endpoints

The app provides special endpoints for testing (`routes/test_routes.py`):

| Endpoint | Description |
|----------|-------------|
| `POST /api/test/reset` | Delete all data |
| `POST /api/test/bulk-users` | Insert multiple users |
| `POST /api/test/bulk-posts` | Insert multiple posts |
| `POST /api/test/bulk-likes` | Insert multiple likes |
| `POST /api/test/bulk-profiles` | Insert multiple profiles |
| `POST /api/test/bulk-fetches` | Insert multiple fetch records |
| `POST /api/test/set-community` | Set current community |

## DataBuilder

Builder pattern for creating test scenarios:

```python
from data_builder import DataBuilder

def test_admin_filter(api, clean_db):
    # Setup
    builder = DataBuilder(api)
    builder.with_community('test-comm')
    builder.with_fetch('members')
    builder.with_specific_user(role='admin', points=5000)
    builder.with_users(10)  # 10 random members
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

### Builder Methods

```python
builder = DataBuilder(api)

# Set context
builder.with_community('slug')     # Set community for all data

# Add fetch record (required for users)
builder.with_fetch('members')      # Type: members, posts, leaderboard

# Add users
builder.with_users(count)          # N random users
builder.with_specific_user(        # User with specific attributes
    role='admin',
    points=1000,
    last_active_days_ago=5,
    joined_days_ago=30,
    skool_id='custom_id',
    is_online=True
)

# Execute
builder.build()                    # Insert all into DB
```

### Data Generator Functions

For custom scenarios:

```python
from data_builder import generate_user, generate_post, generate_fetch

# Single user
user = generate_user(
    index=0,
    community_slug='test',
    fetch_id=1,
    role='moderator',
    points=2000
)

# Single post
post = generate_post(
    index=0,
    community_slug='test',
    user_skool_id=user['skool_id'],
    user_name=user['name'],
    upvotes=50
)
```

## Writing Tests

### Basic Test Pattern

```python
def test_filter_by_role(api, clean_db):
    # 1. Setup - create test data
    builder = DataBuilder(api)
    builder.with_community('test')
    builder.with_fetch('members')
    builder.with_specific_user(role='admin')
    builder.with_specific_user(role='member')
    builder.build()

    # 2. Execute - call the API
    result = api.filter_users({
        'communitySlug': 'test',
        'include': {'member_role': 'admin'},
        'exclude': {}
    })

    # 3. Assert - verify result
    assert len(result) == 1
    assert result[0]['member_role'] == 'admin'
```

### Testing Edge Cases

```python
def test_empty_filter_returns_all(api, clean_db):
    builder = DataBuilder(api)
    builder.with_community('test')
    builder.with_fetch('members')
    builder.with_users(5)
    builder.build()

    result = api.filter_users({
        'communitySlug': 'test',
        'include': {},
        'exclude': {}
    })

    assert len(result) == 5

def test_no_results(api, clean_db):
    builder = DataBuilder(api)
    builder.with_community('test')
    builder.with_fetch('members')
    builder.with_users(5)  # all members
    builder.build()

    result = api.filter_users({
        'communitySlug': 'test',
        'include': {'member_role': 'admin'},
        'exclude': {}
    })

    assert len(result) == 0
```

### Testing Multiple Filters

```python
def test_combined_filters(api, clean_db):
    builder = DataBuilder(api)
    builder.with_community('test')
    builder.with_fetch('members')
    builder.with_specific_user(role='admin', points=5000)
    builder.with_specific_user(role='admin', points=100)
    builder.with_specific_user(role='member', points=5000)
    builder.build()

    result = api.filter_users({
        'communitySlug': 'test',
        'include': {'member_role': 'admin'},
        'exclude': {},
        'points_min': 1000
    })

    assert len(result) == 1
    assert result[0]['points'] >= 1000
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_BASE_URL` | `http://localhost:3000` | Server URL for tests |

## Adding Test Endpoints

If you need new test helpers, add them to `myversion/routes/test_routes.py`:

```python
def register(app):
    @app.route('/api/test/my-helper', methods=['POST'])
    def my_helper():
        data = request.json
        # ... do something ...
        return jsonify({'ok': True})
```

## Reproducing This Pattern

1. **Test routes** - Add `/api/test/*` endpoints for data manipulation
2. **conftest.py** - Create `api` fixture with helper methods
3. **data_builder.py** - Create builder for test data generation
4. **test_*.py** - Write tests using fixtures and builder
5. **test_fast.sh** - Script to start server and run pytest
