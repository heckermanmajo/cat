lib = {}
lib.primaryColorRGB = [32, 178, 170]; // default: lightseagreen
lib.setTheme = async function (themeName){
    ConfigEntry.set('theme', themeName).then()
    const themes = {
        blue:   { color: "lightseagreen", rgb: [32, 178, 170] },
        red:    { color: "crimson",       rgb: [220, 20, 60] },
        green:  { color: "lightgreen",    rgb: [144, 238, 144] },
        purple: { color: "#a855f7",       rgb: [168, 85, 247] },
        orange: { color: "#f97316",       rgb: [249, 115, 22] },
        pink:   { color: "#ec4899",       rgb: [236, 72, 153] },
        cyan:   { color: "#06b6d4",       rgb: [6, 182, 212] },
        gold:   { color: "#eab308",       rgb: [234, 179, 8] }
    };
    const theme = themes[themeName] || themes.blue;
    let color = theme.color;
    lib.primaryColorRGB = theme.rgb;
    let css = `
        button, a, select, b, h1, h2, h3, h4, h5, h6{ color: ${color} !important; }
        input[type="checkbox"]{ accent-color: ${color} !important;}
    `;
    let style = document.getElementById("dynamicThemeStyle");
    if(!style){
        style = document.createElement('style');
        style.id = "dynamicThemeStyle";
        document.head.appendChild(style);
    }
    style.innerHTML = css;
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: themeName, rgb: theme.rgb } }));
};
lib.setupThemeOnLoad = async function (){
    let themeName = await ConfigEntry.get('theme');
    if(!themeName) {await ConfigEntry.set('theme', 'red'); themeName = 'red';}
    lib.setTheme(themeName).then();
    const themeSelection = document.getElementById("themeSelection");
    if(themeSelection)
        for(let o of themeSelection.options)
            if(o.value === themeName) o.selected = "true";
};
lib.error = function(message, data){ console.error(message); console.error(data); } // todo

lib.loadAllCommunities = async () => {
    let communityListData; const communitiesKey = "communities";
    let name = await ConfigEntry.get(communitiesKey);
    communityListData = name ? name : "[]";
    try { communityListData = JSON.parse(communityListData);
    } catch (e){ lib.error(e, communityListData); }
    communityListData = Array.from(communityListData.filter(c => c !== ""));
    console.log("loaded communities:", communityListData);
    return communityListData;
}
// todo: breaks currently if we use select...
lib.addEventHandlerToCloseDialogByClickingOutside = (dialogElement) => {
    dialogElement.addEventListener("click", (event) => {
        const rect = dialogElement.getBoundingClientRect();
        const clickedInDialog =
            event.clientX >= rect.left &&
            event.clientX <= rect.right &&
            event.clientY >= rect.top &&
            event.clientY <= rect.bottom;
        if (!clickedInDialog) dialogElement.close();
    });
}

// Error Dialog
lib.errorDialog = null;
lib.showError = function(title, message) {
    console.error(`[ERROR] ${title}:`, message);
    if (!lib.errorDialog) {
        lib.errorDialog = document.createElement('dialog');
        lib.errorDialog.innerHTML = `
            <h3 id="errTitle" style="color:crimson"></h3>
            <pre id="errMsg" style="max-width:500px;max-height:300px;overflow:auto"></pre>
            <iframe id="errIframe" style="width:600px;height:400px;border:1px solid #333;display:none"></iframe>
            <br><button onclick="this.closest('dialog').close()">OK</button>
        `;
        document.body.appendChild(lib.errorDialog);
    }
    const msgStr = String(message);
    const isHtml = msgStr.trim().startsWith('<!') || msgStr.trim().startsWith('<html');
    const preEl = lib.errorDialog.querySelector('#errMsg');
    const iframeEl = lib.errorDialog.querySelector('#errIframe');

    lib.errorDialog.querySelector('#errTitle').textContent = title;
    if (isHtml) {
        preEl.style.display = 'none';
        iframeEl.style.display = 'block';
        iframeEl.srcdoc = msgStr;
    } else {
        preEl.style.display = 'block';
        iframeEl.style.display = 'none';
        preEl.textContent = msgStr;
    }
    lib.errorDialog.showModal();
};

// Global error handlers - immer auch in Konsole loggen
window.onerror = (msg, src, line, col, error) => {
    console.error('[JS ERROR]', msg, `\n  at ${src}:${line}:${col}`, error);
    lib.showError('JS Error', `${msg}\n${src}:${line}`);
};
window.onunhandledrejection = (e) => {
    console.error('[PROMISE ERROR]', e.reason);
    lib.showError('Promise Error', e.reason);
};

// Cat Loading Animation
lib.loadingOverlay = null;
lib.loadingInterval = null;
lib.catEmojis = ['🐱', '😺', '😸', '😹', '😻', '😼', '😽', '🙀', '😿', '😾', '🐈', '🐈‍⬛'];
lib.loadingTexts = ['thinking', 'doodling', 'miauing', 'purring', 'napping', 'stretching', 'hunting', 'grooming', 'exploring', 'sneaking'];

lib.showLoading = function(customText, options = {}) {
    if (lib.loadingOverlay) return;

    const { onCancel, warning, showProgress } = options;

    lib.loadingOverlay = document.createElement('div');
    lib.loadingOverlay.id = 'catLoadingOverlay';
    lib.loadingOverlay.innerHTML = `
        <style>
            #catLoadingOverlay {
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.7); z-index: 9999;
                display: flex; flex-direction: column; align-items: center; justify-content: center;
            }
            #catLoadingOverlay .cat-container {
                position: relative; width: 200px; height: 150px; overflow: hidden;
            }
            #catLoadingOverlay .floating-cat {
                position: absolute; font-size: 2rem;
                animation: floatUp 2s ease-out forwards;
            }
            @keyframes floatUp {
                0% { transform: translateY(100px) scale(0.5); opacity: 0; }
                20% { opacity: 1; }
                80% { opacity: 1; }
                100% { transform: translateY(-100px) scale(1.2); opacity: 0; }
            }
            #catLoadingOverlay .loading-text {
                font-size: 1.5rem; color: white; margin-top: 20px;
                font-family: monospace;
            }
            #catLoadingOverlay .dots::after {
                content: ''; animation: dots 1.5s infinite;
            }
            @keyframes dots {
                0%, 20% { content: '.'; }
                40% { content: '..'; }
                60%, 100% { content: '...'; }
            }
            #catLoadingOverlay .loading-progress {
                color: #888; font-size: 1rem; margin-top: 10px;
            }
            #catLoadingOverlay .loading-warning {
                color: #f85149; font-size: 1rem; font-weight: bold; margin-top: 15px;
            }
            #catLoadingOverlay .loading-cancel {
                margin-top: 20px; background: #f85149; color: #fff; border: none;
                padding: 10px 25px; font-size: 1rem; cursor: pointer; border-radius: 5px;
            }
            #catLoadingOverlay progress {
                width: 250px; height: 12px; margin-top: 10px;
            }
        </style>
        <div class="cat-container" id="catContainer"></div>
        <div class="loading-text"><span id="loadingTextContent">thinking</span><span class="dots"></span></div>
        ${showProgress ? '<div class="loading-progress" id="loadingProgress">0 / 0</div><progress id="loadingProgressBar" value="0" max="100"></progress>' : ''}
        ${warning ? `<div class="loading-warning">${warning}</div>` : ''}
        ${onCancel ? '<button class="loading-cancel" id="loadingCancelBtn">Abbrechen</button>' : ''}
    `;
    document.body.appendChild(lib.loadingOverlay);

    if (onCancel) {
        lib.loadingOverlay.querySelector('#loadingCancelBtn').onclick = onCancel;
    }

    // Spawn cats
    const container = lib.loadingOverlay.querySelector('#catContainer');
    const spawnCat = () => {
        const cat = document.createElement('span');
        cat.className = 'floating-cat';
        cat.textContent = lib.catEmojis[Math.floor(Math.random() * lib.catEmojis.length)];
        cat.style.left = (Math.random() * 160 + 20) + 'px';
        container.appendChild(cat);
        setTimeout(() => cat.remove(), 2000);
    };
    spawnCat();
    lib.loadingInterval = setInterval(spawnCat, 400);

    // Change text
    const textEl = lib.loadingOverlay.querySelector('#loadingTextContent');
    if (customText) {
        textEl.textContent = customText;
    } else {
        const changeText = () => {
            textEl.textContent = lib.loadingTexts[Math.floor(Math.random() * lib.loadingTexts.length)];
        };
        lib.textInterval = setInterval(changeText, 2000);
    }
};

lib.updateLoadingProgress = function(current, total) {
    if (!lib.loadingOverlay) return;
    const progressEl = lib.loadingOverlay.querySelector('#loadingProgress');
    const barEl = lib.loadingOverlay.querySelector('#loadingProgressBar');
    if (progressEl) progressEl.textContent = `${current} / ${total}`;
    if (barEl) barEl.value = total > 0 ? Math.round((current / total) * 100) : 0;
};

lib.hideLoading = function() {
    if (lib.loadingInterval) { clearInterval(lib.loadingInterval); lib.loadingInterval = null; }
    if (lib.textInterval) { clearInterval(lib.textInterval); lib.textInterval = null; }
    if (lib.loadingOverlay) { lib.loadingOverlay.remove(); lib.loadingOverlay = null; }
};