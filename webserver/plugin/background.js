// CatKnows Fetcher - Background Script (Firefox)
const API_URL = "http://localhost:3000";

// State
let tasks = [];
let results = [];
let isRunning = false;
let isPaused = false;
let shouldStop = false;
let currentTaskIndex = 0;
let lastTaskResult = null;

// ============================================================================
// API
// ============================================================================

async function loadTasks() {
    console.log('[bg] loadTasks() aufgerufen');
    console.log('[bg] Fetch:', `${API_URL}/api/fetch-tasks`);
    const res = await fetch(`${API_URL}/api/fetch-tasks`);
    console.log('[bg] Response status:', res.status);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    tasks = await res.json();
    console.log('[bg] Tasks geladen:', tasks);
    results = [];
    return tasks;
}

async function sendResult(taskResult) {
    console.log('[bg] sendResult() aufgerufen');
    const res = await fetch(`${API_URL}/api/fetch-result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results: [taskResult] })
    });
    console.log('[bg] Response status:', res.status);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    console.log('[bg] Server response:', data);
    return data;
}

// ============================================================================
// Fetch Logic - runs in Skool tab context
// ============================================================================

async function executeTask(tabId, task) {
    const code = `
        (async function() {
            const task = ${JSON.stringify(task)};

            // Get buildId from page
            const nextData = document.getElementById("__NEXT_DATA__");
            if (!nextData) return { error: "No __NEXT_DATA__ found" };

            const { buildId } = JSON.parse(nextData.textContent);
            if (!buildId) return { error: "No buildId found" };

            // Build URL based on task type
            let url;
            if (task.type === "members") {
                url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + "/-/members.json?t=active&p=" + task.pageParam + "&group=" + task.communitySlug;
            } else if (task.type === "posts") {
                url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + ".json?s=newest&p=" + task.pageParam;
            } else if (task.type === "profile") {
                // Profile page: /@username?group=communitySlug
                url = "https://www.skool.com/_next/data/" + buildId + "/@" + task.userName + ".json?group=" + task.communitySlug;
            } else if (task.type === "comments") {
                // Post detail page contains comments
                url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + "/" + task.postName + ".json?group=" + task.communitySlug + "&p=" + task.postName;
            } else if (task.type === "likes") {
                // Likes API endpoint
                url = "https://www.skool.com/api/post/" + task.postSkoolHexId + "/votes?tab=upvotes";
            } else if (task.type === "leaderboard") {
                // Leaderboard page
                url = "https://www.skool.com/_next/data/" + buildId + "/" + task.communitySlug + ".json?tab=leaderboard&p=" + task.pageParam + "&group=" + task.communitySlug;
            } else {
                return { error: "Unknown task type: " + task.type };
            }

            // Fetch data
            const res = await fetch(url, { credentials: "include" });
            if (!res.ok) return { error: "HTTP " + res.status };

            const data = await res.json();
            return { ok: true, type: task.type, data };
        })();
    `;

    const results = await browser.tabs.executeScript(tabId, { code });
    return results[0];
}

async function runAllTasks(resume = false) {
    console.log('[bg] runAllTasks() aufgerufen, resume:', resume);

    if (isRunning && !resume) {
        console.log('[bg] Already running, abort');
        return { error: "Already running" };
    }

    // Reset stop flag
    shouldStop = false;
    isPaused = false;
    isRunning = true;

    if (!resume) {
        results = [];
        currentTaskIndex = 0;
        console.log('[bg] Fresh start, results cleared');
    } else {
        console.log('[bg] Resuming from task index:', currentTaskIndex, 'results so far:', results.length);
    }

    // Find Skool tab
    console.log('[bg] Searching for Skool tab...');
    const tabs = await browser.tabs.query({ url: "https://www.skool.com/*" });
    if (!tabs.length) {
        console.error('[bg] No Skool tab found!');
        isRunning = false;
        return { error: "No Skool tab found" };
    }
    console.log('[bg] Found Skool tab:', tabs[0].id, tabs[0].url);

    // Execute tasks - reload task list after each fetch
    console.log('[bg] Starting task loop, tasks.length:', tasks.length);
    while (tasks.length > 0) {
        // Check for stop signal
        if (shouldStop) {
            console.log('[bg] STOP signal received, pausing...');
            isPaused = true;
            isRunning = false;
            return { ok: true, paused: true, results, message: "Stopped by user" };
        }

        currentTaskIndex++;
        const task = tasks[0];
        console.log('[bg] ========================================');
        console.log('[bg] Task', currentTaskIndex, '/', tasks.length);
        console.log('[bg] Task type:', task.type);
        console.log('[bg] Task details:', JSON.stringify(task));

        const startTime = Date.now();
        const result = await executeTask(tabs[0].id, task);
        const duration = Date.now() - startTime;

        console.log('[bg] Task completed in', duration, 'ms');
        console.log('[bg] Result:', result.error ? 'ERROR: ' + result.error : 'OK');

        lastTaskResult = { task, result };
        results.push(lastTaskResult);

        // Send result immediately
        console.log('[bg] Sending result to server...');
        try {
            await sendResult(lastTaskResult);
            console.log('[bg] Result sent successfully');
        } catch (e) {
            console.error('[bg] Failed to send result:', e);
        }

        // Reload tasks (server may have generated new ones)
        console.log('[bg] Reloading tasks from server...');
        await loadTasks();
        console.log('[bg] Tasks remaining:', tasks.length);

        // Delay between requests (5s to avoid rate limiting)
        if (tasks.length > 0) {
            console.log('[bg] Waiting 5s before next task...');
            await new Promise(r => setTimeout(r, 5000));
        }
    }

    console.log('[bg] ========================================');
    console.log('[bg] All tasks completed! Total results:', results.length);
    isRunning = false;
    isPaused = false;
    currentTaskIndex = 0;
    return { ok: true, results };
}

function stopTasks() {
    console.log('[bg] stopTasks() called');
    if (!isRunning) {
        console.log('[bg] Not running, nothing to stop');
        return { ok: false, message: "Not running" };
    }
    shouldStop = true;
    console.log('[bg] Stop signal set, will pause after current task');
    return { ok: true, message: "Stopping..." };
}

// ============================================================================
// Message Handler
// ============================================================================

browser.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    console.log('[bg] Message empfangen:', msg.type);

    if (msg.type === "LOAD_TASKS") {
        loadTasks()
            .then(t => { console.log('[bg] Sende tasks zurück:', t.length); sendResponse({ tasks: t }); })
            .catch(e => { console.error('[bg] Fehler:', e); sendResponse({ error: e.message }); });
        return true;
    }

    if (msg.type === "RUN_TASKS") {
        console.log('[bg] Starting RUN_TASKS...');
        runAllTasks(false).then(r => sendResponse(r)).catch(e => sendResponse({ error: e.message }));
        return true;
    }

    if (msg.type === "STOP_TASKS") {
        console.log('[bg] STOP_TASKS received');
        sendResponse(stopTasks());
        return true;
    }

    if (msg.type === "RESUME_TASKS") {
        console.log('[bg] RESUME_TASKS received, isPaused:', isPaused);
        if (!isPaused) {
            sendResponse({ error: "Not paused" });
            return true;
        }
        runAllTasks(true).then(r => sendResponse(r)).catch(e => sendResponse({ error: e.message }));
        return true;
    }

    if (msg.type === "GET_STATE") {
        const state = { tasks, results, isRunning, isPaused, currentTaskIndex, totalTasks: tasks.length };
        console.log('[bg] GET_STATE:', 'running:', isRunning, 'paused:', isPaused, 'tasks:', tasks.length);
        sendResponse(state);
        return true;
    }
});
