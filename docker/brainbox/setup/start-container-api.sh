#!/bin/bash
# Start the in-container API server that wraps Claude CLI
# This runs on port 9000 and accepts query requests from the orchestrator

set -euo pipefail

# Configuration
PORT="${CONTAINER_API_PORT:-9000}"
LOG_FILE="/home/developer/.container-api.log"

# Ensure we're running as developer user
if [ "$(id -u)" = "0" ]; then
    echo "ERROR: Do not run as root. Run as developer user." >&2
    exit 1
fi

# Check if Claude CLI is available
if ! command -v claude &>/dev/null; then
    echo "ERROR: Claude CLI not found. Is it installed?" >&2
    exit 1
fi

# Start the API server in the background
echo "Starting container API server on port ${PORT}..."

python3 -m brainbox.container_api \
    > "${LOG_FILE}" 2>&1 &

# Save PID
echo $! > /home/developer/.container-api.pid

echo "Container API server started (PID: $!, logs: ${LOG_FILE})"
echo "Health check: curl http://localhost:${PORT}/health"
