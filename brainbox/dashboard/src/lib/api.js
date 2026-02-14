/** API client for brainbox backend. */

export async function fetchSessions() {
  const res = await fetch('/api/sessions');
  return res.json();
}

export async function stopSession(name) {
  const res = await fetch('/api/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return res.json();
}

export async function deleteSession(name) {
  const res = await fetch('/api/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return res.json();
}

export async function startSession(name) {
  const res = await fetch('/api/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return res.json();
}

export async function createSession({ name, role, volume, query, openTab, llm_provider, llm_model, ollama_host }) {
  const res = await fetch('/api/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, role, volume, query, openTab, llm_provider, llm_model, ollama_host }),
  });
  return res.json();
}

export async function fetchContainerMetrics() {
  const res = await fetch('/api/metrics/containers');
  return res.json();
}

export async function fetchHubState() {
  const res = await fetch('/api/hub/state');
  return res.json();
}

/**
 * Connect to the SSE event stream.
 * Returns the EventSource instance (caller can close it).
 * Calls `onEvent(data)` for each message.
 */
export function connectSSE(onEvent) {
  const es = new EventSource('/api/events');
  es.onmessage = (e) => onEvent(e.data);
  return es;
}
