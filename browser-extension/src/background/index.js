// CatKnows Background Service Worker
// Handles background fetching, notifications, and queue management

const GO_CLIENT_URL = "http://localhost:3000";
const QUEUE_CHECK_ALARM = "catknows-queue-check";
const QUEUE_CHECK_INTERVAL_MINUTES = 5; // Check every 5 minutes

// State (will be restored from storage)
let currentQueue = null;
let isRunning = false;
let completedCount = 0;
let fetchLog = []; // Log of completed fetches with timing
let debugLog = []; // Detailed debug log for troubleshooting
let currentTask = null; // Currently executing task

// Restore state from storage on startup
chrome.storage.local.get(["currentQueue", "completedCount", "isRunning"], (result) => {
  if (result.currentQueue) {
    currentQueue = result.currentQueue;
    console.log("[CatKnows] Restored queue from storage:", currentQueue.tasks?.length, "tasks");
  }
  if (result.completedCount) {
    completedCount = result.completedCount;
  }
  // Don't restore isRunning - if we're restarting, we're not running anymore
});

// Save queue to storage whenever it changes
function saveQueueToStorage() {
  chrome.storage.local.set({
    currentQueue: currentQueue,
    completedCount: completedCount
  });
}

// Type labels for notifications
const TYPE_LABELS = {
  'about_page': 'About Page',
  'profile': 'Profile',
  'members': 'Members',
  'community_page': 'Posts',
  'post_details': 'Post Details',
  'likes': 'Likes'
};

console.log("[CatKnows] Background service worker started");

// Debug logging helper
function addDebugLog(level, message, details = null) {
  const entry = {
    timestamp: new Date().toISOString(),
    level, // 'info', 'warn', 'error', 'success'
    message,
    details
  };
  debugLog.push(entry);
  // Keep only last 50 entries
  if (debugLog.length > 50) {
    debugLog = debugLog.slice(-50);
  }
  console.log(`[CatKnows][${level.toUpperCase()}] ${message}`, details || '');
  // Broadcast update to popup
  broadcastState();
}

// ==================== ALARM SETUP ====================

// Setup periodic queue check alarm
chrome.alarms.create(QUEUE_CHECK_ALARM, {
  periodInMinutes: QUEUE_CHECK_INTERVAL_MINUTES
});

// Listen for alarm events
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === QUEUE_CHECK_ALARM) {
    console.log("[CatKnows] Periodic queue check triggered");
    await checkQueueAndNotify();
  }
});

// ==================== INSTALLATION ====================

chrome.runtime.onInstalled.addListener((details) => {
  console.log("[CatKnows] Extension installed:", details.reason);

  // Initialize storage
  chrome.storage.local.get(["fetchedCommunities", "fetchLog", "autoFetchEnabled"], (result) => {
    if (!result.fetchedCommunities) {
      chrome.storage.local.set({ fetchedCommunities: {} });
    }
    if (!result.fetchLog) {
      chrome.storage.local.set({ fetchLog: [] });
    }
    if (result.autoFetchEnabled === undefined) {
      chrome.storage.local.set({ autoFetchEnabled: true });
    }
  });

  // Do initial queue check after installation
  setTimeout(() => checkQueueAndNotify(), 3000);
});

// ==================== QUEUE CHECK & NOTIFICATION ====================

async function checkServerStatus() {
  try {
    const res = await fetch(`${GO_CLIENT_URL}/api/hello`);
    return res.ok;
  } catch (e) {
    return false;
  }
}

async function getCommunityIds() {
  try {
    const res = await fetch(`${GO_CLIENT_URL}/api/setting?key=community_ids`);
    if (res.ok) {
      const data = await res.json();
      return data.value || null;
    }
  } catch (e) {
    console.warn("[CatKnows] Could not get community_ids:", e);
  }
  return null;
}

async function fetchQueueFromServer(communityIds) {
  try {
    const res = await fetch(`${GO_CLIENT_URL}/api/fetch-queue?communityIds=${encodeURIComponent(communityIds)}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (e) {
    console.error("[CatKnows] Queue fetch error:", e);
  }
  return null;
}

async function checkQueueAndNotify() {
  // Check if server is online
  const serverOnline = await checkServerStatus();
  if (!serverOnline) {
    console.log("[CatKnows] Server offline, skipping queue check");
    return;
  }

  // Get community IDs from settings
  const communityIds = await getCommunityIds();
  if (!communityIds) {
    console.log("[CatKnows] No community IDs configured, skipping queue check");
    return;
  }

  // Check if already running
  if (isRunning) {
    console.log("[CatKnows] Already running, skipping queue check");
    return;
  }

  // Fetch queue
  const queue = await fetchQueueFromServer(communityIds);
  if (!queue || queue.tasks.length === 0) {
    console.log("[CatKnows] No tasks in queue");
    // Update badge to show we checked
    chrome.action.setBadgeText({ text: "" });
    return;
  }

  // Update badge with task count
  chrome.action.setBadgeText({ text: String(queue.totalTasks) });
  chrome.action.setBadgeBackgroundColor({ color: "#8b5cf6" });

  // Show notification
  chrome.notifications.create("queue-available", {
    type: "basic",
    iconUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAIRJREFUWEftl0EOgCAMBLsn8f8/0pN4EWMCB0gLJerBA1xgp9sCoT+5iYioucc+IlZ+Yt8TzyYPEbEASAkARdJW+V5JGf9pBlg+5V8ycExOOgDeV+gB+AJAD8AXAHoAvgDQA/AFgB6ALwD0AHwBoAfgCwA9AF8A6AH4AkAPUO0Bkx/E17D7BwXwICG5GwF9AAAAAElFTkSuQmCC",
    title: "CatKnows - Neue Daten verfuegbar",
    message: `${queue.totalTasks} Fetch-Tasks warten. Klicke um zu starten.`,
    buttons: [
      { title: "Jetzt ausfuehren" },
      { title: "Spaeter" }
    ],
      });

  // Store queue for later use
  currentQueue = queue;
  completedCount = 0;
  saveQueueToStorage();
}

// Handle notification button clicks
chrome.notifications.onButtonClicked.addListener(async (notificationId, buttonIndex) => {
  if (notificationId === "queue-available") {
    chrome.notifications.clear(notificationId);

    if (buttonIndex === 0) {
      // "Jetzt ausfuehren" clicked
      console.log("[CatKnows] User clicked 'Jetzt ausfuehren'");
      await startBackgroundFetching();
    } else {
      // "Spaeter" clicked
      console.log("[CatKnows] User clicked 'Spaeter'");
    }
  }
});

// Handle notification click (anywhere on notification)
chrome.notifications.onClicked.addListener(async (notificationId) => {
  if (notificationId === "queue-available") {
    chrome.notifications.clear(notificationId);
    // Open popup or start fetching
    await startBackgroundFetching();
  }
});

// ==================== BACKGROUND FETCHING ====================

async function getSkoolTab() {
  // Find an existing Skool tab or create one
  const tabs = await chrome.tabs.query({ url: "https://www.skool.com/*" });
  if (tabs.length > 0) {
    return tabs[0];
  }

  // No Skool tab found - we need one for fetching
  return null;
}

async function executeTaskInTab(tab, task) {
  addDebugLog('info', `Executing task in tab ${tab.id}`, { taskType: task.type, communityId: task.communityId });

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: async (task) => {
        const debugInfo = { steps: [] };

        try {
          // Step 1: Check page URL
          debugInfo.steps.push({ step: 'check_url', url: window.location.href });

          if (!window.location.hostname.includes('skool.com')) {
            return {
              type: task.type,
              status: 'error',
              error: 'Tab is not on skool.com',
              debugInfo
            };
          }

          // Step 2: Get build ID from page
          debugInfo.steps.push({ step: 'find_next_data' });
          const nextDataScript = document.getElementById("__NEXT_DATA__");
          if (!nextDataScript) {
            debugInfo.steps.push({ step: 'next_data_missing', error: 'Element not found' });
            return {
              type: task.type,
              status: 'error',
              error: 'No __NEXT_DATA__ element - page may not be fully loaded or not a Skool page',
              debugInfo
            };
          }

          // Step 3: Parse Next.js data
          debugInfo.steps.push({ step: 'parse_next_data' });
          let nextData;
          try {
            nextData = JSON.parse(nextDataScript.textContent);
          } catch (parseErr) {
            debugInfo.steps.push({ step: 'parse_error', error: parseErr.message });
            return {
              type: task.type,
              status: 'error',
              error: `Failed to parse __NEXT_DATA__: ${parseErr.message}`,
              debugInfo
            };
          }

          const buildId = nextData.buildId;
          if (!buildId) {
            debugInfo.steps.push({ step: 'no_build_id', nextDataKeys: Object.keys(nextData) });
            return {
              type: task.type,
              status: 'error',
              error: 'Build ID not found in __NEXT_DATA__',
              debugInfo
            };
          }
          debugInfo.buildId = buildId;
          debugInfo.steps.push({ step: 'got_build_id', buildId });

          const communityId = task.communityId;
          let url, entityType;

          // Step 4: Build URL based on task type
          debugInfo.steps.push({ step: 'build_url', taskType: task.type });

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
              // Post-Details (Comments) werden über api2.skool.com geholt, nicht Next.js Data
              const postId = task.entityId;
              if (!postId) {
                debugInfo.steps.push({ step: 'no_post_id', error: 'entityId (postId) is missing' });
                return { type: task.type, status: 'error', error: 'postId not provided in task', debugInfo };
              }
              // Get groupId (Skool UUID) from task.params (provided by queue builder)
              // Fallback to extracting from page data if not provided
              const detailsGroupId = task.params?.groupId
                           || nextData.props?.pageProps?.groupId
                           || nextData.props?.pageProps?.group?.id
                           || nextData.query?.groupId;
              if (!detailsGroupId) {
                debugInfo.steps.push({ step: 'no_group_id', error: 'groupId not in task.params and not found in __NEXT_DATA__' });
                return { type: task.type, status: 'error', error: 'groupId not available for post_details (rebuild queue after fetching posts)', debugInfo };
              }
              debugInfo.groupId = detailsGroupId;
              // Use api2.skool.com/posts/{ID}/comments endpoint (same as old_codebase FetchComments.php)
              // Default limit is 25 (API rejects 100)
              url = `https://api2.skool.com/posts/${postId}/comments?group-id=${detailsGroupId}&limit=25&pinned=true`;
              entityType = 'post_details';
              break;

            case 'likes':
              const likePostId = task.entityId;
              if (!likePostId) {
                debugInfo.steps.push({ step: 'no_post_id', error: 'entityId (postId) is missing for likes' });
                return { type: task.type, status: 'error', error: 'postId not provided in task', debugInfo };
              }
              // Get groupId (Skool UUID) from task.params (provided by queue builder)
              // Fallback to extracting from page data if not provided
              const groupId = task.params?.groupId
                           || nextData.props?.pageProps?.groupId
                           || nextData.props?.pageProps?.group?.id
                           || nextData.query?.groupId;
              if (!groupId) {
                debugInfo.steps.push({ step: 'no_group_id', error: 'groupId not in task.params and not found in __NEXT_DATA__' });
                return { type: task.type, status: 'error', error: 'groupId not available (rebuild queue after fetching posts)', debugInfo };
              }
              debugInfo.groupId = groupId;
              url = `https://api2.skool.com/posts/${likePostId}/vote-users?group-id=${groupId}`;
              entityType = 'likes';
              break;

            default:
              return { type: task.type, status: 'skipped', reason: 'Unknown type', debugInfo };
          }

          debugInfo.fetchUrl = url;
          debugInfo.steps.push({ step: 'url_built', url });

          // Step 5: Fetch the data
          debugInfo.steps.push({ step: 'fetching' });
          const fetchStart = Date.now();

          let response;
          try {
            response = await fetch(url, {
              credentials: "include",
              headers: { "Accept": "application/json" }
            });
          } catch (fetchErr) {
            debugInfo.steps.push({ step: 'fetch_network_error', error: fetchErr.message });
            return {
              type: task.type,
              status: 'error',
              error: `Network error: ${fetchErr.message}`,
              debugInfo
            };
          }

          const fetchDuration = Date.now() - fetchStart;
          debugInfo.fetchDuration = fetchDuration;

          if (!response.ok) {
            // Try to get response body for more error details
            let errorBody = '';
            try {
              const text = await response.text();
              if (text) {
                // Try to parse as JSON for better formatting
                try {
                  const jsonErr = JSON.parse(text);
                  errorBody = jsonErr.message || jsonErr.error || JSON.stringify(jsonErr).substring(0, 200);
                } catch {
                  errorBody = text.substring(0, 200);
                }
              }
            } catch {}

            debugInfo.steps.push({
              step: 'fetch_http_error',
              status: response.status,
              statusText: response.statusText,
              body: errorBody
            });
            return {
              type: task.type,
              status: 'error',
              error: errorBody
                ? `HTTP ${response.status}: ${errorBody}`
                : `HTTP ${response.status}: ${response.statusText}`,
              debugInfo
            };
          }

          debugInfo.steps.push({ step: 'fetch_ok', status: response.status, duration: fetchDuration });

          // Step 6: Parse response
          debugInfo.steps.push({ step: 'parsing_response' });
          let data;
          try {
            data = await response.json();
          } catch (jsonErr) {
            debugInfo.steps.push({ step: 'json_parse_error', error: jsonErr.message });
            return {
              type: task.type,
              status: 'error',
              error: `Failed to parse response JSON: ${jsonErr.message}`,
              debugInfo
            };
          }

          debugInfo.steps.push({ step: 'success', dataKeys: Object.keys(data || {}) });

          return { type: task.type, entityType, data, task, debugInfo, status: 'success' };

        } catch (unexpectedErr) {
          debugInfo.steps.push({ step: 'unexpected_error', error: unexpectedErr.message, stack: unexpectedErr.stack });
          return {
            type: task.type,
            status: 'error',
            error: `Unexpected error: ${unexpectedErr.message}`,
            debugInfo
          };
        }
      },
      args: [task]
    });

    const result = results[0].result;

    // Log debug info
    if (result.debugInfo) {
      addDebugLog(
        result.status === 'error' ? 'error' : 'info',
        `Task execution completed: ${result.status}`,
        { steps: result.debugInfo.steps, error: result.error }
      );
    }

    return result;

  } catch (scriptErr) {
    addDebugLog('error', `Script injection failed`, { error: scriptErr.message, tabId: tab.id });
    return {
      type: task.type,
      status: 'error',
      error: `Script injection failed: ${scriptErr.message}`
    };
  }
}

async function syncToGoClient(fetchResult) {
  if (fetchResult.status === 'skipped') {
    return { success: true, skipped: true };
  }

  let entityId;
  if (fetchResult.task.page) {
    entityId = `${fetchResult.task.communityId}_page_${fetchResult.task.page}`;
  } else if (fetchResult.entityType === 'likes' && fetchResult.task.entityId) {
    // Likes use special format: communityId_post_postId (matches queue.go:408)
    entityId = `${fetchResult.task.communityId}_post_${fetchResult.task.entityId}`;
  } else if (fetchResult.task.entityId) {
    entityId = `${fetchResult.task.communityId}_${fetchResult.task.entityId}`;
  } else {
    entityId = fetchResult.task.communityId;
  }

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

// Validate Build-ID by making a test request
async function validateBuildId(tab) {
  addDebugLog('info', 'Validating Build-ID...');

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: async () => {
        // Get build ID from page
        const nextDataScript = document.getElementById("__NEXT_DATA__");
        if (!nextDataScript) {
          return { valid: false, error: 'no_next_data', message: 'Seite nicht vollstaendig geladen' };
        }

        let nextData;
        try {
          nextData = JSON.parse(nextDataScript.textContent);
        } catch (e) {
          return { valid: false, error: 'parse_error', message: 'Konnte Seiten-Daten nicht lesen' };
        }

        const buildId = nextData.buildId;
        if (!buildId) {
          return { valid: false, error: 'no_build_id', message: 'Keine Build-ID gefunden' };
        }

        // Get a community slug to test with (from current page or query)
        const pathMatch = window.location.pathname.match(/^\/([a-zA-Z0-9-]+)/);
        const testSlug = pathMatch ? pathMatch[1] : null;

        if (!testSlug || testSlug === 'discover' || testSlug === 'settings') {
          // Can't validate without a community, but buildId exists - assume ok
          return { valid: true, buildId, warning: 'Konnte Build-ID nicht testen (keine Community-Seite)' };
        }

        // Make a lightweight test request to validate the build ID
        const testUrl = `https://www.skool.com/_next/data/${buildId}/${testSlug}/about.json?group=${testSlug}`;

        try {
          const response = await fetch(testUrl, {
            credentials: "include",
            headers: { "Accept": "application/json" }
          });

          if (response.ok) {
            return { valid: true, buildId, testSlug };
          } else if (response.status === 404) {
            // Check if it's a build ID issue (Next.js returns specific error)
            const text = await response.text();
            if (text.includes('404') || text.includes('Error')) {
              return {
                valid: false,
                error: 'stale_build_id',
                buildId,
                message: 'Build-ID ist veraltet - Skool hat ein Update gemacht'
              };
            }
            // 404 might be community not found - buildId could still be valid
            return { valid: true, buildId, warning: `Community "${testSlug}" nicht gefunden, aber Build-ID scheint ok` };
          } else {
            return { valid: true, buildId, warning: `Test-Request gab HTTP ${response.status}` };
          }
        } catch (fetchErr) {
          // Network error - can't validate, assume ok
          return { valid: true, buildId, warning: `Netzwerk-Fehler beim Testen: ${fetchErr.message}` };
        }
      }
    });

    return results[0].result;
  } catch (e) {
    addDebugLog('error', `Build-ID validation script failed: ${e.message}`);
    return { valid: false, error: 'script_error', message: e.message };
  }
}

async function startBackgroundFetching() {
  addDebugLog('info', 'startBackgroundFetching called');

  // Queue should already be restored by message handler, but double-check
  if (!currentQueue || currentQueue.tasks.length === 0) {
    addDebugLog('warn', 'No queue to process - should not happen');
    return;
  }

  if (isRunning) {
    addDebugLog('warn', 'Already running - should not happen');
    return;
  }

  // Find a Skool tab
  addDebugLog('info', 'Searching for Skool tab...');
  const tab = await getSkoolTab();

  if (!tab) {
    addDebugLog('error', 'No Skool tab found - cannot execute fetches');
    chrome.notifications.create("need-skool-tab", {
      type: "basic",
      iconUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAIRJREFUWEftl0EOgCAMBLsn8f8/0pN4EWMCB0gLJerBA1xgp9sCoT+5iYioucc+IlZ+Yt8TzyYPEbEASAkARdJW+V5JGf9pBlg+5V8ycExOOgDeV+gB+AJAD8AXAHoAvgDQA/AFgB6ALwD0AHwBoAfgCwA9AF8A6AH4AkAPUO0Bkx/E17D7BwXwICG5GwF9AAAAAElFTkSuQmCC",
      title: "CatKnows",
      message: "Bitte oeffne einen Tab mit skool.com um Fetches auszufuehren.",
          });
    return;
  }

  addDebugLog('success', `Found Skool tab: ${tab.id} - ${tab.url}`);

  // Validate Build-ID before starting
  const validation = await validateBuildId(tab);

  if (!validation.valid) {
    addDebugLog('error', `Build-ID validation failed: ${validation.message}`, validation);

    chrome.notifications.create("build-id-invalid", {
      type: "basic",
      iconUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAIRJREFUWEftl0EOgCAMBLsn8f8/0pN4EWMCB0gLJerBA1xgp9sCoT+5iYioucc+IlZ+Yt8TzyYPEbEASAkARdJW+V5JGf9pBlg+5V8ycExOOgDeV+gB+AJAD8AXAHoAvgDQA/AFgB6ALwD0AHwBoAfgCwA9AF8A6AH4AkAPUO0Bkx/E17D7BwXwICG5GwF9AAAAAElFTkSuQmCC",
      title: "CatKnows - Seite neu laden!",
      message: validation.message + ". Bitte druecke F5 im Skool-Tab und starte dann erneut.",
      requireInteraction: true
    });

    // Also broadcast to popup
    broadcastState();
    return;
  }

  if (validation.warning) {
    addDebugLog('warn', `Build-ID validation warning: ${validation.warning}`);
  } else {
    addDebugLog('success', `Build-ID validated: ${validation.buildId}`);
  }

  isRunning = true;
  fetchLog = [];
  debugLog = []; // Clear debug log on new run

  // Update badge to show running
  chrome.action.setBadgeText({ text: "..." });
  chrome.action.setBadgeBackgroundColor({ color: "#10b981" });

  // Notify start
  chrome.notifications.create("fetch-started", {
    type: "basic",
    iconUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAIRJREFUWEftl0EOgCAMBLsn8f8/0pN4EWMCB0gLJerBA1xgp9sCoT+5iYioucc+IlZ+Yt8TzyYPEbEASAkARdJW+V5JGf9pBlg+5V8ycExOOgDeV+gB+AJAD8AXAHoAvgDQA/AFgB6ALwD0AHwBoAfgCwA9AF8A6AH4AkAPUO0Bkx/E17D7BwXwICG5GwF9AAAAAElFTkSuQmCC",
    title: "CatKnows - Fetching gestartet",
    message: `${currentQueue.tasks.length} Tasks werden verarbeitet...`,
      });

  addDebugLog('info', `Starting to process ${currentQueue.tasks.length} tasks`);

  // Broadcast to popup
  broadcastState();

  let taskIndex = 0;
  while (isRunning && currentQueue.tasks.length > 0) {
    taskIndex++;
    const task = currentQueue.tasks[0];
    const typeLabel = TYPE_LABELS[task.type] || task.type;
    const startTime = Date.now();

    // Set current task
    currentTask = {
      ...task,
      typeLabel,
      index: taskIndex,
      total: currentQueue.totalTasks,
      startedAt: new Date().toISOString()
    };
    broadcastState();

    addDebugLog('info', `[${taskIndex}/${currentQueue.totalTasks}] Starting task: ${typeLabel}`, {
      communityId: task.communityId,
      page: task.page,
      entityId: task.entityId
    });

    try {
      const result = await executeTaskInTab(tab, task);

      const fetchDuration = Date.now() - startTime;

      // Check for error status from executeTaskInTab
      if (result.status === 'error') {
        addDebugLog('error', `Task failed: ${result.error}`, result.debugInfo);

        // Log error
        const logEntry = {
          type: task.type,
          typeLabel,
          communityId: task.communityId,
          page: task.page || null,
          entityId: task.entityId || null,
          status: 'error',
          error: result.error,
          url: result.debugInfo?.fetchUrl || null,
          duration: fetchDuration,
          timestamp: new Date().toISOString()
        };
        fetchLog.push(logEntry);

        // Continue with next task
        currentQueue.tasks.shift();
        saveQueueToStorage();
        broadcastState();

        await new Promise(r => setTimeout(r, 1000));
        continue;
      }

      if (result.status === 'skipped') {
        addDebugLog('warn', `Task skipped: ${result.reason}`);
      } else {
        // Sync to Go client
        addDebugLog('info', 'Syncing data to Go client...');
        try {
          await syncToGoClient(result);
          addDebugLog('success', 'Data synced successfully');
        } catch (syncErr) {
          addDebugLog('error', `Sync failed: ${syncErr.message}`);
        }
      }

      // Log this fetch
      const logEntry = {
        type: task.type,
        typeLabel,
        communityId: task.communityId,
        page: task.page || null,
        entityId: task.entityId || null,
        status: result.status === 'skipped' ? 'skipped' : 'success',
        duration: fetchDuration,
        timestamp: new Date().toISOString()
      };
      fetchLog.push(logEntry);

      // Remove completed task
      currentQueue.tasks.shift();
      completedCount++;
      saveQueueToStorage();

      // Update badge
      const remaining = currentQueue.tasks.length;
      chrome.action.setBadgeText({ text: remaining > 0 ? String(remaining) : "ok" });

      addDebugLog('success', `Task completed in ${fetchDuration}ms, ${remaining} remaining`);

      // Broadcast progress to popup
      broadcastState();

      // Delay between tasks (2-5 seconds)
      if (isRunning && currentQueue.tasks.length > 0) {
        const delay = 2000 + Math.random() * 3000;
        addDebugLog('info', `Waiting ${Math.round(delay)}ms before next task...`);
        await new Promise(r => setTimeout(r, delay));
      }
    } catch (e) {
      addDebugLog('error', `Unexpected error in task loop: ${e.message}`, { stack: e.stack });

      // Log error
      const logEntry = {
        type: task.type,
        typeLabel,
        communityId: task.communityId,
        page: task.page || null,
        entityId: task.entityId || null,
        status: 'error',
        error: e.message,
        duration: Date.now() - startTime,
        timestamp: new Date().toISOString()
      };
      fetchLog.push(logEntry);

      // Continue with next task
      currentQueue.tasks.shift();
      saveQueueToStorage();

      // Broadcast to popup
      broadcastState();

      await new Promise(r => setTimeout(r, 1000));
    }
  }

  currentTask = null;
  isRunning = false;
  saveQueueToStorage();

  // Save fetch log
  await saveFetchLog();

  // Final notification
  const successCount = fetchLog.filter(l => l.status === 'success').length;
  const errorCount = fetchLog.filter(l => l.status === 'error').length;
  const totalDuration = fetchLog.reduce((sum, l) => sum + l.duration, 0);
  const avgWaitTime = fetchLog.length > 0 ? Math.round(totalDuration / fetchLog.length / 1000) : 0;

  chrome.notifications.create("fetch-complete", {
    type: "basic",
    iconUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAIRJREFUWEftl0EOgCAMBLsn8f8/0pN4EWMCB0gLJerBA1xgp9sCoT+5iYioucc+IlZ+Yt8TzyYPEbEASAkARdJW+V5JGf9pBlg+5V8ycExOOgDeV+gB+AJAD8AXAHoAvgDQA/AFgB6ALwD0AHwBoAfgCwA9AF8A6AH4AkAPUO0Bkx/E17D7BwXwICG5GwF9AAAAAElFTkSuQmCC",
    title: "CatKnows - Fertig!",
    message: `${successCount} erfolgreich, ${errorCount} Fehler. Durchschn. ${avgWaitTime}s pro Fetch.`,
      });

  // Clear badge after a moment
  setTimeout(() => {
    chrome.action.setBadgeText({ text: "" });
  }, 5000);

  // Broadcast final state
  broadcastState();
}

async function stopBackgroundFetching() {
  isRunning = false;
  chrome.action.setBadgeText({ text: "stop" });
  setTimeout(() => {
    chrome.action.setBadgeText({ text: "" });
  }, 2000);
  broadcastState();
}

async function saveFetchLog() {
  // Get existing log and append new entries
  const result = await chrome.storage.local.get(["fetchLog"]);
  const existingLog = result.fetchLog || [];

  // Keep last 100 entries
  const combined = [...existingLog, ...fetchLog].slice(-100);
  await chrome.storage.local.set({ fetchLog: combined });
}

// ==================== MESSAGE HANDLING ====================

function broadcastState() {
  const state = {
    type: "STATE_UPDATE",
    isRunning,
    queue: currentQueue,
    completedCount,
    fetchLog: fetchLog.slice(-20), // Last 20 entries
    debugLog: debugLog.slice(-30), // Last 30 debug entries
    currentTask // Currently executing task
  };

  // Send to popup if open
  chrome.runtime.sendMessage(state).catch(() => {
    // Popup not open, ignore
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("[CatKnows] Message received:", message.type);

  // Handle sync to Go client (from content script)
  if (message.type === "SYNC_TO_GO_CLIENT") {
    (async () => {
      try {
        const response = await fetch(`${GO_CLIENT_URL}/api/sync`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(message.payload)
        });

        if (!response.ok) {
          sendResponse({ success: false, error: `HTTP ${response.status}` });
        } else {
          const data = await response.json();
          sendResponse({ success: true, data });
        }
      } catch (error) {
        console.error("[CatKnows] Sync error:", error);
        sendResponse({ success: false, error: error.message });
      }
    })();
    return true;
  }

  // Get current state (from popup)
  if (message.type === "GET_STATE") {
    sendResponse({
      isRunning,
      queue: currentQueue,
      completedCount,
      fetchLog: fetchLog.slice(-20),
      debugLog: debugLog.slice(-30),
      currentTask
    });
    return true;
  }

  // Get debug log (from popup)
  if (message.type === "GET_DEBUG_LOG") {
    sendResponse({ debugLog: debugLog });
    return true;
  }

  // Clear debug log (from popup)
  if (message.type === "CLEAR_DEBUG_LOG") {
    debugLog = [];
    broadcastState();
    sendResponse({ success: true });
    return true;
  }

  // Force reset state (from popup) - use when stuck
  if (message.type === "FORCE_RESET") {
    addDebugLog('warn', 'Force reset triggered by user');
    isRunning = false;
    currentTask = null;
    chrome.action.setBadgeText({ text: "" });
    saveQueueToStorage();
    broadcastState();
    sendResponse({ success: true });
    return true;
  }

  // Start fetching (from popup)
  if (message.type === "START_FETCHING") {
    // Restore queue from storage synchronously first if needed
    (async () => {
      if (!currentQueue) {
        addDebugLog('info', 'Restoring queue before start...');
        const result = await chrome.storage.local.get(["currentQueue", "completedCount"]);
        if (result.currentQueue) {
          currentQueue = result.currentQueue;
          completedCount = result.completedCount || 0;
        }
      }

      // Validate we can start
      if (!currentQueue || currentQueue.tasks.length === 0) {
        sendResponse({ success: false, error: "No queue loaded" });
        return;
      }

      if (isRunning) {
        sendResponse({ success: false, error: "Already running" });
        return;
      }

      // Send response immediately, then start fetching in background
      sendResponse({ success: true });

      // Start fetching (don't await - runs in background)
      startBackgroundFetching().catch(e => {
        console.error("[CatKnows] Background fetching error:", e);
        addDebugLog('error', `Background fetching crashed: ${e.message}`);
      });
    })();
    return true;
  }

  // Stop fetching (from popup)
  if (message.type === "STOP_FETCHING") {
    stopBackgroundFetching();
    sendResponse({ success: true });
    return true;
  }

  // Load queue (from popup)
  if (message.type === "LOAD_QUEUE") {
    (async () => {
      console.log("[CatKnows] LOAD_QUEUE for:", message.communityIds);
      const queue = await fetchQueueFromServer(message.communityIds);
      console.log("[CatKnows] Queue loaded:", queue);
      if (queue) {
        currentQueue = queue;
        completedCount = 0;
        fetchLog = [];
        saveQueueToStorage();
        broadcastState();
        sendResponse({ success: true, queue });
      } else {
        sendResponse({ success: false, error: "Failed to load queue" });
      }
    })();
    return true;
  }

  // Check queue now (from popup)
  if (message.type === "CHECK_QUEUE_NOW") {
    checkQueueAndNotify();
    sendResponse({ success: true });
    return true;
  }

  // Get fetch log (from popup)
  if (message.type === "GET_FETCH_LOG") {
    (async () => {
      const result = await chrome.storage.local.get(["fetchLog"]);
      sendResponse({ fetchLog: result.fetchLog || [] });
    })();
    return true;
  }

  // Community fetched notification (from content script)
  if (message.type === "COMMUNITY_FETCHED") {
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#10b981" });
    setTimeout(() => {
      chrome.action.setBadgeText({ text: "" });
    }, 3000);
  }

  return true;
});

// Initial queue check on startup
setTimeout(() => checkQueueAndNotify(), 5000);
