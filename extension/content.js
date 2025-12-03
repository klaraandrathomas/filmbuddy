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
  const AUTO_HIDE_DELAY = 30000; // 30 seconds before auto-hiding

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
    inputFocused: false  // Track input focus state
  };

  // ========== STYLES ==========
  const styles = `
    #filmbuddy-overlay {
      position: fixed;
      top: 0;
      right: 0;
      width: ${PANEL_WIDTH}px;
      height: 100vh;
      z-index: 2147483647;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      transform: translateX(100%);
      transition: transform 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      pointer-events: none;
    }

    #filmbuddy-overlay.visible {
      transform: translateX(0);
      pointer-events: auto;
    }

    #filmbuddy-overlay * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    .fb-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: rgba(0, 0, 0, 0.4);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-left: 1px solid rgba(255, 255, 255, 0.15);
      color: #e0e0e0;
    }

    .fb-header {
      padding: 20px 20px 16px;
      background: rgba(0, 0, 0, 0.25);
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      flex-shrink: 0;
    }

    .fb-header-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 18px;
    }

    .fb-title {
      font-size: 20px;
      font-weight: 600;
      color: #fff;
      letter-spacing: -0.3px;
    }

    .fb-pin-btn {
      background: rgba(255, 255, 255, 0.1);
      border: none;
      color: rgba(255, 255, 255, 0.6);
      width: 32px;
      height: 32px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }

    .fb-pin-btn:hover {
      background: rgba(255, 255, 255, 0.15);
      color: #fff;
    }

    .fb-pin-btn.pinned {
      background: rgba(255, 255, 255, 0.2);
      color: #fff;
    }

    .fb-controls {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .fb-select {
      flex: 1;
      padding: 10px 14px;
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 8px;
      font-size: 14px;
      cursor: pointer;
      min-width: 0;
    }

    .fb-select:hover {
      background: rgba(255, 255, 255, 0.15);
    }

    .fb-select:focus {
      outline: none;
      border-color: rgba(255, 255, 255, 0.3);
    }

    .fb-timestamp {
      font-family: 'SF Mono', Monaco, monospace;
      font-size: 14px;
      font-weight: 500;
      color: #fff;
      background: rgba(255, 255, 255, 0.1);
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      flex-shrink: 0;
    }

    .fb-spoiler {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 13px;
      color: rgba(255, 255, 255, 0.7);
      flex-shrink: 0;
    }

    .fb-spoiler input {
      width: 36px;
      height: 20px;
      appearance: none;
      -webkit-appearance: none;
      background: rgba(255, 255, 255, 0.15);
      border-radius: 10px;
      position: relative;
      cursor: pointer;
      transition: background 0.2s;
    }

    .fb-spoiler input::after {
      content: '';
      position: absolute;
      top: 3px;
      left: 3px;
      width: 14px;
      height: 14px;
      background: #fff;
      border-radius: 50%;
      transition: transform 0.2s;
    }

    .fb-spoiler input:checked {
      background: rgba(245, 158, 11, 0.8);
    }

    .fb-spoiler input:checked::after {
      transform: translateX(16px);
    }

    .fb-chat {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .fb-chat::-webkit-scrollbar {
      width: 6px;
    }

    .fb-chat::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.2);
      border-radius: 3px;
    }

    .fb-welcome {
      background: rgba(255, 255, 255, 0.08);
      padding: 18px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      font-size: 15px;
      line-height: 1.6;
    }

    .fb-welcome-sub {
      color: rgba(255, 255, 255, 0.5);
      font-size: 13px;
      margin-top: 10px;
    }

    .fb-message {
      max-width: 90%;
      padding: 14px 18px;
      border-radius: 12px;
      font-size: 15px;
      line-height: 1.6;
      animation: fb-msg-in 0.25s ease-out;
      word-wrap: break-word;
    }

    @keyframes fb-msg-in {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .fb-message.user {
      align-self: flex-end;
      background: rgba(255, 255, 255, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #fff;
      border-bottom-right-radius: 4px;
    }

    .fb-message.assistant {
      align-self: flex-start;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-bottom-left-radius: 4px;
    }

    .fb-message.error {
      background: rgba(239, 68, 68, 0.2);
      border: 1px solid rgba(239, 68, 68, 0.35);
      color: #fca5a5;
    }

    .fb-loading {
      display: flex;
      gap: 6px;
      padding: 14px 18px;
      align-self: flex-start;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
    }

    .fb-loading span {
      width: 8px;
      height: 8px;
      background: rgba(255, 255, 255, 0.5);
      border-radius: 50%;
      animation: fb-bounce 1.4s infinite ease-in-out;
    }

    .fb-loading span:nth-child(1) { animation-delay: -0.32s; }
    .fb-loading span:nth-child(2) { animation-delay: -0.16s; }

    @keyframes fb-bounce {
      0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
      40% { transform: scale(1); opacity: 1; }
    }

    .fb-input-area {
      padding: 16px 20px;
      background: rgba(0, 0, 0, 0.25);
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      flex-shrink: 0;
    }

    .fb-input-wrapper {
      display: flex;
      gap: 12px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 12px 12px 12px 18px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      transition: border-color 0.2s, background 0.2s;
    }

    .fb-input-wrapper:hover {
      background: rgba(255, 255, 255, 0.12);
    }

    .fb-input-wrapper:focus-within {
      border-color: rgba(255, 255, 255, 0.3);
      background: rgba(255, 255, 255, 0.12);
    }

    .fb-input {
      flex: 1;
      background: none;
      border: none;
      color: #fff;
      font-size: 15px;
      font-family: inherit;
      resize: none;
      max-height: 100px;
      line-height: 1.5;
    }

    .fb-input::placeholder {
      color: rgba(255, 255, 255, 0.4);
    }

    .fb-input:focus {
      outline: none;
    }

    .fb-send-btn {
      width: 40px;
      height: 40px;
      background: rgba(255, 255, 255, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 10px;
      color: #fff;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: all 0.2s;
    }

    .fb-send-btn:hover {
      background: rgba(255, 255, 255, 0.25);
    }

    .fb-send-btn:disabled {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(255, 255, 255, 0.1);
      color: rgba(255, 255, 255, 0.3);
      cursor: not-allowed;
    }

    /* Hover trigger zone */
    #filmbuddy-trigger {
      position: fixed;
      top: 0;
      right: 0;
      width: ${SHOW_THRESHOLD}px;
      height: 100vh;
      z-index: 2147483646;
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
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 2v4m0 12v4m-10-10h4m12 0h4"/>
              </svg>
            </button>
          </div>
          <div class="fb-controls">
            <select class="fb-select" id="fb-film-select">
              <option value="">Loading...</option>
            </select>
            <span class="fb-timestamp" id="fb-timestamp">0:00</span>
            <label class="fb-spoiler">
              <input type="checkbox" id="fb-spoiler-toggle">
              <span>Spoilers</span>
            </label>
          </div>
        </div>
        <div class="fb-chat" id="fb-chat">
          <div class="fb-welcome">
            Ask me anything about what you're watching!
            <div class="fb-welcome-sub">I won't spoil what's ahead.</div>
          </div>
        </div>
        <div class="fb-input-area">
          <div class="fb-input-wrapper">
            <textarea class="fb-input" id="fb-input" placeholder="Ask about the movie..." rows="1"></textarea>
            <button class="fb-send-btn" id="fb-send">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
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

    // Start hide timer when mouse leaves overlay (unless pinned)
    overlay.addEventListener('mouseleave', (e) => {
      if (!state.isPinned && e.clientX < window.innerWidth - PANEL_WIDTH) {
        scheduleHide();
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

    // Check for URL changes every 2 seconds (only re-detect on navigation)
    state.lastUrl = window.location.href;
    setInterval(checkForNavigation, 2000);
  }

  function checkForNavigation() {
    const currentUrl = window.location.href;
    if (currentUrl !== state.lastUrl) {
      console.log('[FilmBuddy] URL changed, re-detecting movie');
      state.lastUrl = currentUrl;
      state.detectedTitle = null; // Reset so detection runs fresh
      detectAndMatchMovie();
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

  async function detectAndMatchMovie() {
    // Skip if already detected for this URL
    if (state.detectedTitle) return;

    const title = detectMovieTitle();
    if (!title) {
      console.log('[FilmBuddy] No title found on page');
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
        console.log('[FilmBuddy] Matched to:', data.matched_film_id);
      } else {
        state.isUnknownMovie = true;
        if (select) select.value = '__unknown__';
        console.log('[FilmBuddy] No match found, using general chat');
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
    msg.textContent = content;
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
