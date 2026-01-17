const { app, BrowserWindow, BrowserView, ipcMain, globalShortcut } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

const API_URL = 'http://localhost:3000';
const API_PORT = 3000;

let mainWindow;
let skoolView;
let skoolVisible = false;
let pythonProcess = null;

// ============================================================================
// Python Server Management
// ============================================================================

function getPythonPath() {
  const isPackaged = app.isPackaged;
  const platform = process.platform;

  // Binary name based on platform
  const binaryName = platform === 'win32' ? 'catknows.exe' : 'catknows';

  if (isPackaged) {
    // Production: Binary is in resources folder
    return path.join(process.resourcesPath, 'python', binaryName);
  } else {
    // Development: Use the myversion dist or run directly
    const devPath = path.join(__dirname, '..', 'myversion', 'dist', binaryName);
    const altPath = path.join(__dirname, '..', 'myversion');

    // Check if compiled binary exists
    const fs = require('fs');
    if (fs.existsSync(devPath)) {
      return devPath;
    }
    // Fallback: return path anyway, will show error if not found
    return devPath;
  }
}

function startPythonServer() {
  return new Promise((resolve, reject) => {
    const pythonPath = getPythonPath();
    console.log('[main] Starting Python server:', pythonPath);

    const fs = require('fs');
    if (!fs.existsSync(pythonPath)) {
      console.log('[main] Python binary not found at:', pythonPath);
      // In development, server might already be running
      resolve(false);
      return;
    }

    // Start Python process
    pythonProcess = spawn(pythonPath, [], {
      cwd: path.dirname(pythonPath),
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log('[python]', data.toString().trim());
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error('[python:err]', data.toString().trim());
    });

    pythonProcess.on('error', (err) => {
      console.error('[main] Failed to start Python:', err);
      reject(err);
    });

    pythonProcess.on('exit', (code) => {
      console.log('[main] Python process exited with code:', code);
      pythonProcess = null;
    });

    resolve(true);
  });
}

function stopPythonServer() {
  if (pythonProcess) {
    console.log('[main] Stopping Python server...');
    pythonProcess.kill();
    pythonProcess = null;
  }
}

async function waitForServer(maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const ready = await new Promise((resolve) => {
        const req = http.get(API_URL, (res) => {
          resolve(res.statusCode === 200);
        });
        req.on('error', () => resolve(false));
        req.setTimeout(1000, () => { req.destroy(); resolve(false); });
      });

      if (ready) {
        console.log('[main] Server is ready!');
        return true;
      }
    } catch (e) {
      // ignore
    }

    console.log(`[main] Waiting for server... (${i + 1}/${maxAttempts})`);
    await new Promise(r => setTimeout(r, 500));
  }

  return false;
}

// ============================================================================
// Window Management
// ============================================================================

function hideSkoolView() {
  skoolView.setBounds({ x: 0, y: 0, width: 0, height: 0 });
  skoolVisible = false;
  mainWindow.webContents.send('skool-hidden');
}

async function createWindow() {
  // Main window
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    show: false // Don't show until ready
  });

  // Show loading screen first
  mainWindow.loadFile('loading.html');
  mainWindow.show();

  // Start Python server
  let pythonStarted = false;
  try {
    pythonStarted = await startPythonServer();
  } catch (e) {
    console.error('[main] Error starting Python:', e);
  }

  // Wait for server to be ready
  const serverReady = await waitForServer();

  if (serverReady) {
    console.log('[main] Loading web UI from localhost:3000');
    mainWindow.loadURL(API_URL);
  } else {
    console.log('[main] Server not ready, showing error');
    mainWindow.loadFile('error.html');
  }

  // Skool BrowserView (hidden initially)
  skoolView = new BrowserView({
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.addBrowserView(skoolView);
  skoolView.setBounds({ x: 0, y: 0, width: 0, height: 0 });
  skoolView.webContents.loadURL('https://www.skool.com');
}

// ============================================================================
// Skool Login UI
// ============================================================================

ipcMain.handle('show-skool-login', async () => {
  const bounds = mainWindow.getContentBounds();
  skoolView.setBounds({
    x: 50,
    y: 80,
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
// Login Status Check
// ============================================================================

ipcMain.handle('check-skool-login', async () => {
  try {
    await skoolView.webContents.loadURL('https://www.skool.com');
    await new Promise(r => setTimeout(r, 1500));

    const code = `
      (function() {
        const hasUserMenu = !!document.querySelector('[data-testid="user-menu"]');
        const hasAvatar = !!document.querySelector('img[alt*="avatar"], .avatar, [class*="Avatar"]');
        const hasDashboard = window.location.pathname.includes('/dashboard');
        const hasLogout = !!document.querySelector('a[href*="logout"], button[class*="logout"]');
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
// Fetch Logic
// ============================================================================

ipcMain.handle('execute-fetch-task', async (event, task) => {
  try {
    const code = `
      (async function() {
        const task = ${JSON.stringify(task)};

        const nextData = document.getElementById("__NEXT_DATA__");
        if (!nextData) return { error: "No __NEXT_DATA__ found - not on Skool page?" };

        const { buildId } = JSON.parse(nextData.textContent);
        if (!buildId) return { error: "No buildId found" };

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

ipcMain.handle('navigate-skool', async (event, url) => {
  try {
    await skoolView.webContents.loadURL(url);
    await new Promise(r => setTimeout(r, 1000));
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

  globalShortcut.register('Escape', () => {
    if (skoolVisible) {
      console.log('[main] Escape pressed - hiding Skool');
      hideSkoolView();
    }
  });
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  stopPythonServer();
});

app.on('window-all-closed', () => {
  stopPythonServer();
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
