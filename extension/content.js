/**
 * content.js - Content script for YouTube watch pages
 *
 * Responsibilities:
 * 1. Extracts the YouTube video ID ("v" parameter) from the current URL.
 * 2. Persists the current video ID in chrome.storage.local for extension side panel access.
 * 3. Observes SPA (Single Page Application) navigation on YouTube using:
 *    - MutationObserver on document title
 *    - YouTube custom navigation events ('yt-navigate-finish')
 *    - Periodic polling fallback on window.location.href
 */

let lastVideoId = null;

/**
 * Extracts the video ID from the "v" query parameter of the provided URL.
 * @param {string} url - The URL string to parse (defaults to current window location)
 * @returns {string|null} - The video ID string or null if not found
 */
function extractVideoId(url = window.location.href) {
  try {
    const urlObj = new URL(url);
    return urlObj.searchParams.get("v");
  } catch (err) {
    return null;
  }
}

/**
 * Checks if the video ID has changed, logs to console, and saves to storage.
 */
async function checkAndProcessVideoId() {
  const currentVideoId = extractVideoId();

  // If no video ID or it has not changed since the last check, skip
  if (!currentVideoId || currentVideoId === lastVideoId) {
    return;
  }

  lastVideoId = currentVideoId;
  console.log(`Video Understanding: detected video ID: ${currentVideoId}`);

  try {
    await chrome.storage.local.set({ currentVideoId });
  } catch (err) {
    console.error("Video Understanding: Failed to save video ID to chrome.storage.local", err);
  }
}

// 1. Initial check when script loads
checkAndProcessVideoId();

// 2. YouTube SPA navigation event listener
window.addEventListener("yt-navigate-finish", checkAndProcessVideoId);

// 3. Browser history navigation (back/forward)
window.addEventListener("popstate", checkAndProcessVideoId);

// 4. MutationObserver on <title> (YouTube updates document.title on video transitions)
const titleElement = document.querySelector("title");
if (titleElement) {
  const titleObserver = new MutationObserver(() => {
    checkAndProcessVideoId();
  });
  titleObserver.observe(titleElement, { childList: true, characterData: true, subtree: true });
}

// 5. Periodic polling fallback (1 second interval) to catch any edge cases where events do not fire
setInterval(checkAndProcessVideoId, 1000);
