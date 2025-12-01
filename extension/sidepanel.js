/*
  SIDEPANEL.JS
  ============
  Main logic for the FilmBuddy sidebar.

  Responsibilities:
  1. Send questions to the backend API
  2. Display responses in the chat
  3. Get current timestamp from content script
  4. Manage UI state (loading, errors, etc.)

  Communication flow:
  - Sidebar ←→ Background (chrome.runtime messages)
  - Background ←→ Content Script (chrome.tabs messages)
  - Sidebar → Backend (fetch API)
*/

// ========== CONFIGURATION ==========

const API_BASE_URL = 'http://localhost:8000';
const DEFAULT_FILM_ID = 'la_la_land';

// ========== DOM ELEMENTS ==========

const elements = {
  filmSelect: document.getElementById('film-select'),
  currentTime: document.getElementById('current-time'),
  spoilerMode: document.getElementById('spoiler-mode'),
  connectionStatus: document.getElementById('connection-status'),
  chatContainer: document.getElementById('chat-container'),
  questionInput: document.getElementById('question-input'),
  sendButton: document.getElementById('send-button'),
};

// ========== STATE ==========

let state = {
  currentTimestamp: 0,        // Current video position in seconds
  isLoading: false,           // Whether we're waiting for a response
  isConnected: false,         // Backend connection status
  timestampInterval: null,    // Interval for updating timestamp
};

// ========== INITIALIZATION ==========

document.addEventListener('DOMContentLoaded', () => {
  initializeExtension();
  setupEventListeners();
  startTimestampPolling();
  checkBackendConnection();
});

function initializeExtension() {
  // Load saved preferences from storage
  chrome.storage.local.get(['filmId', 'spoilerMode'], (result) => {
    if (result.filmId) {
      elements.filmSelect.value = result.filmId;
    }
    if (result.spoilerMode !== undefined) {
      elements.spoilerMode.checked = result.spoilerMode;
    }
  });
}

function setupEventListeners() {
  // Send button click
  elements.sendButton.addEventListener('click', handleSendMessage);

  // Enter key to send (Shift+Enter for new line)
  elements.questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Auto-resize textarea
  elements.questionInput.addEventListener('input', () => {
    elements.questionInput.style.height = 'auto';
    elements.questionInput.style.height = Math.min(elements.questionInput.scrollHeight, 120) + 'px';
  });

  // Save preferences on change
  elements.filmSelect.addEventListener('change', () => {
    chrome.storage.local.set({ filmId: elements.filmSelect.value });
  });

  elements.spoilerMode.addEventListener('change', () => {
    chrome.storage.local.set({ spoilerMode: elements.spoilerMode.checked });
  });
}

// ========== TIMESTAMP MANAGEMENT ==========

function startTimestampPolling() {
  // Poll for timestamp updates every second
  state.timestampInterval = setInterval(updateTimestamp, 1000);
  updateTimestamp(); // Initial update
}

async function updateTimestamp() {
  try {
    // Request timestamp from content script via background
    const response = await chrome.runtime.sendMessage({ action: 'getTimestamp' });

    if (response && response.found && response.timestamp !== undefined) {
      state.currentTimestamp = response.timestamp;
      elements.currentTime.textContent = formatTime(response.timestamp);
      elements.currentTime.style.color = ''; // Reset color on success
    } else if (response && !response.found) {
      // Video element not found on page
      elements.currentTime.textContent = 'No video';
      elements.currentTime.style.color = '#ff9800'; // Orange warning
      console.warn('[FilmBuddy] Video not detected on current page');
    }
  } catch (error) {
    // Content script might not be available (not on a video page)
    elements.currentTime.textContent = 'Not ready';
    elements.currentTime.style.color = '#999';
    console.log('[FilmBuddy] Content script not available:', error.message);
  }
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// ========== BACKEND COMMUNICATION ==========

async function checkBackendConnection() {
  try {
    const response = await fetch(`${API_BASE_URL}/ping`);
    const data = await response.json();

    if (data.ok) {
      setConnectionStatus('connected', 'Connected');
      state.isConnected = true;
    } else {
      throw new Error('Backend not ready');
    }
  } catch (error) {
    setConnectionStatus('error', 'Backend offline');
    state.isConnected = false;
  }
}

function setConnectionStatus(status, text) {
  elements.connectionStatus.className = `status ${status}`;
  elements.connectionStatus.querySelector('.status-text').textContent = text;
}

async function sendQuestion(question) {
  const filmId = elements.filmSelect.value;
  const spoilerMode = elements.spoilerMode.checked ? 'on' : 'off';

  const requestBody = {
    film_id: filmId,
    t_now: state.currentTimestamp,
    query: question,
    spoiler_mode: spoilerMode,
    top_k: 6
  };

  const response = await fetch(`${API_BASE_URL}/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    throw new Error(`Server error: ${response.status}`);
  }

  return await response.json();
}

// ========== MESSAGE HANDLING ==========

async function handleSendMessage() {
  const question = elements.questionInput.value.trim();

  if (!question || state.isLoading) {
    return;
  }

  if (!state.isConnected) {
    addMessage('error', 'Cannot connect to FilmBuddy server. Make sure it\'s running on localhost:8000');
    return;
  }

  // Clear input and add user message
  elements.questionInput.value = '';
  elements.questionInput.style.height = 'auto';
  addMessage('user', question);

  // Show loading indicator
  state.isLoading = true;
  elements.sendButton.disabled = true;
  const loadingMessage = addLoadingMessage();

  try {
    const response = await sendQuestion(question);

    // Remove loading indicator
    loadingMessage.remove();

    // Add assistant response
    if (response.answer) {
      addMessage('assistant', response.answer, {
        timestamp: state.currentTimestamp,
        hits: response.hits,
        llmEnabled: response.llm_enabled
      });
    } else {
      // Fallback if no LLM response (show raw hits)
      const hitsText = response.hits.map(h =>
        `[${formatTime(h.t_start)}] ${h.text.substring(0, 100)}...`
      ).join('\n\n');
      addMessage('assistant', hitsText || 'No relevant content found for your question.');
    }

  } catch (error) {
    loadingMessage.remove();
    addMessage('error', `Error: ${error.message}`);
  } finally {
    state.isLoading = false;
    elements.sendButton.disabled = false;
    elements.questionInput.focus();
  }
}

// ========== UI HELPERS ==========

function addMessage(type, content, meta = {}) {
  // Remove welcome message on first real message
  const welcome = elements.chatContainer.querySelector('.welcome-message');
  if (welcome && type !== 'error') {
    welcome.remove();
  }

  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}`;

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';
  contentDiv.textContent = content;
  messageDiv.appendChild(contentDiv);

  // Add metadata for assistant messages
  if (type === 'assistant' && meta.timestamp !== undefined) {
    const metaDiv = document.createElement('div');
    metaDiv.className = 'message-meta';
    metaDiv.textContent = `At ${formatTime(meta.timestamp)}`;

    // Add sources toggle if hits are available
    if (meta.hits && meta.hits.length > 0) {
      const sourcesBtn = document.createElement('button');
      sourcesBtn.className = 'sources-toggle';
      sourcesBtn.textContent = `View sources (${meta.hits.length})`;

      const sourcesList = document.createElement('div');
      sourcesList.className = 'sources-list';
      sourcesList.innerHTML = meta.hits.map(hit =>
        `<div class="source-item">
          <span class="source-time">[${formatTime(hit.t_start)}]</span>
          ${hit.text.substring(0, 80)}${hit.text.length > 80 ? '...' : ''}
        </div>`
      ).join('');

      sourcesBtn.addEventListener('click', () => {
        sourcesList.classList.toggle('expanded');
        sourcesBtn.textContent = sourcesList.classList.contains('expanded')
          ? 'Hide sources'
          : `View sources (${meta.hits.length})`;
      });

      metaDiv.appendChild(document.createElement('br'));
      metaDiv.appendChild(sourcesBtn);
      messageDiv.appendChild(metaDiv);
      messageDiv.appendChild(sourcesList);
    } else {
      messageDiv.appendChild(metaDiv);
    }
  }

  elements.chatContainer.appendChild(messageDiv);
  scrollToBottom();

  return messageDiv;
}

function addLoadingMessage() {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message loading';
  messageDiv.innerHTML = `
    <div class="loading-dots">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
  elements.chatContainer.appendChild(messageDiv);
  scrollToBottom();
  return messageDiv;
}

function scrollToBottom() {
  elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

// ========== CLEANUP ==========

window.addEventListener('beforeunload', () => {
  if (state.timestampInterval) {
    clearInterval(state.timestampInterval);
  }
});
