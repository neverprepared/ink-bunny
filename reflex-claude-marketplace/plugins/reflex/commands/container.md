---
description: Manage the brainbox API and sandboxed dev environments
allowed-tools: Bash(curl:*), Bash(brainbox:*), Bash(open:*), Bash(kill:*), Bash(cat:*), Bash(mkdir:*), Bash(echo:*), Bash(jq:*)
argument-hint: <start|stop|status|dashboard|config>
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
  echo "  Using defaults (url: http://127.0.0.1:8000, autostart: true)"
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
  echo '{"url": "http://127.0.0.1:8000", "autostart": true}'
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
  CONFIG='{"url": "http://127.0.0.1:8000", "autostart": true}'
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
Usage: /reflex:container <start|stop|status|dashboard|config>

Manage the brainbox API for sandboxed dev environments.

Commands:
  start      Start the API locally (auto-discovers or auto-starts)
  stop       Stop a locally auto-started API
  status     Show connection info and running containers
  dashboard  Open the dashboard in browser
  config     Show/set configuration (url, autostart)

Configuration:
  Config file: ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/reflex/brainbox.json

  Environment variable overrides (highest priority):
    BRAINBOX_URL        API endpoint (local or remote)
    BRAINBOX_AUTOSTART  true/false (default: true)

Examples:
  /reflex:container start
  /reflex:container status
  /reflex:container config url=http://remote:8080
  /reflex:container config autostart=false
```
