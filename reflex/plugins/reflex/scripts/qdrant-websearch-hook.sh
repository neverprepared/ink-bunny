#!/bin/sh
# Qdrant WebSearch auto-storage hook for Reflex
# Called by Claude Code PostToolUse hook
# Automatically stores WebSearch results in Qdrant when available
#
# NOTE: Claude Code executes hooks via /bin/sh, ignoring the shebang.
# This script must be POSIX sh-compatible — no bash-specific features:
#   - No 'pipefail' (bash-only option)
#   - No BASH_SOURCE (use $0 instead)
#   - No here-strings <<< (use printf | instead)

set -eu

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check toggle (default: enabled)
if [ "${REFLEX_QDRANT_AUTOSAVE:-true}" = "false" ]; then
    exit 0
fi

# Read tool data from stdin (JSON from Claude Code hook)
TOOL_DATA=$(cat)

# Extract tool name
TOOL_NAME=$(printf '%s' "$TOOL_DATA" | jq -r '.tool_name // empty' 2>/dev/null || echo "")

# Filter for WebSearch only
if [ "$TOOL_NAME" != "WebSearch" ]; then
    exit 0
fi

# Delegate to Python (fail silently on error)
printf '%s' "$TOOL_DATA" | uvx --quiet --python 3.12 --with qdrant-client --with fastembed \
    python "$SCRIPT_DIR/qdrant-websearch-store.py" 2>/dev/null || true

exit 0
