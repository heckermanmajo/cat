# CatKnows Browser Extension - Refactoring Plan

## Executive Summary

Die aktuelle Extension hat fundamentale Probleme mit State-Management, Race Conditions und Over-Engineering. Dieser Plan beschreibt einen **Clean Rewrite** mit klarer Architektur.

---

## 1. Identifizierte Probleme

### 1.1 State Management (Kritisch)

**Problem:** Globale Variablen + async Storage = Race Conditions

```javascript
// background/index.js - Zeilen 8-26
let currentQueue = null;
let isRunning = false;
let completedCount = 0;
// ...

// Async restore - kann NACH Message-Handler ausgeführt werden!
chrome.storage.local.get(["currentQueue", "completedCount", "isRunning"], (result) => {
  if (result.currentQueue) {
    currentQueue = result.currentQueue;  // <-- Race condition!
  }
});
```

**Konsequenzen:**
- Popup zeigt falschen State an
- Queue wird als leer angezeigt obwohl Daten vorhanden
- `isRunning` wird NICHT restored (absichtlich, aber problematisch)

### 1.2 Manifest Inkompatibilität

**Problem:** Manifest mischt Firefox und Chrome Syntax:

```json
// manifest.json
"background": {
  "scripts": ["background.js"]  // <-- Firefox-Syntax!
}
```

Chrome MV3 erwartet:
```json
"background": {
  "service_worker": "background.js"
}
```

### 1.3 Service Worker Lifecycle

**Problem:** Chrome kann den Service Worker jederzeit beenden und neu starten.

- Alle globalen Variablen gehen verloren
- `isRunning = true` geht verloren während fetch läuft
- Kein robustes "Heartbeat" System

### 1.4 Over-Engineering

| Datei | Zeilen | Problem |
|-------|--------|---------|
| `background/index.js` | 862 | Zu viele Verantwortlichkeiten |
| `popup/popup.js` | 557 | Tightly coupled, viel redundante UI-Logik |
| `popup/popup.html` | 540 | Inline CSS (schwer wartbar) |

**Features die keiner braucht:**
- Alarm-basiertes automatisches Queue-Checking
- Toast-Notifications im Content Script
- Auto-Fetch beim Seitenbesuch (Content Script)
- Debug-Log System im Popup

### 1.5 Content Script Chaos

Der Content Script (`content/index.js`) macht Auto-Fetches die mit dem Queue-System kollidieren:

```javascript
// content/index.js - main()
async function main() {
  // Fetcht automatisch bei jedem Seitenbesuch
  const aboutData = await fetchAboutPage(slug, buildId);
  await sendToGoClient(slug, aboutData);
  await markCommunityFetched(slug);  // Eigener Cache!
}
```

**Probleme:**
- Separater `fetchedCommunities` Cache
- Kollidiert mit Queue-Prioritäten
- User hat keine Kontrolle

### 1.6 Script Injection Komplexität

Die `executeTaskInTab` Funktion injected ~200 Zeilen Code:

```javascript
// background/index.js - Zeilen 234-430
const results = await chrome.scripting.executeScript({
  target: { tabId: tab.id },
  func: async (task) => {
    // ~150 Zeilen komplexe Logik
    // Schwer zu debuggen
    // Kein Error-Boundary
  },
  args: [task]
});
```

---

## 2. Clean Architecture Vorschlag

### 2.1 Neue Struktur

```
plugin-refactoring/
├── src/
│   ├── manifest.json           # Nur Chrome MV3
│   ├── background/
│   │   ├── service-worker.js   # Entry point, minimal
│   │   ├── state.js            # Zentrales State Management
│   │   ├── queue.js            # Queue Logic
│   │   └── fetcher.js          # Skool Data Fetching
│   ├── popup/
│   │   ├── popup.html          # Minimal HTML
│   │   ├── popup.css           # Separates CSS
│   │   └── popup.js            # UI Logic
│   └── content/
│       └── content.js          # Minimal - nur BuildID extraction
├── dist/                       # Build output
└── build.sh                    # Simple build script
```

### 2.2 State Management Pattern

**Prinzip:** State IMMER aus `chrome.storage.local` lesen, NIE in Memory cachen.

```javascript
// state.js
const STATE_KEY = 'catknows_state';

const defaultState = {
  queue: null,
  isRunning: false,
  completedCount: 0,
  currentTaskIndex: -1,
  lastError: null
};

export async function getState() {
  const result = await chrome.storage.local.get(STATE_KEY);
  return result[STATE_KEY] || { ...defaultState };
}

export async function setState(updates) {
  const current = await getState();
  const newState = { ...current, ...updates };
  await chrome.storage.local.set({ [STATE_KEY]: newState });
  return newState;
}

export async function resetState() {
  await chrome.storage.local.set({ [STATE_KEY]: { ...defaultState } });
}
```

**Vorteile:**
- Kein Memory-State der out of sync geraten kann
- Service Worker Restart sicher
- Single Source of Truth

### 2.3 Vereinfachter Message Flow

```
┌─────────┐     getMessage()      ┌─────────────┐
│  Popup  │ ──────────────────────│   Service   │
│         │                       │   Worker    │
│         │ <──────────────────── │             │
└─────────┘     sendResponse()    └──────┬──────┘
                                         │
                                         │ chrome.scripting
                                         │ .executeScript()
                                         ▼
                                  ┌─────────────┐
                                  │  Skool Tab  │
                                  │  (Content)  │
                                  └─────────────┘
```

**Nur diese Messages:**
1. `GET_STATE` - Popup holt aktuellen State
2. `LOAD_QUEUE` - Queue vom Server laden
3. `START_PROCESSING` - Verarbeitung starten
4. `STOP_PROCESSING` - Verarbeitung stoppen

### 2.4 Simpler Fetcher

Statt 200 Zeilen injected Code:

```javascript
// fetcher.js
export async function fetchTask(tab, task) {
  // Step 1: Get buildId from tab
  const [{ result: buildId }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const el = document.getElementById('__NEXT_DATA__');
      if (!el) return null;
      try {
        return JSON.parse(el.textContent).buildId;
      } catch { return null; }
    }
  });

  if (!buildId) {
    return { success: false, error: 'No buildId found' };
  }

  // Step 2: Fetch data from background (no CORS issues)
  const url = buildSkoolUrl(task, buildId);
  const response = await fetch(url, {
    credentials: 'include',
    headers: { 'Accept': 'application/json' }
  });

  if (!response.ok) {
    return { success: false, error: `HTTP ${response.status}` };
  }

  return { success: true, data: await response.json() };
}
```

**Wait...** Background kann nicht mit Cookies fetchen. Das muss im Content Script passieren.

Bessere Lösung:

```javascript
// content.js - Minimal
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'FETCH_DATA') {
    fetchData(msg.url)
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep channel open
  }
});

async function fetchData(url) {
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
```

```javascript
// background - fetcher.js
export async function fetchTask(tabId, task, buildId) {
  const url = buildSkoolUrl(task, buildId);

  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, { type: 'FETCH_DATA', url }, (response) => {
      resolve(response || { success: false, error: 'No response' });
    });
  });
}
```

---

## 3. Refactoring Schritte

### Phase 1: Minimales funktionierendes Plugin

1. **Neues Manifest (Chrome MV3 only)**
2. **State Module** - Storage-basiert, kein Memory-Cache
3. **Minimal Background** - nur Message Handling
4. **Minimal Popup** - Queue laden, starten, stoppen
5. **Minimal Content** - nur Fetch-Helper

### Phase 2: Core Functionality

1. **Queue Loading** vom Go-Client
2. **Task Processing** mit Delays
3. **Progress Display** im Popup
4. **Error Handling** (einfach, ohne Debug-Log Monster)

### Phase 3: Polish

1. Badge Updates
2. Notifications (optional, einfach)
3. Settings Sync

---

## 4. Was wir NICHT mehr brauchen

| Feature | Grund |
|---------|-------|
| Alarm-based Queue Check | Over-engineering, User soll manuell laden |
| Auto-Fetch Content Script | Kollidiert mit Queue, keine Kontrolle |
| Debug Log System | Zu komplex, console.log reicht |
| Toast Notifications (Content) | Unnötig |
| `fetchedCommunities` Cache | Queue-System hat eigene Logik |
| 4 verschiedene Badge-Farben | Eine reicht |

---

## 5. Konkrete Datei-Änderungen

### 5.1 Neue manifest.json

```json
{
  "manifest_version": 3,
  "name": "CatKnows",
  "version": "0.2.0",
  "description": "Skool Community Data Fetcher",

  "permissions": [
    "storage",
    "scripting"
  ],

  "host_permissions": [
    "https://www.skool.com/*",
    "http://localhost:3000/*"
  ],

  "action": {
    "default_popup": "popup/popup.html",
    "default_title": "CatKnows"
  },

  "background": {
    "service_worker": "background/service-worker.js",
    "type": "module"
  },

  "content_scripts": [
    {
      "matches": ["https://www.skool.com/*"],
      "js": ["content/content.js"],
      "run_at": "document_idle"
    }
  ]
}
```

### 5.2 Neuer State Manager

```javascript
// background/state.js
const STATE_KEY = 'catknows_v2';

const DEFAULT_STATE = {
  queue: null,           // { tasks: [], totalTasks: 0 }
  status: 'idle',        // 'idle' | 'running' | 'paused' | 'error'
  progress: {
    completed: 0,
    total: 0,
    currentTask: null
  },
  lastSync: null,
  error: null
};

export async function getState() {
  const result = await chrome.storage.local.get(STATE_KEY);
  return result[STATE_KEY] || structuredClone(DEFAULT_STATE);
}

export async function updateState(changes) {
  const state = await getState();
  const newState = { ...state, ...changes };
  await chrome.storage.local.set({ [STATE_KEY]: newState });
  return newState;
}

export async function updateProgress(taskResult) {
  const state = await getState();
  state.progress.completed++;
  state.progress.currentTask = null;
  if (state.queue?.tasks) {
    state.queue.tasks.shift();
  }
  await chrome.storage.local.set({ [STATE_KEY]: state });
  return state;
}

export async function resetState() {
  await chrome.storage.local.set({ [STATE_KEY]: structuredClone(DEFAULT_STATE) });
}
```

### 5.3 Neuer Service Worker

```javascript
// background/service-worker.js
import * as State from './state.js';
import * as Queue from './queue.js';

const GO_CLIENT = 'http://localhost:3000';

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg).then(sendResponse);
  return true;
});

async function handleMessage(msg) {
  switch (msg.type) {
    case 'GET_STATE':
      return State.getState();

    case 'LOAD_QUEUE':
      return Queue.loadFromServer(GO_CLIENT, msg.communityIds);

    case 'START':
      return Queue.startProcessing();

    case 'STOP':
      return Queue.stopProcessing();

    case 'RESET':
      await State.resetState();
      return { success: true };

    default:
      return { error: 'Unknown message type' };
  }
}
```

### 5.4 Neues Queue Module

```javascript
// background/queue.js
import * as State from './state.js';

let processingInterval = null;

export async function loadFromServer(baseUrl, communityIds) {
  try {
    const res = await fetch(`${baseUrl}/api/fetch-queue?communityIds=${encodeURIComponent(communityIds)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const queue = await res.json();
    await State.updateState({
      queue,
      status: 'idle',
      progress: { completed: 0, total: queue.totalTasks, currentTask: null },
      error: null
    });

    return { success: true, taskCount: queue.totalTasks };
  } catch (err) {
    await State.updateState({ error: err.message });
    return { success: false, error: err.message };
  }
}

export async function startProcessing() {
  const state = await State.getState();

  if (state.status === 'running') {
    return { success: false, error: 'Already running' };
  }

  if (!state.queue?.tasks?.length) {
    return { success: false, error: 'No tasks in queue' };
  }

  await State.updateState({ status: 'running' });
  processNext();

  return { success: true };
}

export async function stopProcessing() {
  await State.updateState({ status: 'paused' });
  return { success: true };
}

async function processNext() {
  const state = await State.getState();

  if (state.status !== 'running' || !state.queue?.tasks?.length) {
    await State.updateState({ status: 'idle' });
    updateBadge('');
    return;
  }

  const task = state.queue.tasks[0];
  await State.updateState({
    progress: { ...state.progress, currentTask: task }
  });

  updateBadge(state.queue.tasks.length.toString());

  try {
    await executeTask(task);
    await State.updateProgress();
  } catch (err) {
    console.error('Task failed:', err);
    // Continue with next task
    const s = await State.getState();
    if (s.queue?.tasks) {
      s.queue.tasks.shift();
      await State.updateState({ queue: s.queue });
    }
  }

  // Delay 2-4 seconds before next
  const delay = 2000 + Math.random() * 2000;
  setTimeout(processNext, delay);
}

async function executeTask(task) {
  // Find skool tab
  const tabs = await chrome.tabs.query({ url: 'https://www.skool.com/*' });
  if (!tabs.length) {
    throw new Error('No Skool tab open');
  }

  const tab = tabs[0];

  // Get buildId
  const [{ result: buildId }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const el = document.getElementById('__NEXT_DATA__');
      if (!el) return null;
      try { return JSON.parse(el.textContent).buildId; }
      catch { return null; }
    }
  });

  if (!buildId) throw new Error('No buildId');

  // Build URL based on task type
  const url = buildUrl(task, buildId);

  // Fetch via content script (has cookies)
  const result = await chrome.tabs.sendMessage(tab.id, {
    type: 'FETCH',
    url
  });

  if (!result?.success) {
    throw new Error(result?.error || 'Fetch failed');
  }

  // Sync to Go client
  await syncToServer(task, result.data);
}

function buildUrl(task, buildId) {
  const c = task.communityId;
  const base = `https://www.skool.com/_next/data/${buildId}`;

  switch (task.type) {
    case 'about_page':
      return `${base}/${c}/about.json?group=${c}`;
    case 'members':
      return `${base}/${c}/-/members.json?t=active&p=${task.page || 1}&group=${c}`;
    case 'community_page':
      return `${base}/${c}.json?s=newest&p=${task.page || 1}`;
    case 'profile':
      return `${base}/@${task.entityId}.json?g=${c}&group=@${task.entityId}`;
    default:
      throw new Error(`Unknown task type: ${task.type}`);
  }
}

async function syncToServer(task, data) {
  const GO_CLIENT = 'http://localhost:3000';

  const payload = {
    action: 'fetch',
    timestamp: new Date().toISOString(),
    entityType: task.type,
    source: 'skool',
    data: {
      id: task.entityId || task.communityId,
      ...data
    }
  };

  const res = await fetch(`${GO_CLIENT}/api/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!res.ok) throw new Error(`Sync failed: ${res.status}`);
}

function updateBadge(text) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color: '#8b5cf6' });
}
```

### 5.5 Neues Content Script

```javascript
// content/content.js
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'FETCH') {
    fetch(msg.url, {
      credentials: 'include',
      headers: { 'Accept': 'application/json' }
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));

    return true; // Keep channel open for async response
  }
});
```

### 5.6 Neues Popup (HTML)

```html
<!-- popup/popup.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <header>
    <h1>CatKnows</h1>
    <span id="status" class="status idle">Idle</span>
  </header>

  <section class="input-section">
    <input type="text" id="communityId" placeholder="Community ID eingeben...">
    <button id="loadBtn">Laden</button>
  </section>

  <section class="queue-section" id="queueSection" hidden>
    <div class="progress">
      <span id="progressText">0 / 0</span>
      <div class="progress-bar">
        <div class="progress-fill" id="progressFill"></div>
      </div>
    </div>

    <div class="current-task" id="currentTask" hidden>
      <span class="label">Aktuell:</span>
      <span id="taskInfo">-</span>
    </div>
  </section>

  <section class="actions">
    <button id="startBtn" class="primary" disabled>Starten</button>
    <button id="stopBtn" disabled>Stoppen</button>
  </section>

  <footer>
    <button id="resetBtn" class="danger small">Reset</button>
    <span id="serverStatus">Server: ?</span>
  </footer>

  <script src="popup.js"></script>
</body>
</html>
```

### 5.7 Neues Popup (JS)

```javascript
// popup/popup.js
const GO_CLIENT = 'http://localhost:3000';

// Elements
const $ = id => document.getElementById(id);
const communityInput = $('communityId');
const loadBtn = $('loadBtn');
const startBtn = $('startBtn');
const stopBtn = $('stopBtn');
const resetBtn = $('resetBtn');
const statusEl = $('status');
const queueSection = $('queueSection');
const progressText = $('progressText');
const progressFill = $('progressFill');
const currentTask = $('currentTask');
const taskInfo = $('taskInfo');
const serverStatus = $('serverStatus');

// Message helper
function sendMsg(type, data = {}) {
  return new Promise(resolve => {
    chrome.runtime.sendMessage({ type, ...data }, resolve);
  });
}

// UI Update
function updateUI(state) {
  // Status badge
  statusEl.textContent = {
    idle: 'Idle',
    running: 'Läuft...',
    paused: 'Pausiert',
    error: 'Fehler'
  }[state.status] || 'Idle';

  statusEl.className = `status ${state.status}`;

  // Queue section
  if (state.queue?.totalTasks > 0) {
    queueSection.hidden = false;

    const done = state.progress.completed;
    const total = state.progress.total;
    progressText.textContent = `${done} / ${total}`;
    progressFill.style.width = `${(done / total) * 100}%`;

    // Current task
    if (state.progress.currentTask) {
      currentTask.hidden = false;
      const t = state.progress.currentTask;
      taskInfo.textContent = `${t.type} - ${t.communityId}`;
    } else {
      currentTask.hidden = true;
    }
  } else {
    queueSection.hidden = true;
  }

  // Buttons
  const hasQueue = state.queue?.tasks?.length > 0;
  startBtn.disabled = state.status === 'running' || !hasQueue;
  stopBtn.disabled = state.status !== 'running';
  loadBtn.disabled = state.status === 'running';
}

// Actions
async function loadQueue() {
  const id = communityInput.value.trim();
  if (!id) return;

  loadBtn.disabled = true;
  const result = await sendMsg('LOAD_QUEUE', { communityIds: id });
  loadBtn.disabled = false;

  if (result.success) {
    refreshState();
  } else {
    alert('Fehler: ' + result.error);
  }
}

async function start() {
  await sendMsg('START');
  refreshState();
}

async function stop() {
  await sendMsg('STOP');
  refreshState();
}

async function reset() {
  if (confirm('State wirklich zurücksetzen?')) {
    await sendMsg('RESET');
    refreshState();
  }
}

async function refreshState() {
  const state = await sendMsg('GET_STATE');
  updateUI(state);
}

async function checkServer() {
  try {
    const res = await fetch(`${GO_CLIENT}/api/hello`);
    serverStatus.textContent = res.ok ? 'Server: Online' : 'Server: Offline';
  } catch {
    serverStatus.textContent = 'Server: Offline';
  }
}

// Load saved community ID
async function loadSavedCommunityId() {
  try {
    const res = await fetch(`${GO_CLIENT}/api/setting?key=community_ids`);
    if (res.ok) {
      const data = await res.json();
      if (data.value) communityInput.value = data.value;
    }
  } catch {}
}

// Event listeners
loadBtn.addEventListener('click', loadQueue);
startBtn.addEventListener('click', start);
stopBtn.addEventListener('click', stop);
resetBtn.addEventListener('click', reset);
communityInput.addEventListener('keypress', e => {
  if (e.key === 'Enter') loadQueue();
});

// Listen for state updates
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'STATE_UPDATE') {
    updateUI(msg);
  }
});

// Init
(async () => {
  await checkServer();
  await loadSavedCommunityId();
  await refreshState();

  // Poll state every 2 seconds while popup is open
  setInterval(refreshState, 2000);
})();
```

---

## 6. Migration Plan

### Schritt 1: Backup
```bash
cp -r browser-extension browser-extension-backup
```

### Schritt 2: Neues Plugin erstellen
Im Ordner `plugin-refactoring/src/` die neuen Dateien anlegen.

### Schritt 3: Testen
1. Chrome: `chrome://extensions` -> Developer Mode -> Load unpacked
2. Queue laden
3. Processing starten
4. Prüfen ob Daten im Go-Client ankommen

### Schritt 4: Altes Plugin ersetzen
Nach erfolgreichem Test das alte `browser-extension/` durch das neue ersetzen.

---

## 7. Offene Fragen zur Klärung

1. **Firefox Support?**
   - Aktuell: Manifest hat Firefox-spezifische Felder
   - Empfehlung: Nur Chrome unterstützen (einfacher)

2. **Notifications nötig?**
   - Aktuell: Chrome Notifications, Badge, Toasts
   - Empfehlung: Nur Badge (zeigt Anzahl Tasks)

3. **Auto-Queue-Check?**
   - Aktuell: Alarm alle 5 Minuten
   - Empfehlung: Entfernen (User soll manuell laden)

4. **Content Script Auto-Fetch?**
   - Aktuell: Fetcht automatisch beim Seitenbesuch
   - Empfehlung: Entfernen (Queue-System nutzen)

---

## 8. Zusammenfassung

| Aspekt | Alt | Neu |
|--------|-----|-----|
| Zeilen Code | ~2000 | ~400 |
| State Management | Memory + Storage (Race Conditions) | Nur Storage |
| Browser Support | Chrome + Firefox (kaputt) | Nur Chrome |
| Features | Viele (komplex) | Wenige (funktional) |
| Debug | Custom Debug-Log | console.log |

**Kernprinzip:** KISS - Keep It Simple, Stupid.
