const loadBtn = document.getElementById('loadBtn');
const runBtn = document.getElementById('runBtn');
const tasksDiv = document.getElementById('tasks');
const statusDiv = document.getElementById('status');

function log(msg) {
    statusDiv.textContent = msg;
}

function renderTasks(tasks) {
    tasksDiv.innerHTML = tasks.map(t =>
        '<div class="task">' + t.type + ': ' + t.communitySlug + ' (page ' + t.pageParam + ')</div>'
    ).join('');
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
    log('Starte Ausführung...');
    runBtn.disabled = true;

    browser.runtime.sendMessage({ type: 'RUN_TASKS' })
        .then(function(res) {
            if (!res) {
                log('Keine Antwort');
            } else if (res.error) {
                log('Fehler: ' + res.error);
            } else {
                renderResults(res.results);
                log('Fertig! ' + res.results.length + ' Tasks ausgeführt');
            }
            runBtn.disabled = false;
        })
        .catch(function(e) {
            log('Fehler: ' + e.message);
            runBtn.disabled = false;
        });
};

// Load initial state
browser.runtime.sendMessage({ type: 'GET_STATE' }).then(function(state) {
    if (state && state.tasks && state.tasks.length) renderTasks(state.tasks);
    if (state && state.results && state.results.length) renderResults(state.results);
    runBtn.disabled = !(state && state.tasks && state.tasks.length);
});
