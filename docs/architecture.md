# Architecture Guide

This document explains how the frontend and backend work together, and how to reproduce this pattern for other tools.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Electron Main Process                       │
│                                                                      │
│  ┌────────────────────────┐      ┌────────────────────────────────┐ │
│  │      BrowserView       │      │         Main Window            │ │
│  │    (External Site)     │      │      (Local Web UI)            │ │
│  │                        │      │                                │ │
│  │  - Embedded browser    │      │  loadURL(http://localhost:X)   │ │
│  │  - executeJavaScript() │      │                                │ │
│  │  - Cookies/Sessions    │      │  ┌──────────────────────────┐  │ │
│  └────────────┬───────────┘      │  │    Vanilla JS + HTML     │  │ │
│               │                  │  │    (served by Flask)     │  │ │
│               │                  │  └────────────┬─────────────┘  │ │
│               │                  └───────────────┼────────────────┘ │
│               │ IPC                              │ HTTP             │
│               │                                  │                  │
│  ┌────────────▼──────────────────────────────────▼───────────────┐  │
│  │                        IPC Handlers                            │  │
│  │   - show-skool-login    - navigate-skool                      │  │
│  │   - check-skool-login   - execute-fetch-task                  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┬───────────────────┘
                                                   │
                              Spawns & Manages     │
                                                   ▼
                          ┌─────────────────────────────────────┐
                          │         Python Backend (Flask)       │
                          │                                      │
                          │   Port: dynamic (3000-3100)          │
                          │   Writes port to .port file          │
                          │                                      │
                          │   ┌───────────┐   ┌──────────────┐  │
                          │   │  Routes   │   │   Entities   │  │
                          │   │  /api/*   │   │   (Models)   │  │
                          │   └─────┬─────┘   └──────┬───────┘  │
                          │         │                │          │
                          │         └────────┬───────┘          │
                          │                  ▼                  │
                          │         ┌────────────────┐          │
                          │         │    SQLite      │          │
                          │         │    app.db      │          │
                          │         └────────────────┘          │
                          └─────────────────────────────────────┘
```

## Backend Architecture

### Entry Point (`app.py`)

```python
from flask import Flask
from model import Model

app = Flask(__name__, static_folder='static')

# Connect to SQLite
Model.connect(DB_PATH)

# Register entities (creates tables + CRUD routes)
User.register(app)
Post.register(app)
ConfigEntry.register(app)

# Register domain routes
query_routes.register(app)
stats_routes.register(app)

# Serve static files
@app.route('/')
def index(): return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename): return send_from_directory('static', filename)
```

### Model Pattern (`model.py`)

The `Model` base class provides:
1. **Auto-migration**: Tables created from class annotations
2. **CRUD operations**: `save()`, `delete()`, `by_id()`, `all()`
3. **Auto-routing**: `register(app)` creates REST endpoints

```python
class Model:
    id: int = None
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def register(cls, app):
        """Creates REST API for this entity"""
        name = cls.__name__.lower()
        cls.update_table()  # Create/migrate table

        # GET /api/user
        @app.route(f'/api/{name}', methods=['GET'])
        def get_all(): return jsonify([x.to_dict() for x in cls.all()])

        # GET /api/user/5
        @app.route(f'/api/{name}/<int:id>', methods=['GET'])
        def get_one(id): ...

        # POST /api/user
        @app.route(f'/api/{name}', methods=['POST'])
        def create(): ...

        # PUT /api/user/5
        @app.route(f'/api/{name}/<int:id>', methods=['PUT'])
        def update(id): ...

        # DELETE /api/user/5
        @app.route(f'/api/{name}/<int:id>', methods=['DELETE'])
        def delete(id): ...
```

### Entity Definition

```python
class User(Model):
    """Just define fields - table + API created automatically"""
    name: str = ""
    email: str = ""
    points: int = 0
    metadata: str = ""  # JSON stored as string

    # Custom queries can override default methods
    @classmethod
    def all(cls, order: str = 'id DESC') -> list['User']:
        # Custom logic here
        return cls.filtered(some_filter)
```

### Domain Routes (`routes/*.py`)

For logic beyond CRUD:

```python
# routes/stats_routes.py
def register(app):
    @app.route('/api/stats/summary', methods=['GET'])
    def summary():
        users = Model.query("SELECT COUNT(*) as c FROM user")[0]['c']
        posts = Model.query("SELECT COUNT(*) as c FROM post")[0]['c']
        return jsonify({'users': users, 'posts': posts})
```

## Frontend Architecture

### Page Structure

Each page is **self-contained**:

```html
<!-- members.html -->
<html>
<head>
    <!-- Shared utilities -->
    <script src="/entity.js"></script>
    <script src="/lib.js"></script>
    <link href="/default.css" rel="stylesheet">

    <!-- Page-specific entity if needed -->
    <script src="/entities/user.js"></script>
</head>
<body>
    <!-- Page content -->
    <script>
        // Page-specific logic inline
        window.onload = async () => {
            const users = await User.all();
            renderUsers(users);
        }
    </script>
</body>
</html>
```

### Entity Class (`entity.js`)

Base class for frontend entities:

```javascript
class Entity {
    static _name = 'entity';
    static _defaults = {};

    constructor(data = {}) {
        this.id = null;
        Object.assign(this, this.constructor._defaults, data);
    }

    get _endpoint() { return `/api/${this.constructor._name}`; }

    async save() {
        const url = this.id ? `${this._endpoint}/${this.id}` : this._endpoint;
        const res = await api(this.id ? 'PUT' : 'POST', url, this.toJSON());
        if (res.ok) Object.assign(this, res.data);
        return res;
    }

    async delete() { ... }
    static async all() { ... }
    static async get(id) { ... }
}
```

### Entity Definitions

```javascript
// entities/user.js
class User extends Entity {
    static _name = 'user';
    static _defaults = {
        name: '',
        email: '',
        points: 0
    };
}
```

### Config Entry Pattern

UI state persisted in database:

```javascript
// Store preference
await ConfigEntry.set('current_community', 'my-community');

// Load preference
const theme = await ConfigEntry.get('theme');
```

### Page Reload Philosophy

Instead of SPA state management:

```javascript
// After saving, just reload
async function saveUser() {
    await user.save();
    window.location.reload();  // Simple, works great locally
}

// Navigation is just links
function goToSettings() {
    window.location.href = '/settings.html';
}
```

## Electron Layer

### Main Process (`main.js`)

```javascript
const { app, BrowserWindow, BrowserView, ipcMain } = require('electron');

let mainWindow;
let externalView;  // For embedding external sites

async function createWindow() {
    // Main window loads local Flask UI
    mainWindow = new BrowserWindow({ ... });
    mainWindow.loadURL(`http://localhost:${PORT}`);

    // BrowserView for external site (hidden initially)
    externalView = new BrowserView({ ... });
    mainWindow.addBrowserView(externalView);
    externalView.setBounds({ x: 0, y: 0, width: 0, height: 0 });
}

// IPC: Show external login
ipcMain.handle('show-external-login', async () => {
    externalView.setBounds({ x: 50, y: 80, width: w, height: h });
    externalView.webContents.loadURL('https://external-site.com/login');
});

// IPC: Execute fetch on external site
ipcMain.handle('execute-fetch', async (event, task) => {
    const code = `
        (async function() {
            const res = await fetch('${task.url}', { credentials: 'include' });
            return await res.json();
        })();
    `;
    return await externalView.webContents.executeJavaScript(code);
});
```

### Preload Script (`preload.js`)

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    showExternalLogin: () => ipcRenderer.invoke('show-external-login'),
    executeFetch: (task) => ipcRenderer.invoke('execute-fetch', task),
    onExternalHidden: (callback) => ipcRenderer.on('external-hidden', callback)
});
```

### Using Electron API from Web UI

```javascript
// In your HTML/JS
async function fetchFromExternal() {
    if (window.electronAPI) {
        const result = await window.electronAPI.executeFetch({
            url: 'https://api.external-site.com/data'
        });
        // Process result
    }
}
```

## Data Flow Example

### Fetching Data from External Site

```
1. User clicks "Fetch Members" in UI
   │
2. Frontend calls /api/fetch/start
   │
3. Backend creates Fetch task, returns task ID
   │
4. Frontend uses window.electronAPI.executeFetch()
   │
5. Electron executes JS in BrowserView (with cookies)
   │
6. External API returns JSON data
   │
7. Frontend POSTs data to /api/fetch/data
   │
8. Backend extracts entities, saves to SQLite
   │
9. Frontend reloads page to show new data
```

## How to Reproduce This Stack

### 1. Create Python Backend

```
myproject/
├── app.py              # Flask entry point
├── model.py            # ORM base class
├── src/
│   ├── user.py         # Entity: class User(Model)
│   └── config_entry.py # Key-value config storage
├── routes/
│   └── custom_routes.py
├── static/
│   ├── index.html
│   ├── entity.js       # Frontend Entity base
│   └── lib.js          # Shared utilities
└── requirements.txt
```

### 2. Create Electron Shell

```
electron-app/
├── main.js             # Window + BrowserView + IPC
├── preload.js          # Expose APIs to renderer
├── loading.html        # Shown while server starts
├── error.html          # Shown if server fails
└── package.json
```

### 3. Create Build Scripts

```python
# build.py
import subprocess
subprocess.run([
    'python', '-m', 'nuitka',
    '--onefile',
    '--include-data-dir=static=static',
    'app.py'
])
```

### 4. Create Start Script

```bash
#!/bin/bash
# Start Python server
python myproject/app.py &
PYTHON_PID=$!

# Wait for .port file
while [ ! -f ".port" ]; do sleep 0.5; done

# Start Electron
cd electron-app && npx electron .

# Cleanup
kill $PYTHON_PID
```

## Design Principles

1. **Simple-Dense-Explicit**: No magic, readable without IDE
2. **Decoupling > DRY**: Each page self-contained
3. **Page Reloads**: Simplest state management
4. **SQLite for Everything**: Even UI preferences
5. **No Web Security**: Local single-user app
6. **Type Hints = Schema**: Python annotations define DB columns
