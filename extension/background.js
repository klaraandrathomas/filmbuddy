/*
  BACKGROUND.JS
  =============
  Service worker that runs in the background.

  Responsibilities:
  1. Route messages between sidebar and content scripts
  2. Handle extension icon clicks (open side panel)
  3. Track which tabs have video players
  4. Manage extension lifecycle events

  This is the central hub for all extension communication.
*/

// ========== STATE ==========

// Track tabs with active video players
const videoTabs = new Map();

// ========== SIDE PANEL MANAGEMENT ==========

/**
 * Open the side panel when the extension icon is clicked.
 */
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

/**
 * Set side panel behavior - open on action click.
 */
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error('[FilmBuddy] Side panel error:', error));

// ========== MESSAGE ROUTING ==========

/**
 * Handle messages from sidebar and content scripts.
 * Routes messages to the appropriate destination.
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

  // ----- Messages FROM sidebar -----

  if (request.action === 'getTimestamp') {
    // Forward timestamp request to the active tab's content script
    forwardToActiveTab(request)
      .then(sendResponse)
      .catch(() => {
        // No video tab found, return default
        sendResponse({ timestamp: 0, found: false });
      });

    // Return true to indicate async response
    return true;
  }

  // ----- Messages FROM content script -----

  if (request.action === 'contentScriptReady') {
    // Content script loaded on a page
    if (sender.tab) {
      videoTabs.set(sender.tab.id, {
        url: request.url,
        hasVideo: request.hasVideo,
        timestamp: Date.now()
      });
      console.log('[FilmBuddy] Content script ready on tab:', sender.tab.id, request.url);
    }
    sendResponse({ acknowledged: true });
    return false;
  }

  if (request.action === 'videoEvent') {
    // Video event occurred (play, pause, seek, etc.)
    // You can broadcast this to the sidebar if needed
    console.log('[FilmBuddy] Video event:', request.event, 'at', request.timestamp);
    return false;
  }

  // Unknown message
  return false;
});

/**
 * Forward a message to the content script in the active tab.
 */
async function forwardToActiveTab(message) {
  try {
    // Get the currently active tab
    const [activeTab] = await chrome.tabs.query({
      active: true,
      currentWindow: true
    });

    if (!activeTab) {
      throw new Error('No active tab');
    }

    // Send message to content script
    const response = await chrome.tabs.sendMessage(activeTab.id, message);
    return response;

  } catch (error) {
    // Content script might not be loaded on this tab
    console.log('[FilmBuddy] Could not reach content script:', error.message);
    throw error;
  }
}

// ========== TAB MANAGEMENT ==========

/**
 * Clean up when a tab is closed.
 */
chrome.tabs.onRemoved.addListener((tabId) => {
  videoTabs.delete(tabId);
});

/**
 * Clean up when a tab navigates away.
 */
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'loading') {
    // Tab is navigating, remove from video tabs
    // Content script will re-register if it loads
    videoTabs.delete(tabId);
  }
});

// ========== INSTALLATION ==========

/**
 * Handle extension installation/update.
 */
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[FilmBuddy] Extension installed');

    // Set default storage values
    chrome.storage.local.set({
      filmId: 'la_la_land',
      spoilerMode: false
    });
  }

  if (details.reason === 'update') {
    console.log('[FilmBuddy] Extension updated to version', chrome.runtime.getManifest().version);
  }
});

// ========== STARTUP ==========

console.log('[FilmBuddy] Background service worker started');
