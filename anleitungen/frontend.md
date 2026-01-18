# Frontend Code Style Guide

This document describes the frontend architecture based on `members.html` as the reference implementation.

## Core Principles

1. **Self-Contained Pages** - Each HTML page is a standalone file with all JS embedded in `<head>`
2. **No Build Tools** - Vanilla JS, no transpilers, no bundlers, no frameworks
3. **Simple > DRY** - Decoupling is more important than avoiding code duplication
4. **Page Reload > SPA** - Use `window.location.reload()` for state changes (fast because everything is local)
5. **Persist UI State** - Store UI preferences in DB via `ConfigEntry`

## File Structure

```
myversion/static/
├── members.html      # Self-contained page
├── posts.html        # Self-contained page
├── entity.js         # Base class for entities
├── lib.js            # Shared utilities (loading, themes, etc.)
├── default.css       # Global styles
└── entities/
    ├── config_entry.js
    ├── user.js
    └── post.js
```

## HTML Page Template

```html
<!DOCTYPE html>
<html lang="en">
    <head>
        <!-- 1. External libs from CDN -->
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <!-- 2. Shared modules -->
        <script src="entity.js"></script>
        <script src="/entities/config_entry.js"></script>
        <script src="/entities/user.js"></script>
        <script src="/lib.js"></script>
        <link href="/default.css" type="text/css" rel="stylesheet">

        <title>Cat</title>
        <script>
            // =========================================================================
            // REGION NAME - Description
            // =========================================================================

            // ... all page-specific JS goes here ...

        </script>
    </head>
    <body>
        <!-- HTML structure -->
    </body>
</html>
```

## Code Organization with Regions

Use comment blocks to organize code into logical sections:

```javascript
// =========================================================================
// Graph Rendering (Vis.js) - Interaktionen zwischen Usern
// =========================================================================

// ... code ...

//
//
// region MEMBERS
//
//
```

## State Management

### Global Variables

State is stored in simple global `let` variables at page level:

```javascript
// Data
let members = [];
let membersPage = 1;
const membersLimit = 400;

// UI state
let filterExpanded = false;
let currentView = "list";
let currentCommunity = "";
```

### Persisting UI State

UI preferences are stored in the database via `ConfigEntry`:

```javascript
// Config keys follow pattern: "page.setting_name"
const membersFilterExpandedKey = "members.filter_expanded";
const membersViewConfigKey = "members.current_view";

// Save state
ConfigEntry.set(membersFilterExpandedKey, filterExpanded.toString()).then();

// Load state
const view = await ConfigEntry.get(membersViewConfigKey);
if (view) currentView = view;
```

## API Communication

### Using get() and post()

API calls use the wrapper functions from `lib.js`:

```javascript
// GET request
const res = await get(`/api/user/${memberId}/posts`);
if (res.ok) {
    const data = res.data;
}

// POST request
const res = await post('/api/user/filter', filterState);
if (res.ok) {
    members = res.data;
}
```

### Parallel API Calls

Use `Promise.all` for independent requests:

```javascript
const [postsRes, communitiesRes, likedPostsRes] = await Promise.all([
    get(`/api/user/${memberId}/posts`),
    get(`/api/user/${memberId}/communities`),
    get(`/api/user/${memberId}/liked-posts`)
]);
```

## Loading & Rendering Pattern

### Show Loading Animation

```javascript
let loadMembers = async (skipAnimation = false) => {
    if (!skipAnimation) lib.showLoading();
    const res = await post('/api/user/filter', filterState);
    if (!skipAnimation) lib.hideLoading();
    if (res.ok) {
        members = res.data;
        renderMembersView();
    }
};
```

### HTML Rendering with Template Literals

```javascript
const renderMemberCard = (member, showJson = false) => {
    return `
        <article onclick="loadAndRenderProfileDetails(${member.id})" style="cursor: pointer">
            <b>@${member.name}</b> - ${member.first_name} ${member.last_name}<br>
            <small>
                Role: <b>${member.member_role || '-'}</b> |
                Points: <b>${member.points || 0}</b>
            </small>
            ${showJson ? `<pre>${JSON.stringify(member, null, 2)}</pre>` : ''}
        </article>
    `;
};
```

### Inserting HTML

```javascript
// Clear and rebuild
membersView.innerHTML = "";

// Append items
for (let member of pageMembers) {
    membersList.insertAdjacentHTML("beforeend", renderMemberCard(member));
}

// Direct assignment
secondaryView.innerHTML = html;
```

## Event Handling

### Inline onclick Handlers

Prefer inline handlers for simplicity:

```html
<button onclick="toggleFilterExpanded()">Show Filter</button>
<article onclick="loadAndRenderProfileDetails(${member.id})">...</article>
<select onchange="setCurrentView(this.value)">...</select>
```

### window.onload Pattern

Use IIFE for async initialization:

```javascript
let initialLoading = true;
window.onload = () => {
    lib.showLoading('waking up');

    (async () => {
        // Load view preference
        await getCurrentView();

        // Setup select element
        const select = document.getElementById("membersViewSelection");
        select.value = currentView;
        select.onchange = () => setCurrentView(select.value);

        // Load data
        await loadMembers(true);

        initialLoading = false;
        lib.hideLoading();
    })().then();

    // Parallel non-async setup
    ConfigEntry.get(membersFilterExpandedKey).then((value) => {
        filterExpanded = value === "true";
        // ...
    });
};
```

## View Switching

### Main View (List/Card/Graph)

```javascript
let setCurrentView = (view) => {
    currentView = view;
    ConfigEntry.set(membersViewConfigKey, view).then();
    renderMembersView();
};

const renderMembersView = () => {
    const membersView = document.getElementById("members-view");
    membersView.innerHTML = "";

    switch(currentView) {
        case "list": {
            // render list
        } break;
        case "card": {
            // render cards
        } break;
        case "graph": {
            // render graph
        } break;
        default:
            membersView.innerHTML = "UNKNOWN VIEW -> this is a bug";
            break;
    }
};
```

## Navigation

### Page Navigation via Select

```html
<select id="viewSelection" onchange="window.location.href=this.value">
    <option value="/members.html" selected> MEMBERS </option>
    <option value="/posts.html"> POSTS </option>
    <option value="/communities.html"> COMMUNITIES </option>
</select>
```

### Community Change with Reload

```javascript
let changeCurrentCommunity = (community) => {
    ConfigEntry.set("current_community", community).then(() => {
        window.location.reload();
    });
};
```

## Styling

### Inline Styles for Layout

Use inline styles for page-specific layouts:

```javascript
html += `<article style="margin: 4px 0; padding: 8px; border-left: 3px solid #3498db">
    <b>${title}</b><br>
    <small>by <b>${p.user_name || '-'}</b></small>
</article>`;
```

### CSS Classes for Global Styles

Use `default.css` for reusable styles like buttons, inputs, and the loading indicator.

## Dialog Pattern

Create dialogs dynamically:

```javascript
let openFilterDialog = (mode) => {
    // Remove existing dialogs
    document.querySelectorAll('dialog').forEach(d => d.remove());

    let dialogHtml = `
        <dialog>
            <h4>Title</h4>
            <!-- content -->
            <button onclick="this.closest('dialog').close()">Close</button>
        </dialog>
    `;

    document.body.insertAdjacentHTML('beforeend', dialogHtml);
    setTimeout(() => {
        document.querySelector('dialog').showModal();
    }, 100);
};
```

## Filter State Pattern

```javascript
let filterState = {
    sortBy: 'name_asc',
    searchTerm: '',
    include: {},
    exclude: {}
};

let setFilterCondition = (mode, key, value) => {
    if (value === "-1" || value === "false" || value === null) {
        delete filterState[mode][key];
    } else {
        filterState[mode][key] = value;
    }
    renderFilterConditions();
    loadMembers();
};
```

## Helper Functions

### Date Formatting

```javascript
const formatDate = (ts) => ts ? new Date(ts * 1000).toLocaleDateString() : '-';

const formatAge = (ts) => {
    if (!ts) return '-';
    const now = Math.floor(Date.now() / 1000);
    const diff = now - ts;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + ' min';
    if (diff < 86400) return Math.floor(diff / 3600) + ' hrs';
    return Math.floor(diff / 86400) + ' days';
};
```

## Summary: Do's and Don'ts

### DO
- Keep each page self-contained
- Use global variables for page state
- Persist UI state via ConfigEntry
- Use page reload for major state changes
- Use inline onclick handlers
- Use template literals for HTML generation
- Use `Promise.all` for parallel API calls
- Organize code with region comments

### DON'T
- Don't use frameworks (React, Vue, etc.)
- Don't use build tools (Webpack, Vite, etc.)
- Don't create shared components (each page renders its own HTML)
- Don't use SPA navigation patterns
- Don't over-abstract - duplicate code is fine if it keeps pages independent
