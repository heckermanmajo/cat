const GO_CLIENT_URL = "http://localhost:3000";

// DOM Elements
const statusEl = document.getElementById("status");
const currentCommunityEl = document.getElementById("currentCommunity");
const communityInput = document.getElementById("communityInput");
const loadQueueBtn = document.getElementById("loadQueueBtn");
const startQueueBtn = document.getElementById("startQueueBtn");
const stopQueueBtn = document.getElementById("stopQueueBtn");
const clearCacheBtn = document.getElementById("clearCacheBtn");
const checkNowBtn = document.getElementById("checkNowBtn");
const queueList = document.getElementById("queueList");
const queueStats = document.getElementById("queueStats");
const totalTasksEl = document.getElementById("totalTasks");
const completedTasksEl = document.getElementById("completedTasks");
const remainingTasksEl = document.getElementById("remainingTasks");
const progressContainer = document.getElementById("progressContainer");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const serverDot = document.getElementById("serverDot");
const serverStatusEl = document.getElementById("serverStatus");
const fetchLogList = document.getElementById("fetchLogList");
const toggleLogBtn = document.getElementById("toggleLogBtn");
const fetchLogSection = document.getElementById("fetchLogSection");
const toggleDebugBtn = document.getElementById("toggleDebugBtn");
const debugLogSection = document.getElementById("debugLogSection");
const debugLogList = document.getElementById("debugLogList");
const clearDebugBtn = document.getElementById("clearDebugBtn");
const currentTaskSection = document.getElementById("currentTaskSection");
const taskStatus = document.getElementById("taskStatus");
const taskType = document.getElementById("taskType");
const taskDetails = document.getElementById("taskDetails");
const taskProgress = document.getElementById("taskProgress");
const errorBanner = document.getElementById("errorBanner");
const errorTitle = document.getElementById("errorTitle");
const errorMessage = document.getElementById("errorMessage");
const forceResetBtn = document.getElementById("forceResetBtn");

// State
let currentSlug = null;
let currentQueue = null;
let isRunning = false;
let completedCount = 0;
let showLog = false;
let showDebug = false;
let lastError = null;

// Type labels and icons
const TYPE_ICONS = {
  'about_page': 'A',
  'profile': 'P',
  'members': 'M',
  'community_page': 'C',
  'post_details': 'D',
  'likes': 'L'
};

const TYPE_LABELS = {
  'about_page': 'About Page',
  'profile': 'Profile',
  'members': 'Members',
  'community_page': 'Posts',
  'post_details': 'Post Details',
  'likes': 'Likes'
};

const PRIORITY_LABELS = {
  1: 'High',
  2: 'Medium',
  3: 'Low'
};

// Utility functions
function showStatus(message, type = "success") {
  statusEl.textContent = message;
  statusEl.className = type;
}

function hideStatus() {
  statusEl.className = "";
}

function getCommunitySlugFromUrl(url) {
  try {
    const urlObj = new URL(url);
    if (!urlObj.hostname.includes("skool.com")) return null;

    const skipPatterns = [/^\/$/, /^\/discover/, /^\/settings/, /^\/notifications/, /^\/chat/, /^\/@/, /^\/search/];
    for (const pattern of skipPatterns) {
      if (pattern.test(urlObj.pathname)) return null;
    }

    const match = urlObj.pathname.match(/^\/([a-zA-Z0-9-]+)/);
    return match ? match[1] : null;
  } catch (e) {
    return null;
  }
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// Server status check
async function checkServerStatus() {
  try {
    const res = await fetch(`${GO_CLIENT_URL}/api/hello`);
    if (res.ok) {
      serverDot.className = "server-dot online";
      serverStatusEl.textContent = "Server online";
      return true;
    }
  } catch (e) {}
  serverDot.className = "server-dot offline";
  serverStatusEl.textContent = "Server offline";
  return false;
}

// Load saved community_ids from server settings
async function loadSavedCommunityIds() {
  try {
    const res = await fetch(`${GO_CLIENT_URL}/api/setting?key=community_ids`);
    if (res.ok) {
      const data = await res.json();
      if (data.value) {
        communityInput.value = data.value;
        return data.value;
      }
    }
  } catch (e) {
    console.warn("Could not load community_ids from server:", e);
  }
  return null;
}

// Get state from background script
async function getBackgroundState() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "GET_STATE" }, (response) => {
      if (chrome.runtime.lastError) {
        console.warn("Could not get background state:", chrome.runtime.lastError);
        resolve(null);
      } else {
        resolve(response);
      }
    });
  });
}

// Listen for state updates from background
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "STATE_UPDATE") {
    updateUIFromState(message);
  }
});

// Update UI from background state
function updateUIFromState(state) {
  isRunning = state.isRunning;
  currentQueue = state.queue;
  completedCount = state.completedCount;

  // Update buttons
  startQueueBtn.disabled = isRunning || !currentQueue || currentQueue.tasks.length === 0;
  stopQueueBtn.disabled = !isRunning;
  loadQueueBtn.disabled = isRunning;

  // Update queue display
  renderQueue();

  // Update fetch log
  if (state.fetchLog && state.fetchLog.length > 0) {
    renderFetchLog(state.fetchLog);
    // Check for recent errors
    const recentErrors = state.fetchLog.filter(l => l.status === 'error');
    if (recentErrors.length > 0) {
      const lastErr = recentErrors[recentErrors.length - 1];
      showErrorBanner(`Fehler bei ${lastErr.typeLabel}`, lastErr.error || 'Unbekannter Fehler');
    }
  }

  // Update debug log
  if (state.debugLog && state.debugLog.length > 0) {
    renderDebugLog(state.debugLog);
  }

  // Update current task
  updateCurrentTask(state.currentTask);

  // Update status
  if (isRunning) {
    showStatus("Fetching im Hintergrund...", "info");
  }
}

// Load queue via background script
async function loadQueue() {
  const communityId = communityInput.value.trim();
  if (!communityId) {
    showStatus("Please enter a Community ID", "error");
    return;
  }

  loadQueueBtn.disabled = true;
  showStatus("Loading queue...", "info");

  chrome.runtime.sendMessage({ type: "LOAD_QUEUE", communityIds: communityId }, (response) => {
    loadQueueBtn.disabled = false;

    if (chrome.runtime.lastError) {
      showStatus(`Error: ${chrome.runtime.lastError.message}`, "error");
      return;
    }

    if (response && response.success) {
      currentQueue = response.queue;
      completedCount = 0;
      renderQueue();

      if (currentQueue.tasks.length > 0) {
        startQueueBtn.disabled = false;
        showStatus(`${currentQueue.totalTasks} tasks loaded`, "success");
      } else {
        showStatus("No tasks - data is up to date!", "success");
      }
    } else {
      showStatus(`Error: ${response?.error || "Unknown error"}`, "error");
    }
  });
}

// Render queue in UI
function renderQueue() {
  if (!currentQueue || currentQueue.tasks.length === 0) {
    queueList.innerHTML = '<div class="queue-empty">No tasks in queue</div>';
    queueStats.style.display = "none";
    progressContainer.style.display = "none";
    return;
  }

  queueStats.style.display = "flex";
  progressContainer.style.display = "block";

  const total = currentQueue.totalTasks;
  const remaining = currentQueue.tasks.length;

  totalTasksEl.textContent = total;
  completedTasksEl.textContent = completedCount;
  remainingTasksEl.textContent = remaining;

  const progress = total > 0 ? ((completedCount / total) * 100) : 0;
  progressFill.style.width = `${progress}%`;
  progressText.textContent = `${completedCount} / ${total} Tasks`;

  // Render first 5 tasks
  const tasksToShow = currentQueue.tasks.slice(0, 5);
  queueList.innerHTML = tasksToShow.map(task => {
    const icon = TYPE_ICONS[task.type] || '?';
    const label = TYPE_LABELS[task.type] || task.type;
    const priorityLabel = PRIORITY_LABELS[task.priority] || `P${task.priority}`;
    const priorityClass = task.priority === 1 ? 'high' : task.priority === 2 ? 'medium' : 'low';

    return `
      <div class="queue-item">
        <span class="type-icon">${icon}</span>
        <span class="type-name">${label}${task.page ? ` (S.${task.page})` : ''}</span>
        <span class="priority ${priorityClass}">${priorityLabel}</span>
      </div>
    `;
  }).join('');

  if (currentQueue.tasks.length > 5) {
    queueList.innerHTML += `<div class="queue-empty">+ ${currentQueue.tasks.length - 5} more tasks</div>`;
  }
}

// Render fetch log
function renderFetchLog(log) {
  if (!log || log.length === 0) {
    fetchLogList.innerHTML = '<div class="log-empty">Keine Fetches bisher</div>';
    return;
  }

  // Show most recent first
  const sortedLog = [...log].reverse();

  fetchLogList.innerHTML = sortedLog.map(entry => {
    const statusClass = entry.status === 'success' ? 'success' : entry.status === 'error' ? 'error' : 'skipped';
    const statusIcon = entry.status === 'success' ? 'ok' : entry.status === 'error' ? '!' : '-';
    const icon = TYPE_ICONS[entry.type] || '?';

    let details = entry.communityId;
    if (entry.page) details += ` S.${entry.page}`;
    if (entry.entityId) details += ` ${entry.entityId.substring(0, 10)}...`;

    // Show error message if present
    let errorHtml = '';
    if (entry.status === 'error' && entry.error) {
      let errorContent = escapeHtml(entry.error);
      if (entry.url) {
        errorContent += `<br><span style="color:#6b7280;">URL: ${escapeHtml(entry.url)}</span>`;
      }
      errorHtml = `<div class="log-error-detail">${errorContent}</div>`;
    }

    return `
      <div class="log-item ${statusClass}">
        <span class="log-icon">${icon}</span>
        <span class="log-type">${entry.typeLabel}</span>
        <span class="log-details">${details}</span>
        <span class="log-duration">${formatDuration(entry.duration)}</span>
        <span class="log-status">${statusIcon}</span>
      </div>
      ${errorHtml}
    `;
  }).join('');
}

// Render debug log
function renderDebugLog(log) {
  if (!log || log.length === 0) {
    debugLogList.innerHTML = '<div class="log-empty" style="color: #6b7280;">Kein Debug-Log vorhanden</div>';
    return;
  }

  // Show most recent first
  const sortedLog = [...log].reverse();

  debugLogList.innerHTML = sortedLog.map(entry => {
    const time = formatTime(entry.timestamp);
    const levelClass = entry.level;
    let detailsHtml = '';

    if (entry.details) {
      // Format details as JSON, but compact
      let detailsStr = '';
      if (typeof entry.details === 'object') {
        try {
          detailsStr = JSON.stringify(entry.details, null, 0);
          // Truncate if too long
          if (detailsStr.length > 200) {
            detailsStr = detailsStr.substring(0, 200) + '...';
          }
        } catch (e) {
          detailsStr = String(entry.details);
        }
      } else {
        detailsStr = String(entry.details);
      }
      detailsHtml = `<div class="debug-details">${escapeHtml(detailsStr)}</div>`;
    }

    return `
      <div class="debug-entry">
        <span class="debug-time">${time}</span>
        <span class="debug-level ${levelClass}">${entry.level.toUpperCase()}</span>
        <span class="debug-message">${escapeHtml(entry.message)}</span>
      </div>
      ${detailsHtml}
    `;
  }).join('');

  // Auto-scroll to top (most recent)
  debugLogList.scrollTop = 0;
}

// Escape HTML to prevent XSS
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Update current task display
function updateCurrentTask(task) {
  if (task) {
    currentTaskSection.classList.remove('idle');
    taskStatus.classList.remove('idle');
    taskStatus.classList.add('running');
    taskStatus.textContent = 'Running';
    taskType.textContent = task.typeLabel || task.type;

    let details = task.communityId;
    if (task.page) details += ` - Seite ${task.page}`;
    if (task.entityId) details += ` - ${task.entityId}`;
    taskDetails.textContent = details;

    taskProgress.textContent = `Task ${task.index} von ${task.total}`;
  } else {
    currentTaskSection.classList.add('idle');
    taskStatus.classList.add('idle');
    taskStatus.classList.remove('running');
    taskStatus.textContent = isRunning ? 'Warte...' : 'Idle';
    taskType.textContent = isRunning ? 'Bereite naechsten Task vor...' : 'Warte auf Start...';
    taskDetails.textContent = '';
    taskProgress.textContent = '';
  }
}

// Show error banner
function showErrorBanner(title, message) {
  errorTitle.textContent = title;
  errorMessage.textContent = message;
  errorBanner.classList.add('visible');
  lastError = { title, message, timestamp: Date.now() };
}

// Hide error banner
function hideErrorBanner() {
  errorBanner.classList.remove('visible');
  lastError = null;
}

// Toggle debug log visibility
function toggleDebugLog() {
  showDebug = !showDebug;
  debugLogSection.style.display = showDebug ? "block" : "none";
  toggleDebugBtn.textContent = showDebug ? "Debug aus" : "Debug";

  if (showDebug) {
    // Load full debug log from background
    chrome.runtime.sendMessage({ type: "GET_DEBUG_LOG" }, (response) => {
      if (response && response.debugLog) {
        renderDebugLog(response.debugLog);
      }
    });
  }
}

// Clear debug log
function clearDebugLog() {
  chrome.runtime.sendMessage({ type: "CLEAR_DEBUG_LOG" }, (response) => {
    if (response && response.success) {
      debugLogList.innerHTML = '<div class="log-empty" style="color: #6b7280;">Debug-Log geloescht</div>';
    }
  });
}

// Force reset - use when stuck
function forceReset() {
  chrome.runtime.sendMessage({ type: "FORCE_RESET" }, (response) => {
    if (response && response.success) {
      showStatus("State wurde zurueckgesetzt", "info");
      isRunning = false;
      startQueueBtn.disabled = !currentQueue || currentQueue.tasks.length === 0;
      stopQueueBtn.disabled = true;
      loadQueueBtn.disabled = false;
      updateCurrentTask(null);
      hideErrorBanner();
    }
  });
}

// Start queue processing via background
function startQueue() {
  chrome.runtime.sendMessage({ type: "START_FETCHING" }, (response) => {
    if (response && response.success) {
      isRunning = true;
      startQueueBtn.disabled = true;
      stopQueueBtn.disabled = false;
      showStatus("Fetching gestartet...", "info");
    }
  });
}

// Stop queue processing
function stopQueue() {
  chrome.runtime.sendMessage({ type: "STOP_FETCHING" }, (response) => {
    if (response && response.success) {
      isRunning = false;
      stopQueueBtn.disabled = true;
      showStatus("Stopped", "info");
    }
  });
}

// Check queue now
function checkQueueNow() {
  chrome.runtime.sendMessage({ type: "CHECK_QUEUE_NOW" }, (response) => {
    showStatus("Queue wird geprueft...", "info");
  });
}

// Toggle fetch log visibility
function toggleFetchLog() {
  showLog = !showLog;
  fetchLogSection.style.display = showLog ? "block" : "none";
  toggleLogBtn.textContent = showLog ? "Log ausblenden" : "Fetch-Log";

  if (showLog) {
    // Load full log from storage
    chrome.runtime.sendMessage({ type: "GET_FETCH_LOG" }, (response) => {
      if (response && response.fetchLog) {
        renderFetchLog(response.fetchLog);
      }
    });
  }
}

// Clear cache
function clearCache() {
  chrome.storage.local.set({ fetchedCommunities: {} }, () => {
    showStatus("Cache cleared", "info");
  });
}

// Initialize popup
async function init() {
  // Check server status
  const serverOnline = await checkServerStatus();

  // Load saved community_ids from server (if online)
  let savedCommunityIds = null;
  if (serverOnline) {
    savedCommunityIds = await loadSavedCommunityIds();
  }

  // Get current state from background
  const bgState = await getBackgroundState();
  if (bgState) {
    updateUIFromState(bgState);
  }

  // Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && tab.url) {
    currentSlug = getCommunitySlugFromUrl(tab.url);
    if (currentSlug) {
      currentCommunityEl.textContent = currentSlug;
      currentCommunityEl.classList.remove("none");
      // Only override with current slug if no saved community_ids
      if (!savedCommunityIds) {
        communityInput.value = currentSlug;
      }
    } else {
      currentCommunityEl.textContent = "No Skool community";
      currentCommunityEl.classList.add("none");
    }
  } else {
    currentCommunityEl.textContent = "No page loaded";
    currentCommunityEl.classList.add("none");
  }

  // Event listeners
  loadQueueBtn.addEventListener("click", loadQueue);
  startQueueBtn.addEventListener("click", startQueue);
  stopQueueBtn.addEventListener("click", stopQueue);
  clearCacheBtn.addEventListener("click", clearCache);
  checkNowBtn.addEventListener("click", checkQueueNow);
  toggleLogBtn.addEventListener("click", toggleFetchLog);
  toggleDebugBtn.addEventListener("click", toggleDebugLog);
  clearDebugBtn.addEventListener("click", clearDebugLog);
  errorBanner.addEventListener("click", hideErrorBanner);
  forceResetBtn.addEventListener("click", forceReset);

  communityInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") loadQueue();
  });
}

// Run init
init();
