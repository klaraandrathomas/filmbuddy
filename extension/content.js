/*
  CONTENT.JS
  ==========
  Content script injected into streaming sites (Netflix, YouTube, etc.)

  Responsibilities:
  1. Find the video player element on the page
  2. Extract current playback timestamp
  3. Respond to timestamp requests from the sidebar

  This script runs in the context of the web page, so it has access
  to the video element's properties like currentTime.
*/

// ========== INJECTION GUARD ==========
// Prevent duplicate injection (e.g., from both manifest and programmatic injection)
if (!window.__filmbuddyInjected) {
  window.__filmbuddyInjected = true;

  // ========== VIDEO DETECTION ==========

  /**
   * Find the main video element on the page.
   * Different streaming sites have different DOM structures.
   */
  function findVideoElement() {
    // Try common video element selectors
    const selectors = [
      'video',                           // Generic
      'video.video-stream',              // YouTube
      'video[src]',                      // Videos with direct src
      '.watch-video video',              // Netflix
      '#netflix-player video',           // Netflix alternative
      '.html5-video-player video',       // YouTube alternative
    ];

    for (const selector of selectors) {
      const video = document.querySelector(selector);
      if (video && video.currentTime !== undefined) {
        return video;
      }
    }

    // Fallback: find any video element
    const videos = document.querySelectorAll('video');
    if (videos.length > 0) {
      // Return the largest video (likely the main player)
      let mainVideo = videos[0];
      let maxArea = 0;

      videos.forEach(video => {
        const area = video.clientWidth * video.clientHeight;
        if (area > maxArea) {
          maxArea = area;
          mainVideo = video;
        }
      });

      return mainVideo;
    }

    return null;
  }

  /**
   * Get the current timestamp from the video player.
   * Returns timestamp in seconds, or 0 if no video found.
   */
  function getCurrentTimestamp() {
    const video = findVideoElement();

    if (video) {
      const timestamp = video.currentTime || 0;
      const duration = video.duration || 0;
      const paused = video.paused;

      console.log('[FilmBuddy] Video detected:', {
        timestamp: timestamp.toFixed(2),
        duration: duration.toFixed(2),
        paused: paused,
        dimensions: `${video.clientWidth}x${video.clientHeight}`
      });

      return {
        timestamp: timestamp,
        duration: duration,
        paused: paused,
        found: true
      };
    }

    console.warn('[FilmBuddy] No video element found on page');
    return {
      timestamp: 0,
      duration: 0,
      paused: true,
      found: false
    };
  }

  // ========== MESSAGE HANDLING ==========

  /**
   * Listen for messages from the background script.
   * The sidebar sends requests through background → content script.
   */
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getTimestamp') {
      const timestampData = getCurrentTimestamp();
      sendResponse(timestampData);
    }

    if (request.action === 'ping') {
      // Health check to verify content script is loaded
      sendResponse({ loaded: true, url: window.location.href });
    }

    // Return true to indicate we will send a response asynchronously
    // (even though we send it synchronously, this prevents errors)
    return true;
  });

  // ========== INITIALIZATION ==========

  /**
   * Log when content script loads (helpful for debugging).
   */
  console.log('[FilmBuddy] Content script loaded on:', window.location.hostname);

  /**
   * Notify background script that we're ready.
   * This helps the extension know which tabs have video players.
   */
  chrome.runtime.sendMessage({
    action: 'contentScriptReady',
    url: window.location.href,
    hasVideo: findVideoElement() !== null
  });

} else {
  console.log('[FilmBuddy] Content script already injected, skipping duplicate');
}
