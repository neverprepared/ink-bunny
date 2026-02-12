#!/bin/bash
# Discover and optionally auto-start the container-lifecycle API.
#
# Resolution order: env var > config file > defaults
#
# Outputs JSON to stdout:
#   {"url": "...", "status": "connected"}   — API already running
#   {"url": "...", "status": "started"}     — auto-started successfully
#   {"status": "unavailable"}               — not reachable and not auto-started
#
# Writes active URL to ${CLAUDE_CONFIG_DIR}/reflex/.container-lifecycle-url

set -euo pipefail

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}"
CONFIG_DIR="${CLAUDE_DIR}/reflex"
CONFIG_FILE="${CONFIG_DIR}/container-lifecycle.json"
URL_FILE="${CONFIG_DIR}/.container-lifecycle-url"
PID_FILE="${CONFIG_DIR}/.container-lifecycle-pid"

# -----------------------------------------------------------------------------
# Read configuration
# -----------------------------------------------------------------------------

DEFAULT_URL="http://127.0.0.1:8000"
DEFAULT_AUTOSTART="true"

# Start with defaults
URL="$DEFAULT_URL"
AUTOSTART="$DEFAULT_AUTOSTART"

# Layer config file values (if present)
if [[ -f "$CONFIG_FILE" ]]; then
  CFG_URL=$(jq -r '.url // empty' "$CONFIG_FILE" 2>/dev/null || true)
  CFG_AUTOSTART=$(jq -r '.autostart // empty' "$CONFIG_FILE" 2>/dev/null || true)
  [[ -n "$CFG_URL" ]] && URL="$CFG_URL"
  [[ -n "$CFG_AUTOSTART" ]] && AUTOSTART="$CFG_AUTOSTART"
fi

# Layer env var overrides (highest priority)
[[ -n "${CONTAINER_LIFECYCLE_URL:-}" ]] && URL="$CONTAINER_LIFECYCLE_URL"
[[ -n "${CONTAINER_LIFECYCLE_AUTOSTART:-}" ]] && AUTOSTART="$CONTAINER_LIFECYCLE_AUTOSTART"

# Extract port from URL for auto-start
PORT=$(echo "$URL" | sed -n 's|.*:\([0-9]*\)$|\1|p')
PORT="${PORT:-8000}"

# Extract host from URL for auto-start
HOST=$(echo "$URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
HOST="${HOST:-127.0.0.1}"

# -----------------------------------------------------------------------------
# Health check
# -----------------------------------------------------------------------------

health_check() {
  curl -sf "${URL}/api/sessions" --max-time 2 >/dev/null 2>&1
}

# -----------------------------------------------------------------------------
# Already running?
# -----------------------------------------------------------------------------

if health_check; then
  mkdir -p "$CONFIG_DIR"
  echo "$URL" > "$URL_FILE"
  echo "{\"url\": \"${URL}\", \"status\": \"connected\"}"
  exit 0
fi

# -----------------------------------------------------------------------------
# Auto-start if enabled
# -----------------------------------------------------------------------------

if [[ "$AUTOSTART" != "true" ]]; then
  rm -f "$URL_FILE"
  echo '{"status": "unavailable", "reason": "autostart disabled"}'
  exit 0
fi

if ! command -v container-lifecycle >/dev/null 2>&1; then
  rm -f "$URL_FILE"
  echo '{"status": "unavailable", "reason": "container-lifecycle not on PATH"}'
  exit 0
fi

# Only auto-start for local URLs
if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" ]]; then
  rm -f "$URL_FILE"
  echo '{"status": "unavailable", "reason": "remote URL not reachable"}'
  exit 0
fi

mkdir -p "$CONFIG_DIR"
container-lifecycle api --host "$HOST" --port "$PORT" >/dev/null 2>&1 &
API_PID=$!
echo "$API_PID" > "$PID_FILE"

# Wait up to 10s for health check
for i in $(seq 1 20); do
  if health_check; then
    echo "$URL" > "$URL_FILE"
    echo "{\"url\": \"${URL}\", \"status\": \"started\", \"pid\": ${API_PID}}"
    exit 0
  fi
  sleep 0.5
done

# Failed to start — clean up
kill "$API_PID" 2>/dev/null || true
rm -f "$PID_FILE" "$URL_FILE"
echo '{"status": "unavailable", "reason": "API failed to start within 10s"}'
exit 0
