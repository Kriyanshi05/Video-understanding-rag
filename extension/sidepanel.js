/**
 * sidepanel.js - Script for sidepanel.html
 *
 * Responsibilities:
 * 1. Reads the current YouTube video ID from chrome.storage.local on initial load.
 * 2. Displays the video ID in plain text on the page.
 * 3. Listens for live updates via chrome.storage.onChanged to keep the display
 *    in sync as the user browses YouTube videos.
 */

const displayEl = document.getElementById("video-id-display");

/**
 * Updates the text display element with the current video ID or a fallback message.
 * @param {string|null} videoId - The YouTube video ID or null/undefined
 */
function updateDisplay(videoId) {
  if (videoId) {
    displayEl.textContent = `Current video: ${videoId}`;
  } else {
    displayEl.textContent = "No video detected";
  }
}

/**
 * Loads the current video ID from local storage.
 */
async function init() {
  try {
    const { currentVideoId } = await chrome.storage.local.get("currentVideoId");
    updateDisplay(currentVideoId);
  } catch (err) {
    console.error("Video Understanding: Failed to read video ID from chrome.storage.local", err);
    displayEl.textContent = "Error reading storage";
  }
}

// Listen for storage changes in real time (e.g. user navigates to another video)
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.currentVideoId) {
    updateDisplay(changes.currentVideoId.newValue);
  }
});

// Run initial load
init();
