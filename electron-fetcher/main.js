const { app, BrowserWindow, BrowserView, ipcMain, globalShortcut } = require('electron');
const path = require('path');

const API_URL = 'http://localhost:3000';

let mainWindow;
let skoolView;
let skoolVisible = false;

function hideSkoolView() {
  skoolView.setBounds({ x: 0, y: 0, width: 0, height: 0 });
  skoolVisible = false;
  // Info an Renderer senden
  mainWindow.webContents.send('skool-hidden');
}

async function createWindow() {
  // Hauptfenster - lädt eure Web-UI
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  // Prüfen ob Python-Server läuft
  let usePythonServer = false;
  try {
    const http = require('http');
    await new Promise((resolve, reject) => {
      const req = http.get(API_URL, (res) => {
        usePythonServer = res.statusCode === 200;
        resolve();
      });
      req.on('error', () => resolve());
      req.setTimeout(1000, () => { req.destroy(); resolve(); });
    });
  } catch (e) {
    usePythonServer = false;
  }

  if (usePythonServer) {
    console.log('[main] Python-Server gefunden, lade localhost:3000');
    mainWindow.loadURL(API_URL);
  } else {
    console.log('[main] Kein Python-Server, lade test.html');
    mainWindow.loadFile('test.html');
  }

  // Skool BrowserView (erstmal versteckt)
  skoolView = new BrowserView({
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.addBrowserView(skoolView);
  skoolView.setBounds({ x: 0, y: 0, width: 0, height: 0 }); // Versteckt
  skoolView.webContents.loadURL('https://www.skool.com');

  // DevTools im Development
  // mainWindow.webContents.openDevTools();
  // skoolView.webContents.openDevTools();
}

// ============================================================================
// Skool Login UI - zeigen/verstecken
// ============================================================================

ipcMain.handle('show-skool-login', async () => {
  const bounds = mainWindow.getContentBounds();
  // Skool-View als Overlay anzeigen - mit Header-Bereich für Close-Button
  skoolView.setBounds({
    x: 50,
    y: 80,  // Platz für Close-Button oben
    width: bounds.width - 100,
    height: bounds.height - 130
  });
  skoolView.webContents.loadURL('https://www.skool.com/login');
  skoolVisible = true;
  return { ok: true };
});

ipcMain.handle('hide-skool', async () => {
  hideSkoolView();
  return { ok: true };
});

ipcMain.handle('is-skool-visible', async () => {
  return { visible: skoolVisible };
});

// ============================================================================
// Login-Status prüfen
// ============================================================================

ipcMain.handle('check-skool-login', async () => {
  try {
    // Skool-Startseite laden um Login-Status zu prüfen
    await skoolView.webContents.loadURL('https://www.skool.com');

    // Kurz warten bis Seite geladen
    await new Promise(r => setTimeout(r, 1500));

    const code = `
      (function() {
        // Verschiedene Indikatoren für eingeloggt
        const hasUserMenu = !!document.querySelector('[data-testid="user-menu"]');
        const hasAvatar = !!document.querySelector('img[alt*="avatar"], .avatar, [class*="Avatar"]');
        const hasDashboard = window.location.pathname.includes('/dashboard');
        const hasLogout = !!document.querySelector('a[href*="logout"], button[class*="logout"]');

        // Schauen ob Login-Button sichtbar (= nicht eingeloggt)
        const hasLoginBtn = !!document.querySelector('a[href="/login"]');

        return {
          loggedIn: (hasUserMenu || hasAvatar || hasDashboard || hasLogout) && !hasLoginBtn,
          url: window.location.href
        };
      })()
    `;

    const result = await skoolView.webContents.executeJavaScript(code);
    return result;
  } catch (e) {
    return { loggedIn: false, error: e.message };
  }
});

// ============================================================================
// Fetch-Logik - Tasks im Skool-Kontext ausführen
// ============================================================================

ipcMain.handle('execute-fetch-task', async (event, task) => {
  try {
    const code = `
      (async function() {
        const task = ${JSON.stringify(task)};

        // BuildId von der Seite holen
        const nextData = document.getElementById("__NEXT_DATA__");
        if (!nextData) return { error: "No __NEXT_DATA__ found - not on Skool page?" };

        const { buildId } = JSON.parse(nextData.textContent);
        if (!buildId) return { error: "No buildId found" };

        // URL basierend auf Task-Typ bauen
        let url;
        if (task.type === "members") {
          url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + "/-/members.json?t=active&p=" + task.pageParam + "&group=" + task.communitySlug;
        } else if (task.type === "posts") {
          url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + ".json?s=newest&p=" + task.pageParam;
        } else if (task.type === "profile") {
          url = "https://www.skool.com/_next/data/" + buildId + "/@" + task.userName + ".json?group=" + task.communitySlug;
        } else if (task.type === "comments") {
          if (!task.groupSkoolId) return { error: "groupSkoolId missing for comments" };
          url = "https://api2.skool.com/posts/" + task.postSkoolHexId + "/comments?group-id=" + task.groupSkoolId + "&limit=25&pinned=true";
        } else if (task.type === "likes") {
          if (!task.groupSkoolId) return { error: "groupSkoolId missing for likes" };
          url = "https://api2.skool.com/posts/" + task.postSkoolHexId + "/vote-users?group-id=" + task.groupSkoolId;
        } else if (task.type === "leaderboard") {
          url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + ".json?tab=leaderboard&p=" + task.pageParam + "&group=" + task.communitySlug;
        } else if (task.type === "community_about") {
          url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + "/about.json?group=" + task.communitySlug;
        } else {
          return { error: "Unknown task type: " + task.type };
        }

        // Fetch mit Cookies (Session)
        const res = await fetch(url, { credentials: "include" });
        if (!res.ok) return { error: "HTTP " + res.status };

        const data = await res.json();
        return { ok: true, type: task.type, data };
      })();
    `;

    const result = await skoolView.webContents.executeJavaScript(code);
    return result;
  } catch (e) {
    return { error: e.message };
  }
});

// ============================================================================
// Navigieren (für buildId)
// ============================================================================

ipcMain.handle('navigate-skool', async (event, url) => {
  try {
    await skoolView.webContents.loadURL(url);
    await new Promise(r => setTimeout(r, 1000)); // Warten bis geladen
    return { ok: true };
  } catch (e) {
    return { error: e.message };
  }
});

// ============================================================================
// App Lifecycle
// ============================================================================

app.whenReady().then(() => {
  createWindow();

  // Escape-Taste zum Schließen des Skool-Overlays
  globalShortcut.register('Escape', () => {
    if (skoolVisible) {
      console.log('[main] Escape pressed - hiding Skool');
      hideSkoolView();
    }
  });
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
