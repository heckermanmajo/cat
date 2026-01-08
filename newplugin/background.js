// CatKnows Fetcher - Background Script (Firefox)
const API_URL = "http://localhost:3000";

// State
let tasks = [];
let results = [];
let isRunning = false;
let currentTaskIndex = 0;

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

async function sendResults() {
    console.log('[bg] sendResults() aufgerufen');
    const res = await fetch(`${API_URL}/api/fetch-result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results })
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

async function runAllTasks() {
    if (isRunning) return { error: "Already running" };
    isRunning = true;
    results = [];
    currentTaskIndex = 0;

    // Find Skool tab
    const tabs = await browser.tabs.query({ url: "https://www.skool.com/*" });
    if (!tabs.length) {
        isRunning = false;
        return { error: "No Skool tab found" };
    }

    // Execute each task
    for (let i = 0; i < tasks.length; i++) {
        currentTaskIndex = i + 1;
        const result = await executeTask(tabs[0].id, tasks[i]);
        results.push({ task: tasks[i], result });
        // Delay between requests (5s to avoid rate limiting)
        if (i < tasks.length - 1) {
            await new Promise(r => setTimeout(r, 5000));
        }
    }

    // Send results to server
    const serverResponse = await sendResults();

    isRunning = false;
    currentTaskIndex = 0;
    return { ok: true, results, serverResponse };
}

// ============================================================================
// Message Handler
// ============================================================================

browser.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    console.log('[bg] Message empfangen:', msg);
    if (msg.type === "LOAD_TASKS") {
        loadTasks()
            .then(t => { console.log('[bg] Sende tasks zurück'); sendResponse({ tasks: t }); })
            .catch(e => { console.error('[bg] Fehler:', e); sendResponse({ error: e.message }); });
        return true;
    }
    if (msg.type === "RUN_TASKS") {
        runAllTasks().then(r => sendResponse(r)).catch(e => sendResponse({ error: e.message }));
        return true;
    }
    if (msg.type === "GET_STATE") {
        sendResponse({ tasks, results, isRunning, currentTaskIndex, totalTasks: tasks.length });
        return true;
    }
});
