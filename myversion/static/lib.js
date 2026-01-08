lib = {}
lib.setTheme = async function (themeName){
    ConfigEntry.set('theme', themeName).then()
    let color = "lightseagreen";
    if (themeName === "green") color = "lightgreen";
    if (themeName === "red") color = "crimson";
    let colorElements = "button, a, select, b, h1, h2, h3, h4, h5, h6";
    document.querySelectorAll(colorElements).forEach(el => el.style.color = color);
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