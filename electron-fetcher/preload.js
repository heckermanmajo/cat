const { contextBridge, ipcRenderer } = require('electron');

// Bridge zwischen eurer Web-UI und Electron
contextBridge.exposeInMainWorld('electronFetcher', {

  // Skool Login-Overlay anzeigen
  showSkoolLogin: () => ipcRenderer.invoke('show-skool-login'),

  // Skool-View verstecken
  hideSkool: () => ipcRenderer.invoke('hide-skool'),

  // Prüfen ob Skool-Overlay sichtbar ist
  isSkoolVisible: () => ipcRenderer.invoke('is-skool-visible'),

  // Prüfen ob bei Skool eingeloggt
  checkSkoolLogin: () => ipcRenderer.invoke('check-skool-login'),

  // Einen Fetch-Task ausführen
  executeFetchTask: (task) => ipcRenderer.invoke('execute-fetch-task', task),

  // Skool zu einer URL navigieren (für buildId)
  navigateSkool: (url) => ipcRenderer.invoke('navigate-skool', url),

  // Event-Listener für Skool-Hidden
  onSkoolHidden: (callback) => ipcRenderer.on('skool-hidden', callback)
});

// Info ausgeben wenn geladen
console.log('[preload] electronFetcher API bereit');
