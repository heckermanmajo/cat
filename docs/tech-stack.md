# Tech Stack

This document describes the technologies used in this project. The stack is designed for **local-only desktop applications** that need to fetch data from web services while providing a web-based UI.

## Overview

```
┌─────────────────────────────────────────────────────┐
│                    Electron Shell                    │
│  ┌─────────────────┐    ┌─────────────────────────┐ │
│  │   BrowserView   │    │      Main Window        │ │
│  │   (Skool.com)   │    │   (Local Flask UI)      │ │
│  │                 │    │                         │ │
│  │  - Login        │    │  ┌─────────────────┐    │ │
│  │  - Data Fetch   │    │  │  Static HTML    │    │ │
│  │                 │    │  │  + Vanilla JS   │    │ │
│  └─────────────────┘    │  └─────────────────┘    │ │
│                         └───────────┬─────────────┘ │
└─────────────────────────────────────┼───────────────┘
                                      │ HTTP (localhost)
                           ┌──────────▼──────────┐
                           │   Python Backend    │
                           │   (Flask + SQLite)  │
                           └─────────────────────┘
```

## Backend

### Python 3.13+
- **Flask** - Lightweight web framework serving REST API and static files
- **Flask-CORS** - Cross-Origin Resource Sharing (for development)
- **SQLite** - Embedded database, stored as single file (`app.db`)

### Key Libraries
```
flask          # Web framework
flask-cors     # CORS support
nuitka         # Python-to-C compiler for distribution
requests       # HTTP client (for external API calls)
```

### Why These Choices
- **Flask**: Minimal, no magic, easy to understand - perfect for local apps
- **SQLite**: Zero-config, single-file database - ideal for desktop apps
- **Nuitka**: Compiles Python to standalone binary - no Python installation required for users

## Frontend

### Electron 28.x
- Desktop wrapper providing native window and system access
- **BrowserView** for embedding external websites (Skool.com login/fetch)
- **IPC** communication between main process and renderer

### Web Technologies
- **Vanilla JavaScript** - No framework, minimal dependencies
- **Static HTML** - Each page is self-contained
- **CSS** - Simple theming via CSS variables

### Why No Framework
- Local app = fast page reloads (no SPA needed)
- Simpler debugging and maintenance
- Each page is independent - easier to understand and modify
- State persisted in SQLite, not in JS memory

## Build & Distribution

### Nuitka (Python Compiler)
Compiles Python code to standalone C binary:
```bash
python -m nuitka --onefile app.py
```
Result: Single executable with all dependencies bundled.

### Electron Builder
Packages Electron app with embedded Python binary:
- **Linux**: AppImage
- **Windows**: Portable EXE
- **macOS**: ZIP archive

### Distribution Package
```
CatKnows/
├── CatKnowsLauncher     # Small launcher (checks updates)
├── CatKnows.AppImage    # Main app (Electron + Python)
└── version.txt          # Current version
```

## Database

### SQLite with Auto-Migration
The `Model` base class handles:
- Automatic table creation from Python class annotations
- Automatic column addition for new fields
- No migration files needed

```python
class User(Model):
    name: str = ""        # Creates TEXT column
    points: int = 0       # Creates INTEGER column
    score: float = 0.0    # Creates REAL column
```

## Development Dependencies

### Node.js 20+
For Electron development:
```json
{
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-builder": "^24.9.1"
  }
}
```

### Python Virtual Environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r myversion/requirements.txt
```

## Key Design Principles

1. **Simple-Dense-Explicit**: Code should be readable without IDE support
2. **Decoupling over DRY**: Each page is self-contained
3. **Page Reloads over SPA**: Simplicity wins when everything runs locally
4. **SQLite for UI State**: Even preferences stored in database
5. **No Web Security Concerns**: Single-user local app, no CSRF/XSS needed
