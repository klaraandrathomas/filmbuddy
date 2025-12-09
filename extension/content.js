/*
  CONTENT.JS - FilmBuddy Overlay
  ==============================
  Injects a floating overlay panel directly onto streaming sites.
  Features: auto-hide/show, movie detection, chat with timestamp awareness.
*/

// Prevent duplicate injection
if (window.__filmbuddyInjected) {
  console.log('[FilmBuddy] Already injected, skipping');
} else {
  window.__filmbuddyInjected = true;

  // ========== CONFIGURATION ==========
  const API_BASE_URL = 'http://localhost:8000';
  const PANEL_WIDTH = 360;
  const SHOW_THRESHOLD = 60; // px from right edge to trigger show
  const AUTO_HIDE_DELAY = 5000; // 5 seconds before auto-hiding

  // ========== STATE ==========
  const state = {
    isVisible: false,
    isPinned: false,
    isLoading: false,
    currentTimestamp: 0,
    detectedTitle: null,
    matchedFilmId: null,
    isUnknownMovie: false,
    availableFilms: [],
    messages: [],
    hideTimeout: null,
    lastUrl: null,  // Track URL to detect navigation
    inputFocused: false,  // Track input focus state
    videoWasPlaying: false  // Track if video has started playing
  };

  // ========== STYLES ==========
  // Using high-specificity selectors and !important to override streaming site CSS
  const styles = `
    /* ===== RESET & BASE ===== */
    #filmbuddy-overlay,
    #filmbuddy-overlay *,
    #filmbuddy-overlay *::before,
    #filmbuddy-overlay *::after {
      box-sizing: border-box !important;
      margin: 0 !important;
      padding: 0 !important;
      border: none !important;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      line-height: 1.5 !important;
      -webkit-font-smoothing: antialiased !important;
    }

    #filmbuddy-overlay {
      position: fixed !important;
      top: 0 !important;
      right: 0 !important;
      width: ${PANEL_WIDTH}px !important;
      height: 100vh !important;
      z-index: 2147483647 !important;
      font-size: 14px !important;
      transform: translateX(100%) !important;
      transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
      pointer-events: none !important;
    }

    #filmbuddy-overlay.visible {
      transform: translateX(0) !important;
      pointer-events: auto !important;
    }

    /* ===== CONTAINER ===== */
    #filmbuddy-overlay .fb-container {
      display: flex !important;
      flex-direction: column !important;
      height: calc(100vh - 48px) !important;
      margin: 24px 14px !important;
      background: rgba(12, 15, 20, 0.85) !important;
      backdrop-filter: blur(12px) !important;
      -webkit-backdrop-filter: blur(12px) !important;
      border-radius: 16px !important;
      border: 1px solid rgba(255, 255, 255, 0.1) !important;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5) !important;
      color: rgba(255, 255, 255, 0.9) !important;
      overflow: hidden !important;
    }

    /* ===== HEADER ===== */
    #filmbuddy-overlay .fb-header {
      padding: 20px 20px 16px 20px !important;
      flex-shrink: 0 !important;
      background: transparent !important;
    }

    #filmbuddy-overlay .fb-header-top {
      display: flex !important;
      align-items: center !important;
      justify-content: space-between !important;
      margin-bottom: 16px !important;
    }

    #filmbuddy-overlay .fb-title {
      font-size: 18px !important;
      font-weight: 600 !important;
      color: #ffffff !important;
      letter-spacing: -0.3px !important;
    }

    #filmbuddy-overlay .fb-pin-btn {
      background: transparent !important;
      border: none !important;
      color: rgba(255, 255, 255, 0.3) !important;
      width: 32px !important;
      height: 32px !important;
      min-width: 32px !important;
      min-height: 32px !important;
      border-radius: 8px !important;
      cursor: pointer !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      transition: all 0.15s ease !important;
    }

    #filmbuddy-overlay .fb-pin-btn:hover {
      background: rgba(255, 255, 255, 0.06) !important;
      color: rgba(255, 255, 255, 0.6) !important;
    }

    #filmbuddy-overlay .fb-pin-btn.pinned {
      color: #22d3ee !important;
    }

    /* Film selector */
    #filmbuddy-overlay .fb-select {
      width: 100% !important;
      padding: 12px 14px !important;
      background: rgba(255, 255, 255, 0.06) !important;
      color: rgba(255, 255, 255, 0.9) !important;
      border: 1px solid rgba(255, 255, 255, 0.1) !important;
      border-radius: 10px !important;
      font-size: 14px !important;
      font-weight: 500 !important;
      cursor: pointer !important;
      transition: all 0.15s ease !important;
      margin-bottom: 12px !important;
      appearance: none !important;
      -webkit-appearance: none !important;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.4)' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E") !important;
      background-repeat: no-repeat !important;
      background-position: right 14px center !important;
    }

    #filmbuddy-overlay .fb-select:hover {
      border-color: rgba(255, 255, 255, 0.18) !important;
      background-color: rgba(255, 255, 255, 0.1) !important;
    }

    #filmbuddy-overlay .fb-select:focus {
      outline: none !important;
      border-color: rgba(34, 211, 238, 0.5) !important;
      box-shadow: 0 0 0 2px rgba(34, 211, 238, 0.1) !important;
    }

    /* Meta row: timestamp + spoiler toggle */
    #filmbuddy-overlay .fb-meta-row {
      display: flex !important;
      align-items: center !important;
      justify-content: space-between !important;
    }

    #filmbuddy-overlay .fb-timestamp {
      font-family: 'SF Mono', Monaco, 'Courier New', monospace !important;
      font-size: 13px !important;
      font-weight: 500 !important;
      color: rgba(255, 255, 255, 0.4) !important;
      background: transparent !important;
    }

    #filmbuddy-overlay .fb-spoiler {
      display: flex !important;
      align-items: center !important;
      gap: 8px !important;
      cursor: pointer !important;
      font-size: 13px !important;
      color: rgba(255, 255, 255, 0.45) !important;
      transition: color 0.15s ease !important;
    }

    #filmbuddy-overlay .fb-spoiler:hover {
      color: rgba(255, 255, 255, 0.65) !important;
    }

    #filmbuddy-overlay .fb-spoiler span {
      font-size: 13px !important;
      color: inherit !important;
    }

    #filmbuddy-overlay .fb-spoiler input {
      width: 36px !important;
      height: 20px !important;
      min-width: 36px !important;
      min-height: 20px !important;
      appearance: none !important;
      -webkit-appearance: none !important;
      background: rgba(255, 255, 255, 0.12) !important;
      border-radius: 10px !important;
      position: relative !important;
      cursor: pointer !important;
      transition: background 0.2s ease !important;
      border: none !important;
    }

    #filmbuddy-overlay .fb-spoiler input::after {
      content: '' !important;
      position: absolute !important;
      top: 2px !important;
      left: 2px !important;
      width: 16px !important;
      height: 16px !important;
      background: rgba(255, 255, 255, 0.95) !important;
      border-radius: 50% !important;
      transition: transform 0.2s ease !important;
      box-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;
    }

    #filmbuddy-overlay .fb-spoiler input:checked {
      background: #f59e0b !important;
    }

    #filmbuddy-overlay .fb-spoiler input:checked::after {
      transform: translateX(16px) !important;
    }

    /* ===== DIVIDER ===== */
    #filmbuddy-overlay .fb-divider {
      height: 1px !important;
      min-height: 1px !important;
      background: rgba(255, 255, 255, 0.06) !important;
      margin: 0 20px !important;
      flex-shrink: 0 !important;
    }

    /* ===== CHAT AREA ===== */
    #filmbuddy-overlay .fb-chat {
      flex: 1 !important;
      min-height: 0 !important;
      overflow-y: auto !important;
      overflow-x: hidden !important;
      padding: 20px !important;
      display: flex !important;
      flex-direction: column !important;
      gap: 16px !important;
      background: transparent !important;
    }

    #filmbuddy-overlay .fb-chat::-webkit-scrollbar {
      width: 5px !important;
    }

    #filmbuddy-overlay .fb-chat::-webkit-scrollbar-track {
      background: transparent !important;
    }

    #filmbuddy-overlay .fb-chat::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.1) !important;
      border-radius: 3px !important;
    }

    #filmbuddy-overlay .fb-welcome {
      font-size: 14px !important;
      line-height: 1.6 !important;
      color: rgba(255, 255, 255, 0.7) !important;
      background: transparent !important;
    }

    #filmbuddy-overlay .fb-welcome-sub {
      color: rgba(255, 255, 255, 0.4) !important;
      font-size: 13px !important;
      margin-top: 8px !important;
      line-height: 1.5 !important;
    }

    #filmbuddy-overlay .fb-message {
      max-width: 88% !important;
      padding: 12px 16px !important;
      border-radius: 12px !important;
      font-size: 14px !important;
      line-height: 1.6 !important;
      animation: fb-msg-in 0.2s ease-out !important;
      word-wrap: break-word !important;
      overflow-wrap: anywhere !important;
      background: transparent !important;
    }

    @keyframes fb-msg-in {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    #filmbuddy-overlay .fb-message.user {
      align-self: flex-end !important;
      background: rgba(34, 211, 238, 0.12) !important;
      color: rgba(255, 255, 255, 0.95) !important;
      border-bottom-right-radius: 4px !important;
    }

    #filmbuddy-overlay .fb-message.assistant {
      align-self: flex-start !important;
      background: rgba(255, 255, 255, 0.05) !important;
      color: rgba(255, 255, 255, 0.9) !important;
      border-bottom-left-radius: 4px !important;
    }

    #filmbuddy-overlay .fb-message.assistant strong {
      font-weight: 700 !important;
      color: #22d3ee !important;
    }

    #filmbuddy-overlay .fb-message.error {
      background: rgba(239, 68, 68, 0.12) !important;
      color: #fca5a5 !important;
    }

    #filmbuddy-overlay .fb-loading {
      display: flex !important;
      gap: 5px !important;
      padding: 12px 16px !important;
      align-self: flex-start !important;
      background: rgba(255, 255, 255, 0.05) !important;
      border-radius: 12px !important;
    }

    #filmbuddy-overlay .fb-loading span {
      width: 6px !important;
      height: 6px !important;
      min-width: 6px !important;
      min-height: 6px !important;
      background: #22d3ee !important;
      border-radius: 50% !important;
      animation: fb-bounce 1.4s infinite ease-in-out !important;
    }

    #filmbuddy-overlay .fb-loading span:nth-child(1) { animation-delay: -0.32s !important; }
    #filmbuddy-overlay .fb-loading span:nth-child(2) { animation-delay: -0.16s !important; }

    @keyframes fb-bounce {
      0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
      40% { transform: scale(1); opacity: 1; }
    }

    /* ===== INPUT AREA ===== */
    #filmbuddy-overlay .fb-input-area {
      padding: 16px 20px 20px 20px !important;
      flex-shrink: 0 !important;
      background: transparent !important;
    }

    #filmbuddy-overlay .fb-input-wrapper {
      display: flex !important;
      align-items: flex-end !important;
      gap: 10px !important;
      background: rgba(255, 255, 255, 0.06) !important;
      border-radius: 12px !important;
      padding: 10px 10px 10px 14px !important;
      border: 1px solid rgba(255, 255, 255, 0.1) !important;
      transition: all 0.15s ease !important;
    }

    #filmbuddy-overlay .fb-input-wrapper:focus-within {
      border-color: rgba(34, 211, 238, 0.4) !important;
      background: rgba(255, 255, 255, 0.08) !important;
      box-shadow: 0 0 0 2px rgba(34, 211, 238, 0.08) !important;
    }

    #filmbuddy-overlay .fb-input {
      flex: 1 !important;
      background: transparent !important;
      border: none !important;
      color: rgba(255, 255, 255, 0.95) !important;
      font-size: 14px !important;
      font-family: inherit !important;
      resize: none !important;
      max-height: 100px !important;
      min-height: 20px !important;
      line-height: 1.5 !important;
      outline: none !important;
    }

    #filmbuddy-overlay .fb-input::placeholder {
      color: rgba(255, 255, 255, 0.3) !important;
    }

    #filmbuddy-overlay .fb-send-btn {
      width: 36px !important;
      height: 36px !important;
      min-width: 36px !important;
      min-height: 36px !important;
      background: #22d3ee !important;
      border: none !important;
      border-radius: 10px !important;
      color: #0f1318 !important;
      cursor: pointer !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      flex-shrink: 0 !important;
      transition: all 0.15s ease !important;
    }

    #filmbuddy-overlay .fb-send-btn:hover {
      background: #67e8f9 !important;
      transform: scale(1.04) !important;
    }

    #filmbuddy-overlay .fb-send-btn:active {
      transform: scale(0.98) !important;
    }

    #filmbuddy-overlay .fb-send-btn:disabled {
      background: rgba(255, 255, 255, 0.08) !important;
      color: rgba(255, 255, 255, 0.25) !important;
      cursor: not-allowed !important;
      transform: none !important;
    }

    #filmbuddy-overlay .fb-send-btn svg {
      width: 18px !important;
      height: 18px !important;
    }

    /* ===== TRIGGER ZONE ===== */
    #filmbuddy-trigger {
      position: fixed !important;
      top: 0 !important;
      right: 0 !important;
      width: ${SHOW_THRESHOLD}px !important;
      height: 100vh !important;
      z-index: 2147483646 !important;
      background: transparent !important;
    }
  `;

  // ========== CREATE OVERLAY ==========
  function createOverlay() {
    // Inject styles
    const styleEl = document.createElement('style');
    styleEl.id = 'filmbuddy-styles';
    styleEl.textContent = styles;
    document.head.appendChild(styleEl);

    // Create trigger zone
    const trigger = document.createElement('div');
    trigger.id = 'filmbuddy-trigger';
    document.body.appendChild(trigger);

    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'filmbuddy-overlay';
    overlay.innerHTML = `
      <div class="fb-container">
        <div class="fb-header">
          <div class="fb-header-top">
            <span class="fb-title">FilmBuddy</span>
            <button class="fb-pin-btn" id="fb-pin" title="Pin panel">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2v4m0 12v4m-10-10h4m12 0h4"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
          </div>
          <select class="fb-select" id="fb-film-select">
            <option value="">Loading...</option>
          </select>
          <div class="fb-meta-row">
            <span class="fb-timestamp" id="fb-timestamp">0:00</span>
            <label class="fb-spoiler">
              <input type="checkbox" id="fb-spoiler-toggle">
              <span>Spoilers</span>
            </label>
          </div>
        </div>
        <div class="fb-divider"></div>
        <div class="fb-chat" id="fb-chat">
          <div class="fb-welcome">
            Ask me anything about what you're watching.
            <div class="fb-welcome-sub">I'll keep answers spoiler-free based on your current timestamp.</div>
          </div>
        </div>
        <div class="fb-input-area">
          <div class="fb-input-wrapper">
            <textarea class="fb-input" id="fb-input" placeholder="Ask about the movie..." rows="1"></textarea>
            <button class="fb-send-btn" id="fb-send">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    // Setup event listeners
    setupEventListeners(trigger, overlay);

    // Initialize
    fetchAvailableFilms();
    startPolling();

    console.log('[FilmBuddy] Overlay created');
  }

  // ========== EVENT LISTENERS ==========
  function setupEventListeners(trigger, overlay) {
    const pinBtn = document.getElementById('fb-pin');
    const filmSelect = document.getElementById('fb-film-select');
    const spoilerToggle = document.getElementById('fb-spoiler-toggle');
    const input = document.getElementById('fb-input');
    const sendBtn = document.getElementById('fb-send');

    // Prevent all events from bubbling to Netflix/streaming site
    // This stops the player controls from appearing when interacting with overlay
    // Using bubble phase (no 'true') so events reach our child elements first
    overlay.addEventListener('click', (e) => e.stopPropagation());
    overlay.addEventListener('mousedown', (e) => e.stopPropagation());
    overlay.addEventListener('mouseup', (e) => e.stopPropagation());
    overlay.addEventListener('mousemove', (e) => e.stopPropagation());
    overlay.addEventListener('keydown', (e) => e.stopPropagation());
    overlay.addEventListener('keyup', (e) => e.stopPropagation());
    overlay.addEventListener('keypress', (e) => e.stopPropagation());

    // Show on hover trigger
    trigger.addEventListener('mouseenter', () => {
      showPanel();
    });

    // Keep panel open while mouse is over it
    overlay.addEventListener('mouseenter', () => {
      // Clear any pending hide timeout
      if (state.hideTimeout) {
        clearTimeout(state.hideTimeout);
        state.hideTimeout = null;
      }
    });

    // Hide immediately when mouse leaves overlay (unless pinned)
    overlay.addEventListener('mouseleave', (e) => {
      if (!state.isPinned && e.clientX < window.innerWidth - PANEL_WIDTH) {
        hidePanel();
      }
    });

    // Pin toggle
    pinBtn.addEventListener('click', () => {
      state.isPinned = !state.isPinned;
      pinBtn.classList.toggle('pinned', state.isPinned);
      pinBtn.title = state.isPinned ? 'Unpin panel' : 'Pin panel';
    });

    // Film select
    filmSelect.addEventListener('change', () => {
      const value = filmSelect.value;
      state.isUnknownMovie = value === '__unknown__';
      if (value && value !== '__unknown__') {
        state.matchedFilmId = value;
      }
    });

    // Input handling
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 100) + 'px';
    });

    // Prevent Netflix from stealing focus when clicking on input
    input.addEventListener('focus', () => {
      // Keep track that we have focus
      state.inputFocused = true;
    });

    input.addEventListener('blur', (e) => {
      // If blur wasn't caused by clicking elsewhere in our overlay, refocus
      // Small delay to check if focus went to another element in overlay
      state.inputFocused = false;
      setTimeout(() => {
        const activeEl = document.activeElement;
        const isInOverlay = overlay.contains(activeEl);
        // If focus left the overlay entirely and we were typing, refocus
        if (!isInOverlay && state.isVisible && input.value.length > 0) {
          input.focus();
        }
      }, 10);
    });

    sendBtn.addEventListener('click', sendMessage);
  }

  function showPanel() {
    // Clear any pending hide timeout
    if (state.hideTimeout) {
      clearTimeout(state.hideTimeout);
      state.hideTimeout = null;
    }

    const overlay = document.getElementById('filmbuddy-overlay');
    if (overlay && !state.isVisible) {
      overlay.classList.add('visible');
      state.isVisible = true;

      // Try to detect movie when panel opens (if not already matched)
      if (!state.matchedFilmId || state.isUnknownMovie) {
        state.detectedTitle = null; // Reset to retry
        detectAndMatchMovie();
      }
    }
  }

  function hidePanel() {
    const overlay = document.getElementById('filmbuddy-overlay');
    if (overlay && state.isVisible && !state.isPinned) {
      overlay.classList.remove('visible');
      state.isVisible = false;
    }
  }

  function scheduleHide() {
    // Clear any existing timeout
    if (state.hideTimeout) {
      clearTimeout(state.hideTimeout);
    }
    // Schedule hide after delay
    state.hideTimeout = setTimeout(() => {
      hidePanel();
      state.hideTimeout = null;
    }, AUTO_HIDE_DELAY);
  }

  // ========== VIDEO & MOVIE DETECTION ==========
  function findVideoElement() {
    const selectors = ['video', '.html5-video-player video', '#netflix-player video'];
    for (const sel of selectors) {
      const video = document.querySelector(sel);
      if (video && video.currentTime !== undefined) return video;
    }
    const videos = document.querySelectorAll('video');
    if (videos.length > 0) {
      return Array.from(videos).reduce((a, b) =>
        (a.clientWidth * a.clientHeight) > (b.clientWidth * b.clientHeight) ? a : b
      );
    }
    return null;
  }

  function detectMovieTitle() {
    const hostname = window.location.hostname;
    let title = null;

    if (hostname.includes('netflix')) {
      // Try multiple selectors for Netflix
      const videoTitleEl = document.querySelector('[data-uia="video-title"]');
      const playerTitleEl = document.querySelector('.video-title h4');
      const ellipsisEl = document.querySelector('.ellipsize-text');

      if (videoTitleEl) {
        title = videoTitleEl.textContent?.trim();
      } else if (playerTitleEl) {
        title = playerTitleEl.textContent?.trim();
      } else if (ellipsisEl) {
        title = ellipsisEl.textContent?.trim();
      } else {
        // Fallback to document title
        title = document.title.replace(/\s*[-|]\s*Netflix.*$/i, '').trim();
      }
    } else if (hostname.includes('youtube')) {
      const h1 = document.querySelector('h1.ytd-watch-metadata yt-formatted-string');
      title = h1?.textContent?.trim() || document.title.replace(/\s*[-–]\s*YouTube.*$/i, '').trim();
    } else if (hostname.includes('amazon')) {
      const titleEl = document.querySelector('.atvwebplayersdk-title-text');
      title = titleEl?.textContent?.trim() || document.title.replace(/\s*[-|].*Prime Video.*$/i, '').trim();
    } else if (hostname.includes('disneyplus')) {
      title = document.title.replace(/\s*[-|]\s*Disney\+.*$/i, '').trim();
    } else if (hostname.includes('hulu')) {
      title = document.title.replace(/\s*[-|].*Hulu.*$/i, '').trim();
    } else if (hostname.includes('max.com')) {
      title = document.title.replace(/\s*[-|]\s*Max.*$/i, '').trim();
    }

    if (title) {
      title = title.replace(/^Watch\s+/i, '').trim();
    }

    return title;
  }

  // ========== POLLING ==========
  function startPolling() {
    // Update timestamp every second
    setInterval(updateTimestamp, 1000);
    updateTimestamp();

    // Check for URL changes and video state every 2 seconds
    state.lastUrl = window.location.href;
    state.videoWasPlaying = false;
    setInterval(checkForChanges, 2000);
  }

  function checkForChanges() {
    const currentUrl = window.location.href;

    // Check for URL change
    if (currentUrl !== state.lastUrl) {
      console.log('[FilmBuddy] URL changed, re-detecting movie');
      state.lastUrl = currentUrl;
      state.detectedTitle = null;
      state.videoWasPlaying = false;
      detectAndMatchMovie();
      return;
    }

    // Check if video started playing (and we haven't detected yet)
    const video = findVideoElement();
    if (video && video.currentTime > 5 && !state.videoWasPlaying) {
      state.videoWasPlaying = true;
      if (!state.detectedTitle || state.isUnknownMovie) {
        console.log('[FilmBuddy] Video playing, attempting detection');
        state.detectedTitle = null; // Reset to retry
        detectAndMatchMovie();
      }
    }
  }

  function updateTimestamp() {
    const video = findVideoElement();
    const timestampEl = document.getElementById('fb-timestamp');
    if (!timestampEl) return;

    if (video) {
      state.currentTimestamp = video.currentTime;
      const mins = Math.floor(video.currentTime / 60);
      const secs = Math.floor(video.currentTime % 60);
      timestampEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
      timestampEl.style.opacity = '1';
    } else {
      timestampEl.textContent = 'No video';
      timestampEl.style.opacity = '0.5';
    }
  }

  async function fetchAvailableFilms() {
    try {
      const response = await fetch(`${API_BASE_URL}/films`);
      const data = await response.json();
      state.availableFilms = data.films || [];
      populateFilmSelect();
      // Run initial detection once after films are loaded
      detectAndMatchMovie();
    } catch (error) {
      console.error('[FilmBuddy] Failed to fetch films:', error);
      state.availableFilms = [];
      populateFilmSelect();
    }
  }

  function populateFilmSelect() {
    const select = document.getElementById('fb-film-select');
    if (!select) return;

    select.innerHTML = '';
    state.availableFilms.forEach(film => {
      const option = document.createElement('option');
      option.value = film.film_id;
      option.textContent = film.display_name;
      select.appendChild(option);
    });

    const unknownOption = document.createElement('option');
    unknownOption.value = '__unknown__';
    unknownOption.textContent = 'Other Movie';
    select.appendChild(unknownOption);

    if (state.matchedFilmId) {
      select.value = state.matchedFilmId;
    } else if (state.availableFilms.length > 0) {
      select.value = state.availableFilms[0].film_id;
      state.matchedFilmId = state.availableFilms[0].film_id;
    }
  }

  async function detectAndMatchMovie(retryCount = 0) {
    // Skip if already successfully matched to a known film
    if (state.detectedTitle && state.matchedFilmId && !state.isUnknownMovie) {
      return;
    }

    const title = detectMovieTitle();
    if (!title) {
      console.log('[FilmBuddy] No title found on page');
      // Retry up to 3 times with increasing delays
      if (retryCount < 3) {
        const delay = (retryCount + 1) * 2000; // 2s, 4s, 6s
        console.log(`[FilmBuddy] Retrying detection in ${delay/1000}s...`);
        setTimeout(() => detectAndMatchMovie(retryCount + 1), delay);
      }
      return;
    }

    state.detectedTitle = title;
    console.log('[FilmBuddy] Detected title:', title);

    try {
      const response = await fetch(`${API_BASE_URL}/match-title?title=${encodeURIComponent(title)}`);
      const data = await response.json();

      const select = document.getElementById('fb-film-select');
      if (data.matched_film_id) {
        state.matchedFilmId = data.matched_film_id;
        state.isUnknownMovie = false;
        if (select) select.value = data.matched_film_id;
        console.log('[FilmBuddy] Matched to:', data.matched_film_id, '(confidence:', data.confidence, ')');
      } else {
        state.isUnknownMovie = true;
        if (select) select.value = '__unknown__';
        console.log('[FilmBuddy] No match found for "' + title + '", using general chat');
      }
    } catch (error) {
      console.error('[FilmBuddy] Match failed:', error);
    }
  }

  // ========== CHAT ==========
  async function sendMessage() {
    const input = document.getElementById('fb-input');
    const query = input.value.trim();
    if (!query || state.isLoading) return;

    input.value = '';
    input.style.height = 'auto';

    addMessage('user', query);
    state.isLoading = true;
    showLoading();

    try {
      let response;
      if (state.isUnknownMovie) {
        response = await fetch(`${API_BASE_URL}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query,
            context: state.detectedTitle ? `Watching: ${state.detectedTitle}` : null
          })
        });
      } else {
        const filmId = document.getElementById('fb-film-select')?.value || state.matchedFilmId;
        const spoilerMode = document.getElementById('fb-spoiler-toggle')?.checked ? 'on' : 'off';

        response = await fetch(`${API_BASE_URL}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            film_id: filmId,
            t_now: state.currentTimestamp,
            query,
            spoiler_mode: spoilerMode,
            top_k: 6
          })
        });
      }

      const data = await response.json();
      hideLoading();
      addMessage('assistant', data.answer || 'No response available.');
    } catch (error) {
      hideLoading();
      addMessage('error', 'Failed to get response. Is the server running?');
    } finally {
      state.isLoading = false;
    }
  }

  function formatMessageContent(content) {
    // Convert markdown-style **bold** to HTML <strong> tags
    // Escape HTML first to prevent XSS
    const escaped = content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
    
    // Now convert **text** to <strong>text</strong>
    return escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  }

  function addMessage(type, content) {
    const chat = document.getElementById('fb-chat');
    if (!chat) return;

    // Remove welcome message on first real message
    const welcome = chat.querySelector('.fb-welcome');
    if (welcome && type !== 'error') {
      welcome.remove();
    }

    const msg = document.createElement('div');
    msg.className = `fb-message ${type}`;
    
    // For assistant messages, format bold text
    if (type === 'assistant') {
      msg.innerHTML = formatMessageContent(content);
    } else {
      msg.textContent = content;
    }
    
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
  }

  function showLoading() {
    const chat = document.getElementById('fb-chat');
    if (!chat) return;

    const loading = document.createElement('div');
    loading.className = 'fb-loading';
    loading.id = 'fb-loading';
    loading.innerHTML = '<span></span><span></span><span></span>';
    chat.appendChild(loading);
    chat.scrollTop = chat.scrollHeight;
  }

  function hideLoading() {
    const loading = document.getElementById('fb-loading');
    if (loading) loading.remove();
  }

  // ========== INIT ==========
  // Wait for page to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createOverlay);
  } else {
    createOverlay();
  }

  // Listen for messages from background
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'ping') {
      sendResponse({ loaded: true });
    }
    return true;
  });

  console.log('[FilmBuddy] Content script loaded on:', window.location.hostname);
}
