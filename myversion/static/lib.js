lib = {}
lib.setTheme = async function (themeName){
    ConfigEntry.set('theme', themeName).then()
    let color = "lightseagreen";
    if (themeName === "green") color = "lightgreen";
    if (themeName === "red") color = "crimson";
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