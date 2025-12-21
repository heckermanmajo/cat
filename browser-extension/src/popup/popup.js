const GO_CLIENT_URL = "http://localhost:3000";

// DOM Elements
const statusEl = document.getElementById("status");
const currentCommunityEl = document.getElementById("currentCommunity");
const communityInput = document.getElementById("communityInput");
const loadQueueBtn = document.getElementById("loadQueueBtn");
const startQueueBtn = document.getElementById("startQueueBtn");
const stopQueueBtn = document.getElementById("stopQueueBtn");
const clearCacheBtn = document.getElementById("clearCacheBtn");
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

// State
let currentSlug = null;
let currentQueue = null;
let isRunning = false;
let completedCount = 0;

// Type labels and icons
const TYPE_ICONS = {
  'about_page': '📄',
  'profile': '👤',
  'members': '👥',
  'community_page': '📝',
  'post_details': '💬',
  'likes': '❤️'
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

// Load queue from server
async function loadQueue() {
  const communityId = communityInput.value.trim();
  if (!communityId) {
    showStatus("Please enter a Community ID", "error");
    return;
  }

  loadQueueBtn.disabled = true;
  showStatus("Loading queue...", "info");

  try {
    const res = await fetch(`${GO_CLIENT_URL}/api/fetch-queue?communityIds=${encodeURIComponent(communityId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    currentQueue = await res.json();
    completedCount = 0;
    renderQueue();

    if (currentQueue.tasks.length > 0) {
      startQueueBtn.disabled = false;
      showStatus(`${currentQueue.totalTasks} tasks loaded`, "success");
    } else {
      showStatus("No tasks - data is up to date!", "success");
    }
  } catch (e) {
    showStatus(`Error: ${e.message}`, "error");
  } finally {
    loadQueueBtn.disabled = false;
  }
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
    const icon = TYPE_ICONS[task.type] || '📦';
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

// Execute a single fetch task
async function executeTask(task) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) throw new Error("No active tab");

  // Execute fetch in content script context
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: async (task) => {
      // Get build ID from page
      const nextDataScript = document.getElementById("__NEXT_DATA__");
      if (!nextDataScript) throw new Error("No Next.js data");

      const nextData = JSON.parse(nextDataScript.textContent);
      const buildId = nextData.buildId;
      if (!buildId) throw new Error("Build ID not found");

      const communityId = task.communityId;
      let url, entityType;

      switch (task.type) {
        case 'about_page':
          url = `https://www.skool.com/_next/data/${buildId}/${communityId}/about.json?group=${communityId}`;
          entityType = 'about_page';
          break;

        case 'members':
          const page = task.page || 1;
          url = `https://www.skool.com/_next/data/${buildId}/${communityId}/-/members.json?t=active&p=${page}&online=&levels=&price=&courseIds=&sortType=-memberlastoffline&monthly=false&annual=false&trials=false&group=${communityId}`;
          entityType = 'members';
          break;

        case 'community_page':
          const postPage = task.page || 1;
          url = postPage === 1
            ? `https://www.skool.com/_next/data/${buildId}/${communityId}.json?c=&s=newest&fl=`
            : `https://www.skool.com/_next/data/${buildId}/${communityId}.json?c=&s=newest&fl=&p=${postPage}`;
          entityType = 'community_page';
          break;

        case 'profile':
          const memberSlug = task.entityId;
          url = `https://www.skool.com/_next/data/${buildId}/@${memberSlug}.json?g=${communityId}&group=@${memberSlug}`;
          entityType = 'profile';
          break;

        case 'post_details':
          // Post details need special handling - for now just mark as needing implementation
          return { type: task.type, status: 'skipped', reason: 'Not yet implemented' };

        case 'likes':
          // Likes use different API
          const postId = task.entityId;
          // Need community skool ID - for now skip
          return { type: task.type, status: 'skipped', reason: 'Not yet implemented' };

        default:
          return { type: task.type, status: 'skipped', reason: 'Unknown type' };
      }

      // Fetch the data
      const response = await fetch(url, {
        credentials: "include",
        headers: { "Accept": "application/json" }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      return { type: task.type, entityType, data, task };
    },
    args: [task]
  });

  return results[0].result;
}

// Send fetched data to Go client
async function syncToGoClient(fetchResult) {
  if (fetchResult.status === 'skipped') {
    return { success: true, skipped: true };
  }

  const entityId = fetchResult.task.page
    ? `${fetchResult.task.communityId}_page_${fetchResult.task.page}`
    : fetchResult.task.entityId
      ? `${fetchResult.task.communityId}_${fetchResult.task.entityId}`
      : fetchResult.task.communityId;

  const payload = {
    action: "fetch",
    timestamp: new Date().toISOString(),
    entityType: fetchResult.entityType,
    source: "skool",
    data: {
      id: entityId,
      ...fetchResult.data
    }
  };

  const res = await fetch(`${GO_CLIENT_URL}/api/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) throw new Error(`Sync failed: HTTP ${res.status}`);
  return await res.json();
}

// Process queue
async function processQueue() {
  if (!currentQueue || currentQueue.tasks.length === 0) {
    showStatus("Queue is empty!", "info");
    return;
  }

  isRunning = true;
  startQueueBtn.disabled = true;
  stopQueueBtn.disabled = false;

  while (isRunning && currentQueue.tasks.length > 0) {
    const task = currentQueue.tasks[0];
    const typeLabel = TYPE_LABELS[task.type] || task.type;

    showStatus(`Fetching: ${typeLabel}...`, "info");

    try {
      const result = await executeTask(task);

      if (result.status !== 'skipped') {
        await syncToGoClient(result);
      }

      // Remove completed task
      currentQueue.tasks.shift();
      completedCount++;
      renderQueue();

      // Small delay between tasks (2-5 seconds)
      if (isRunning && currentQueue.tasks.length > 0) {
        const delay = 2000 + Math.random() * 3000;
        await new Promise(r => setTimeout(r, delay));
      }
    } catch (e) {
      console.error("Task error:", e);
      showStatus(`Error with ${typeLabel}: ${e.message}`, "error");
      // Continue with next task after error
      currentQueue.tasks.shift();
      renderQueue();
      await new Promise(r => setTimeout(r, 1000));
    }
  }

  isRunning = false;
  startQueueBtn.disabled = currentQueue.tasks.length === 0;
  stopQueueBtn.disabled = true;

  if (currentQueue.tasks.length === 0) {
    showStatus("Queue completely processed!", "success");
  }
}

// Stop queue processing
function stopQueue() {
  isRunning = false;
  stopQueueBtn.disabled = true;
  showStatus("Stopped", "info");
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
  startQueueBtn.addEventListener("click", processQueue);
  stopQueueBtn.addEventListener("click", stopQueue);
  clearCacheBtn.addEventListener("click", clearCache);

  communityInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") loadQueue();
  });
}

// Run init
init();
