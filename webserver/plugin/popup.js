const loadBtn = document.getElementById('loadBtn');
const runBtn = document.getElementById('runBtn');
const stopBtn = document.getElementById('stopBtn');
const resumeBtn = document.getElementById('resumeBtn');
const tasksDiv = document.getElementById('tasks');
const statusDiv = document.getElementById('status');
const logDiv = document.getElementById('log');
let pollInterval = null;
let lastLogCount = 0;

function log(msg) {
    statusDiv.textContent = msg;
}

function addLogEntry(entry) {
    const cls = entry.error ? 'log-entry log-err' : (entry.isInfo ? 'log-entry log-info' : 'log-entry log-ok');
    const time = entry.time || new Date().toLocaleTimeString();
    const text = entry.error ? 'ERR: ' + entry.error : (entry.message || 'OK');
    const info = entry.type ? (entry.type + ' ' + (entry.info || '')) : '';
    const line = info ? '[' + time + '] ' + info + ' - ' + text : '[' + time + '] ' + text;
    logDiv.innerHTML += '<div class="' + cls + '">' + line + '</div>';
    logDiv.scrollTop = logDiv.scrollHeight;
}

function renderLog(logEntries) {
    if (!logEntries || logEntries.length === lastLogCount) return;
    // Nur neue Einträge hinzufügen
    for (let i = lastLogCount; i < logEntries.length; i++) {
        addLogEntry(logEntries[i]);
    }
    lastLogCount = logEntries.length;
}

function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(updateProgress, 1000);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function updateProgress() {
    browser.runtime.sendMessage({ type: 'GET_STATE' }).then(function(state) {
        console.log('[popup] State:', state);
        if (state && state.logEntries) {
            renderLog(state.logEntries);
        }
        if (state && state.isRunning && state.totalTasks > 0) {
            log('Fetching ' + state.currentTaskIndex + ' / ' + state.totalTasks + '...');
            stopBtn.disabled = false;
            resumeBtn.disabled = true;
        } else if (state && state.isPaused) {
            stopPolling();
            log('Paused at task ' + state.currentTaskIndex + '. ' + state.results.length + ' done.');
            renderResults(state.results);
            stopBtn.disabled = true;
            resumeBtn.disabled = false;
            runBtn.disabled = true;
            loadBtn.disabled = false;
        } else if (state && !state.isRunning) {
            stopPolling();
            if (state.results && state.results.length) {
                renderResults(state.results);
                log('Fertig! ' + state.results.length + ' Tasks ausgeführt');
            }
            runBtn.disabled = false;
            loadBtn.disabled = false;
            stopBtn.disabled = true;
            resumeBtn.disabled = true;
        }
    });
}

function renderTasks(tasks) {
    tasksDiv.innerHTML = tasks.map(t => {
        let info = t.communitySlug;
        if (t.type === 'profile') info += ' @' + t.userName;
        else if (t.type === 'comments' || t.type === 'likes') info += ' ' + t.postName;
        else info += ' (page ' + t.pageParam + ')';
        return '<div class="task">' + t.type + ': ' + info + '</div>';
    }).join('');
}

function renderResults(results) {
    tasksDiv.innerHTML = results.map(r => {
        const cls = r.result.error ? 'task error' : 'task result';
        const text = r.result.error || 'OK: ' + r.task.type;
        return '<div class="' + cls + '">' + r.task.type + ': ' + text + '</div>';
    }).join('');
}

loadBtn.onclick = function() {
    log('Button geklickt!');
    loadBtn.disabled = true;
    logDiv.innerHTML = '';
    lastLogCount = 0;

    browser.runtime.sendMessage({ type: 'LOAD_TASKS' })
        .then(function(res) {
            if (!res) {
                log('Keine Antwort vom Background');
            } else if (res.error) {
                log('Fehler: ' + res.error);
            } else {
                renderTasks(res.tasks);
                runBtn.disabled = false;
                log(res.tasks.length + ' Tasks geladen');
            }
            loadBtn.disabled = false;
        })
        .catch(function(e) {
            log('Fehler: ' + e.message);
            loadBtn.disabled = false;
        });
};

runBtn.onclick = function() {
    console.log('[popup] Run clicked');
    log('Starte...');
    runBtn.disabled = true;
    loadBtn.disabled = true;
    stopBtn.disabled = false;
    resumeBtn.disabled = true;

    // Kurz warten damit der erste Task startet, dann polling
    setTimeout(startPolling, 500);

    browser.runtime.sendMessage({ type: 'RUN_TASKS' })
        .then(function(res) {
            console.log('[popup] RUN_TASKS response:', res);
            stopPolling();
            if (!res) {
                log('Keine Antwort');
            } else if (res.error) {
                log('Fehler: ' + res.error);
            } else if (res.paused) {
                log('Paused. ' + res.results.length + ' done.');
                renderResults(res.results);
                resumeBtn.disabled = false;
                return;
            } else {
                renderResults(res.results);
                log('Fertig! ' + res.results.length + ' Tasks ausgeführt');
            }
            runBtn.disabled = false;
            loadBtn.disabled = false;
            stopBtn.disabled = true;
            resumeBtn.disabled = true;
        })
        .catch(function(e) {
            console.error('[popup] RUN_TASKS error:', e);
            stopPolling();
            log('Fehler: ' + e.message);
            runBtn.disabled = false;
            loadBtn.disabled = false;
            stopBtn.disabled = true;
        });
};

stopBtn.onclick = function() {
    console.log('[popup] Stop clicked');
    log('Stopping...');
    stopBtn.disabled = true;

    browser.runtime.sendMessage({ type: 'STOP_TASKS' })
        .then(function(res) {
            console.log('[popup] STOP_TASKS response:', res);
            if (res && res.ok) {
                log('Stopping after current task...');
            } else {
                log('Stop failed: ' + (res ? res.message : 'No response'));
                stopBtn.disabled = false;
            }
        })
        .catch(function(e) {
            console.error('[popup] STOP_TASKS error:', e);
            log('Stop error: ' + e.message);
            stopBtn.disabled = false;
        });
};

resumeBtn.onclick = function() {
    console.log('[popup] Resume clicked');
    log('Resuming...');
    resumeBtn.disabled = true;
    stopBtn.disabled = false;
    loadBtn.disabled = true;

    setTimeout(startPolling, 500);

    browser.runtime.sendMessage({ type: 'RESUME_TASKS' })
        .then(function(res) {
            console.log('[popup] RESUME_TASKS response:', res);
            stopPolling();
            if (!res) {
                log('Keine Antwort');
            } else if (res.error) {
                log('Fehler: ' + res.error);
            } else if (res.paused) {
                log('Paused again. ' + res.results.length + ' done.');
                renderResults(res.results);
                resumeBtn.disabled = false;
                stopBtn.disabled = true;
                return;
            } else {
                renderResults(res.results);
                log('Fertig! ' + res.results.length + ' Tasks ausgeführt');
            }
            runBtn.disabled = false;
            loadBtn.disabled = false;
            stopBtn.disabled = true;
            resumeBtn.disabled = true;
        })
        .catch(function(e) {
            console.error('[popup] RESUME_TASKS error:', e);
            stopPolling();
            log('Fehler: ' + e.message);
            resumeBtn.disabled = false;
            loadBtn.disabled = false;
            stopBtn.disabled = true;
        });
};

// Load initial state
browser.runtime.sendMessage({ type: 'GET_STATE' }).then(function(state) {
    console.log('[popup] Initial state:', state);
    if (state && state.tasks && state.tasks.length) renderTasks(state.tasks);
    if (state && state.results && state.results.length) renderResults(state.results);
    if (state && state.logEntries && state.logEntries.length) {
        logDiv.innerHTML = '';
        lastLogCount = 0;
        renderLog(state.logEntries);
    }
    runBtn.disabled = !(state && state.tasks && state.tasks.length);

    // If currently running, show progress and start polling
    if (state && state.isRunning) {
        log('Fetching ' + state.currentTaskIndex + ' / ' + state.totalTasks + '...');
        runBtn.disabled = true;
        loadBtn.disabled = true;
        stopBtn.disabled = false;
        resumeBtn.disabled = true;
        startPolling();
    } else if (state && state.isPaused) {
        log('Paused at task ' + state.currentTaskIndex + '. ' + state.results.length + ' done.');
        runBtn.disabled = true;
        loadBtn.disabled = false;
        stopBtn.disabled = true;
        resumeBtn.disabled = false;
    } else {
        stopBtn.disabled = true;
        resumeBtn.disabled = true;
    }
});
