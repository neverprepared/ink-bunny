---
description: Manage the brainbox API and sandboxed dev environments
allowed-tools: Bash(curl:*), Bash(brainbox:*), Bash(open:*), Bash(kill:*), Bash(cat:*), Bash(mkdir:*), Bash(echo:*), Bash(jq:*)
argument-hint: <start|stop|status|create|query|dashboard|config|health>
---

# Brainbox

Manage the brainbox API that provides sandboxed Docker environments with web terminal access.

## Paths

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CONFIG_DIR="${CLAUDE_DIR}/reflex"
CONFIG_FILE="${CONFIG_DIR}/brainbox.json"
URL_FILE="${CONFIG_DIR}/.brainbox-url"
PID_FILE="${CONFIG_DIR}/.brainbox-pid"
CONNECT_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/brainbox-connect.sh"
```

## Subcommands

### `/reflex:container start`

Start the brainbox API locally (if not already running).

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
"${CLAUDE_PLUGIN_ROOT}/scripts/brainbox-connect.sh"
```

Show the result to the user. If status is "connected", say it was already running. If "started", confirm the API was started. If "unavailable", explain why (check the `reason` field).

### `/reflex:container stop`

Stop a locally auto-started brainbox API.

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
PID_FILE="${CLAUDE_DIR}/reflex/.brainbox-pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  kill "$PID" 2>/dev/null && echo "Brainbox API stopped (pid $PID)." || echo "Process $PID not running."
  rm -f "$PID_FILE" "${CLAUDE_DIR}/reflex/.brainbox-url"
else
  echo "No locally-started API to stop (no PID file found)."
  echo "If the API was started externally, stop it from its original process."
fi
```

### `/reflex:container status`

Show connection info, running containers, and dashboard URL.

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
URL_FILE="${CLAUDE_DIR}/reflex/.brainbox-url"
CONFIG_FILE="${CLAUDE_DIR}/reflex/brainbox.json"

echo "## Brainbox Status"
echo ""

# Connection
if [ -f "$URL_FILE" ]; then
  URL=$(cat "$URL_FILE")
  echo "**Connection:** Connected at ${URL}"

  # Container count
  SESSIONS=$(curl -sf "${URL}/api/sessions" --max-time 3 2>/dev/null || echo "[]")
  TOTAL=$(echo "$SESSIONS" | jq 'length' 2>/dev/null || echo "?")
  ACTIVE=$(echo "$SESSIONS" | jq '[.[] | select(.active == true)] | length' 2>/dev/null || echo "?")
  echo "**Containers:** ${ACTIVE} running / ${TOTAL} total"

  # Dashboard
  echo "**Dashboard:** ${URL}"
else
  echo "**Connection:** Not connected"
  echo ""
  echo "Start with: /reflex:container start"
fi

echo ""

# Config
echo "**Configuration:**"
if [ -f "$CONFIG_FILE" ]; then
  cat "$CONFIG_FILE" | jq .
else
  echo "  Using defaults (url: http://127.0.0.1:9999, autostart: true)"
fi

echo ""
echo "**Environment overrides:**"
echo "  BRAINBOX_URL=${BRAINBOX_URL:-<not set>}"
echo "  BRAINBOX_AUTOSTART=${BRAINBOX_AUTOSTART:-<not set>}"
```

### `/reflex:container dashboard`

Open the brainbox dashboard in the default browser.

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
URL_FILE="${CLAUDE_DIR}/reflex/.brainbox-url"

if [ -f "$URL_FILE" ]; then
  URL=$(cat "$URL_FILE")
  open "$URL" 2>/dev/null || echo "Dashboard URL: $URL"
  echo "Opened dashboard at $URL"
else
  echo "Brainbox is not connected. Start it first:"
  echo "  /reflex:container start"
fi
```

### `/reflex:container create`

Create a new sandboxed container. Auto-detects the caller's workspace profile and home from environment variables (`WORKSPACE_PROFILE`, `WORKSPACE_HOME`). An optional name can be provided as an argument; defaults to the profile name.

Supports additional volume mounts via `--mount` flags.

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
URL_FILE="${CLAUDE_DIR}/reflex/.brainbox-url"

if [ ! -f "$URL_FILE" ]; then
  echo "Brainbox is not connected. Start it first:"
  echo "  /reflex:container start"
  exit 1
fi

URL=$(cat "$URL_FILE")
PROFILE="${WORKSPACE_PROFILE:-}"
WS_HOME="${WORKSPACE_HOME:-}"

# Parse arguments: name (first non-flag) and --mount flags
# Extract name (first non-flag argument)
NAME=$(echo "$ARG" | sed -E 's/^([^ ]*).*/\1/' | grep -v '^--' || echo "")
if [ -z "$NAME" ] || echo "$NAME" | grep -q '^--'; then
  NAME="${PROFILE:-default}"
fi

# Extract all --mount arguments and build JSON array
VOLUMES=$(echo "$ARG" | grep -oE -- '--mount [^ ]+' | sed 's/--mount //' | jq -R . | jq -s -c . || echo "[]")
if [ "$VOLUMES" = "[]" ] || [ -z "$VOLUMES" ]; then
  VOLUMES=""
fi

# Build JSON payload
PAYLOAD="{\"name\":\"${NAME}\",\"role\":\"developer\""
if [ -n "$PROFILE" ]; then
  PAYLOAD="${PAYLOAD},\"workspace_profile\":\"${PROFILE}\""
fi
if [ -n "$WS_HOME" ]; then
  PAYLOAD="${PAYLOAD},\"workspace_home\":\"${WS_HOME}\""
fi
if [ -n "$VOLUMES" ] && [ "$VOLUMES" != "[]" ]; then
  PAYLOAD="${PAYLOAD},\"volumes\":${VOLUMES}"
fi
PAYLOAD="${PAYLOAD}}"

API_KEY=$(curl -sf "${URL}/api/auth/key" --max-time 3 2>/dev/null | jq -r '.key // empty' 2>/dev/null || true)

RESULT=$(curl -sf -X POST "${URL}/api/create" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${API_KEY}" \
  -d "$PAYLOAD" --max-time 60 2>&1)

echo "$RESULT"
```

Parse the `$ARG` from the user's argument:
- First non-flag argument is the container name (defaults to profile name if not provided)
- `--mount /host/path:/container/path[:mode]` — Additional volume mounts (can be specified multiple times)

Show the result: on success report the container URL and detected profile. On failure show the error.

**Examples:**
```bash
# Create with auto-detected profile name
/reflex:container create

# Create with custom name
/reflex:container create myproject

# Create with additional volume mounts
/reflex:container create myproject --mount /data:/workspace/data:ro --mount /configs:/workspace/.config:rw
```

### `/reflex:container query`

Send a query to a running container and get the response via tmux. This is the primary way to interact with containers for orchestration workflows.

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
URL_FILE="${CLAUDE_DIR}/reflex/.brainbox-url"

if [ ! -f "$URL_FILE" ]; then
  echo "Brainbox is not connected. Start it first:"
  echo "  /reflex:container start"
  exit 1
fi

URL=$(cat "$URL_FILE")

# Parse arguments: session_name and query text
# Format: /reflex:container query <session-name> <query-text>
SESSION_NAME=$(echo "$ARG" | awk '{print $1}')
QUERY=$(echo "$ARG" | cut -d' ' -f2-)

if [ -z "$SESSION_NAME" ] || [ -z "$QUERY" ]; then
  echo "Usage: /reflex:container query <session-name> <query>"
  echo ""
  echo "Examples:"
  echo "  /reflex:container query test-1 'What files are in the current directory?'"
  echo "  /reflex:container query myproject 'Run the tests'"
  exit 1
fi

# Build JSON payload
PAYLOAD=$(jq -n --arg q "$QUERY" '{prompt: $q, timeout: 300}')

API_KEY=$(curl -sf "${URL}/api/auth/key" --max-time 3 2>/dev/null | jq -r '.key // empty' 2>/dev/null || true)

RESULT=$(curl -sf -X POST "${URL}/api/sessions/${SESSION_NAME}/query" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${API_KEY}" \
  -d "$PAYLOAD" --max-time 320 2>&1)

echo "$RESULT"
```

Show the result to the user. On success, display the container's response. On timeout or error, show the error message.

**Examples:**
```bash
# Query a container
/reflex:container query test-1 Create a Python script that prints hello world

# Run commands
/reflex:container query myproject List all files in the workspace
```

### `/reflex:container health`

Check health status of observability services (LangFuse, Qdrant).

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
URL_FILE="${CLAUDE_DIR}/reflex/.brainbox-url"

if [ ! -f "$URL_FILE" ]; then
  echo "Brainbox is not connected. Start it first:"
  echo "  /reflex:container start"
  exit 1
fi

URL=$(cat "$URL_FILE")

echo "## Observability Health"
echo ""

# LangFuse
LANGFUSE=$(curl -sf "${URL}/api/langfuse/health" --max-time 3 2>/dev/null || echo '{"healthy":false}')
LANGFUSE_STATUS=$(echo "$LANGFUSE" | jq -r 'if .healthy then "Online" else "Offline" end')
echo "**LangFuse:** ${LANGFUSE_STATUS}"

# Qdrant
QDRANT=$(curl -sf "${URL}/api/qdrant/health" --max-time 3 2>/dev/null || echo '{"healthy":false}')
QDRANT_STATUS=$(echo "$QDRANT" | jq -r 'if .healthy then "Online" else "Offline" end')
QDRANT_URL=$(echo "$QDRANT" | jq -r '.url // "unknown"')
echo "**Qdrant:** ${QDRANT_STATUS} (${QDRANT_URL})"
```

### `/reflex:container config`

Show or set configuration values. With no extra arguments, show current config. With key=value pairs, update the config file.

**Show config:**
```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CONFIG_FILE="${CLAUDE_DIR}/reflex/brainbox.json"

if [ -f "$CONFIG_FILE" ]; then
  echo "## Brainbox Config"
  echo '```json'
  cat "$CONFIG_FILE" | jq .
  echo '```'
else
  echo "No config file. Using defaults:"
  echo '```json'
  echo '{"url": "http://127.0.0.1:9999", "autostart": true}'
  echo '```'
fi
echo ""
echo "Config file: ${CONFIG_FILE}"
echo ""
echo "Set values with:"
echo "  /reflex:container config url=http://host:port"
echo "  /reflex:container config autostart=false"
```

**Set config (e.g. `url=http://remote:8080`):**

Parse the key=value argument. Read the existing config (or start with defaults), update the key, and write back:

```bash
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CONFIG_FILE="${CLAUDE_DIR}/reflex/brainbox.json"
mkdir -p "${CLAUDE_DIR}/reflex"

# Read existing or defaults
if [ -f "$CONFIG_FILE" ]; then
  CONFIG=$(cat "$CONFIG_FILE")
else
  CONFIG='{"url": "http://127.0.0.1:9999", "autostart": true}'
fi

# Apply the update — the key and value come from the user's argument
# e.g. for "url=http://remote:8080":
echo "$CONFIG" | jq --arg key "$KEY" --arg val "$VALUE" '.[$key] = (if $val == "true" then true elif $val == "false" then false else $val end)' > "$CONFIG_FILE"

echo "Updated $KEY = $VALUE"
cat "$CONFIG_FILE" | jq .
```

### No argument or invalid

If no argument or invalid argument provided, show usage:

```
Usage: /reflex:container <start|stop|status|create|query|dashboard|health|config>

Manage the brainbox API for sandboxed dev environments.

Commands:
  start      Start the API locally (auto-discovers or auto-starts)
  stop       Stop a locally auto-started API
  status     Show connection info and running containers
  create     Create a container (auto-detects profile from env)
             Syntax: create [name] [--mount /host:/container[:mode]] ...
  query      Send a query to a running container via tmux
             Syntax: query <session-name> <query-text>
  dashboard  Open the dashboard in browser
  health     Check observability services (LangFuse, Qdrant)
  config     Show/set configuration (url, autostart)

Configuration:
  Config file: ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/reflex/brainbox.json
  Default API port: 9999

  Environment variable overrides (highest priority):
    BRAINBOX_URL        API endpoint (local or remote)
    BRAINBOX_AUTOSTART  true/false (default: true)

Examples:
  /reflex:container start
  /reflex:container create
  /reflex:container create myproject
  /reflex:container create myproject --mount /data:/workspace/data:ro
  /reflex:container query test-1 'List all files in the workspace'
  /reflex:container health
  /reflex:container status
  /reflex:container config url=http://remote:9999
  /reflex:container config autostart=false
```
