// CatKnows Background Service Worker
const GO_CLIENT_URL = "http://localhost:3000";

console.log("[CatKnows] Background service worker started");

// Listen for installation
chrome.runtime.onInstalled.addListener((details) => {
  console.log("[CatKnows] Extension installed:", details.reason);

  // Initialize storage
  chrome.storage.local.get(["fetchedCommunities"], (result) => {
    if (!result.fetchedCommunities) {
      chrome.storage.local.set({ fetchedCommunities: {} });
    }
  });
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("[CatKnows] Message received:", message);

  if (message.type === "COMMUNITY_FETCHED") {
    // Update badge to show activity
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#10b981" });

    // Clear badge after 3 seconds
    setTimeout(() => {
      chrome.action.setBadgeText({ text: "" });
    }, 3000);
  }

  // Handle sync to Go client (from content script to avoid Mixed Content)
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
    return true; // Keep the message channel open for async response
  }

  return true;
});
