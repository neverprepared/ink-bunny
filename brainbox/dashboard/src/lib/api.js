/** API client for brainbox backend. */

let _apiKey = null;

/**
 * Fetch the API key from the loopback-only auth endpoint.
 * Called once at startup before the app mounts.
 */
export async function initApiKey() {
  try {
    const res = await fetch('/api/auth/key');
    if (res.ok) {
      const data = await res.json();
      _apiKey = data.key;
    }
  } catch {
    // API key endpoint not available — mutating requests will fail with 401
  }
}

/**
 * Build headers for mutating (protected) requests.
 * Includes X-API-Key when available.
 */
function protectedHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (_apiKey) headers['X-API-Key'] = _apiKey;
  return headers;
}

/**
 * Helper to handle fetch responses with proper error handling.
 * @param {string} url - API endpoint URL
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<any>} Parsed JSON response
 * @throws {Error} If request fails or returns non-OK status
 */
async function fetchJSON(url, options = {}) {
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      const errorText = await res.text().catch(() => res.statusText);
      throw new Error(`HTTP ${res.status}: ${errorText}`);
    }
    return await res.json();
  } catch (err) {
    if (err instanceof Error && err.message.startsWith('HTTP')) {
      throw err; // Re-throw HTTP errors as-is
    }
    // Network error or other fetch failure
    throw new Error(`Network error: ${err.message || 'Unable to connect to server'}`);
  }
}

export async function fetchSessions(signal = null) {
  return fetchJSON('/api/sessions', signal ? { signal } : {});
}

export async function stopSession(name) {
  return fetchJSON('/api/stop', {
    method: 'POST',
    headers: protectedHeaders(),
    body: JSON.stringify({ name }),
  });
}

export async function deleteSession(name) {
  return fetchJSON('/api/delete', {
    method: 'POST',
    headers: protectedHeaders(),
    body: JSON.stringify({ name }),
  });
}

export async function startSession(name) {
  return fetchJSON('/api/start', {
    method: 'POST',
    headers: protectedHeaders(),
    body: JSON.stringify({ name }),
  });
}

export async function createSession({ name, role, volume, llm_provider, llm_model, ollama_host, backend, vm_template }) {
  return fetchJSON('/api/create', {
    method: 'POST',
    headers: protectedHeaders(),
    body: JSON.stringify({ name, role, volume, llm_provider, llm_model, ollama_host, backend, vm_template }),
  });
}

export async function fetchContainerMetrics(signal = null) {
  return fetchJSON('/api/metrics/containers', signal ? { signal } : {});
}

export async function fetchHubState() {
  return fetchJSON('/api/hub/state');
}

export async function fetchLangfuseHealth() {
  return fetchJSON('/api/langfuse/health');
}

export async function fetchQdrantHealth() {
  return fetchJSON('/api/qdrant/health');
}

export async function fetchSessionTraces(sessionName, limit = 50) {
  return fetchJSON(`/api/langfuse/sessions/${encodeURIComponent(sessionName)}/traces?limit=${limit}`);
}

export async function fetchSessionSummary(sessionName) {
  return fetchJSON(`/api/langfuse/sessions/${encodeURIComponent(sessionName)}/summary`);
}

export async function fetchTraceDetail(traceId) {
  return fetchJSON(`/api/langfuse/traces/${encodeURIComponent(traceId)}`);
}

/**
 * Connect to the SSE event stream with automatic reconnection.
 * Returns an object with a close() method.
 * Calls `onEvent(data)` for each message.
 * Calls `onError(error)` on errors (optional).
 * Calls `onReconnect(attemptNumber)` when reconnecting (optional).
 */
export function connectSSE(onEvent, onError = null, onReconnect = null) {
  let es = null;
  let reconnectTimeout = null;
  let reconnectAttempts = 0;
  const maxReconnectDelay = 30000; // 30s max delay
  let isClosed = false;

  function connect() {
    if (isClosed) return;

    es = new EventSource('/api/events');

    es.onmessage = (e) => {
      reconnectAttempts = 0; // Reset on successful message
      onEvent(e.data);
    };

    es.onerror = (err) => {
      if (onError) onError(err);

      // Don't reconnect if explicitly closed
      if (isClosed) return;

      es.close();

      // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay);
      reconnectAttempts++;

      console.log(`SSE connection lost. Reconnecting in ${delay}ms (attempt ${reconnectAttempts})...`);

      if (onReconnect) onReconnect(reconnectAttempts);

      reconnectTimeout = setTimeout(() => {
        connect();
      }, delay);
    };
  }

  connect();

  return {
    close: () => {
      isClosed = true;
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      if (es) {
        es.close();
        es = null;
      }
    }
  };
}
