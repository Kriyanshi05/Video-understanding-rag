/**
 * background.js - Background Service Worker for Video Understanding
 *
 * Responsibilities:
 * - Listens for clicks on the extension action icon in the browser toolbar.
 * - Opens the extension side panel for the active tab using chrome.sidePanel.open().
 */

chrome.action.onClicked.addListener(async (tab) => {
  try {
    if (tab?.id) {
      // Open the side panel targeting the active tab
      await chrome.sidePanel.open({ tabId: tab.id });
    } else if (tab?.windowId) {
      // Fallback targeting the window if tabId is unavailable
      await chrome.sidePanel.open({ windowId: tab.windowId });
    }
  } catch (err) {
    console.error("Video Understanding: Failed to open side panel", err);
  }
});
