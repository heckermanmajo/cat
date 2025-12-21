// CatKnows Content Script - Auto-fetches community data on Skool pages

const GO_CLIENT_URL = "http://localhost:3000";

// Extract community slug from URL
// Patterns: skool.com/community-name, skool.com/community-name/about, etc.
function getCommunitySlug() {
  const path = window.location.pathname;

  // Skip non-community pages
  const skipPatterns = [
    /^\/$/,                    // homepage
    /^\/discover/,             // discover page
    /^\/settings/,             // settings
    /^\/notifications/,        // notifications
    /^\/chat/,                 // chat
    /^\/@/,                    // user profiles
    /^\/search/,               // search
  ];

  for (const pattern of skipPatterns) {
    if (pattern.test(path)) {
      return null;
    }
  }

  // Extract first path segment as community slug
  const match = path.match(/^\/([a-zA-Z0-9-]+)/);
  if (match) {
    return match[1];
  }

  return null;
}

// Get Next.js build ID from the page
function getBuildId() {
  const nextDataScript = document.getElementById("__NEXT_DATA__");
  if (nextDataScript) {
    try {
      const data = JSON.parse(nextDataScript.textContent);
      return data.buildId;
    } catch (e) {
      console.error("[CatKnows] Failed to parse __NEXT_DATA__:", e);
    }
  }
  return null;
}

// Show toast notification
function showToast(message, isError = false) {
  // Remove existing toast if any
  const existing = document.getElementById("catknows-toast");
  if (existing) {
    existing.remove();
  }

  const toast = document.createElement("div");
  toast.id = "catknows-toast";
  toast.innerHTML = `
    <style>
      #catknows-toast {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 14px;
        z-index: 999999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: catknows-slide-in 0.3s ease-out;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      #catknows-toast.success {
        background: #10b981;
        color: white;
      }
      #catknows-toast.error {
        background: #ef4444;
        color: white;
      }
      #catknows-toast.info {
        background: #3b82f6;
        color: white;
      }
      @keyframes catknows-slide-in {
        from {
          transform: translateX(100%);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
    </style>
    <span>${isError ? '✗' : '✓'}</span>
    <span>${message}</span>
  `;

  toast.className = isError ? "error" : "success";
  document.body.appendChild(toast);

  // Auto-remove after 4 seconds
  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.animation = "catknows-slide-in 0.3s ease-out reverse";
      setTimeout(() => toast.remove(), 300);
    }
  }, 4000);
}

// Fetch the about page data
async function fetchAboutPage(slug, buildId) {
  const url = `https://www.skool.com/_next/data/${buildId}/${slug}/about.json?group=${slug}`;

  console.log("[CatKnows] Fetching:", url);

  const response = await fetch(url, {
    credentials: "include",  // Use user's cookies
    headers: {
      "Accept": "application/json",
    }
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json();
}

// Send data to Go client via background script (to avoid Mixed Content issues)
async function sendToGoClient(slug, data) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({
      type: "SYNC_TO_GO_CLIENT",
      payload: {
        action: "fetch",
        timestamp: new Date().toISOString(),
        entityType: "community-about",
        source: "skool",
        data: {
          id: slug,
          slug: slug,
          ...data
        }
      }
    }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else if (response && response.success) {
        resolve(response);
      } else {
        reject(new Error(response?.error || "Unknown error"));
      }
    });
  });
}

// Check if community was already fetched
async function wasCommunityFetched(slug) {
  return new Promise((resolve) => {
    chrome.storage.local.get(["fetchedCommunities"], (result) => {
      const fetched = result.fetchedCommunities || {};
      resolve(!!fetched[slug]);
    });
  });
}

// Mark community as fetched
async function markCommunityFetched(slug) {
  return new Promise((resolve) => {
    chrome.storage.local.get(["fetchedCommunities"], (result) => {
      const fetched = result.fetchedCommunities || {};
      fetched[slug] = {
        fetchedAt: new Date().toISOString()
      };
      chrome.storage.local.set({ fetchedCommunities: fetched }, resolve);
    });
  });
}

// Main function
async function main() {
  const slug = getCommunitySlug();

  if (!slug) {
    console.log("[CatKnows] Not a community page, skipping");
    return;
  }

  console.log("[CatKnows] Detected community:", slug);

  // Check if already fetched
  const alreadyFetched = await wasCommunityFetched(slug);
  if (alreadyFetched) {
    console.log("[CatKnows] Community already fetched, skipping");
    return;
  }

  // Get build ID
  const buildId = getBuildId();
  if (!buildId) {
    console.error("[CatKnows] Could not get build ID");
    showToast("Konnte Build-ID nicht ermitteln", true);
    return;
  }

  console.log("[CatKnows] Build ID:", buildId);

  try {
    // Fetch about page
    showToast(`Lade Community "${slug}"...`, false);
    const aboutData = await fetchAboutPage(slug, buildId);

    console.log("[CatKnows] About data fetched:", aboutData);

    // Send to Go client
    try {
      await sendToGoClient(slug, aboutData);
      showToast(`Community "${slug}" erfolgreich synchronisiert!`, false);
    } catch (goError) {
      console.warn("[CatKnows] Go client not available:", goError);
      showToast(`Community "${slug}" geladen (Go-Client offline)`, false);
    }

    // Mark as fetched
    await markCommunityFetched(slug);

  } catch (error) {
    console.error("[CatKnows] Fetch error:", error);
    showToast(`Fehler beim Laden: ${error.message}`, true);
  }
}

// Run on page load
main();
