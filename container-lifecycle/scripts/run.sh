#!/bin/bash
# Start/reuse container via lifecycle manager, inject auth tokens, start ttyd web terminal

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/developer"
SECRETS_DIR="$CONFIG_DIR/.secrets"
SESSION_NAME=""
VOLUME_MOUNT=""
NO_OPEN=false
QUERY=""

# Parse arguments
while getopts "s:v:nq:" opt; do
    case $opt in
        s)
            SESSION_NAME="$OPTARG"
            ;;
        v)
            VOLUME_MOUNT="$OPTARG"
            ;;
        n)
            NO_OPEN=true
            ;;
        q)
            QUERY="$OPTARG"
            ;;
        *)
            echo "Usage: $0 [-s session_name] [-v /host/path:/container/path] [-n] [-q \"question\"]"
            exit 1
            ;;
    esac
done

SESSION_NAME="${SESSION_NAME:-default}"
CONTAINER_NAME="developer-${SESSION_NAME}"

# === Token setup (interactive — must happen before lifecycle) ===

mkdir -p "$SECRETS_DIR"

if [ ! -f "$SECRETS_DIR/CLAUDE_CODE_OAUTH_TOKEN" ]; then
    # Check if token is already in environment (e.g. from direnv)
    if [ -n "$CLAUDE_CODE_OAUTH_TOKEN" ]; then
        echo "$CLAUDE_CODE_OAUTH_TOKEN" > "$SECRETS_DIR/CLAUDE_CODE_OAUTH_TOKEN"
        chmod 600 "$SECRETS_DIR/CLAUDE_CODE_OAUTH_TOKEN"
        echo "Saved Claude Code token from environment."
    else
        echo ""
        echo "=== Claude Code setup ==="
        echo ""
        echo "No Claude Code token found. Let's set one up."
        echo ""
        echo "Run this command in another terminal:"
        echo ""
        echo "  claude setup-token"
        echo ""
        echo "It will generate a long-lived OAuth token (valid for 1 year)."
        echo "Paste the token below."
        echo ""
        while true; do
            read -p "Token: " claude_token
            if [ -n "$claude_token" ]; then
                echo "$claude_token" > "$SECRETS_DIR/CLAUDE_CODE_OAUTH_TOKEN"
                chmod 600 "$SECRETS_DIR/CLAUDE_CODE_OAUTH_TOKEN"
                echo "Saved."
                break
            fi
            echo "Token is required. Please run 'claude setup-token' and paste the result."
        done
    fi
fi

if [ ! -f "$SECRETS_DIR/GH_TOKEN" ]; then
    if [ -n "$GH_TOKEN" ]; then
        echo "$GH_TOKEN" > "$SECRETS_DIR/GH_TOKEN"
        chmod 600 "$SECRETS_DIR/GH_TOKEN"
        echo "Saved GitHub token from environment."
    else
        echo ""
        echo "=== GitHub CLI setup ==="
        echo ""
        echo "No GitHub token found. Let's set one up."
        echo ""
        echo "Run this in another terminal:"
        echo ""
        echo "  gh auth token"
        echo ""
        echo "Or create a Personal Access Token at:"
        echo "  https://github.com/settings/tokens"
        echo ""
        echo "Paste the token below (or press Enter to skip)."
        echo ""
        read -p "Token: " gh_token

        if [ -n "$gh_token" ]; then
            echo "$gh_token" > "$SECRETS_DIR/GH_TOKEN"
            chmod 600 "$SECRETS_DIR/GH_TOKEN"
            echo "Saved."
        else
            echo "No token provided, skipping. You can set it up later by re-running this script."
        fi
    fi
fi

# === Delegate to lifecycle manager (legacy/dev mode — hardened=false) ===

LIFECYCLE_ARGS="run --session $SESSION_NAME --hardened false"

if [ -n "$VOLUME_MOUNT" ]; then
    LIFECYCLE_ARGS="$LIFECYCLE_ARGS --volume $VOLUME_MOUNT"
fi

OUTPUT=$(uv run python -m container_lifecycle $LIFECYCLE_ARGS 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Lifecycle error: $OUTPUT"
    exit 1
fi

# Extract port from lifecycle output
PORT=$(echo "$OUTPUT" | grep -o '"port":[0-9]*' | head -1 | cut -d: -f2)
PORT="${PORT:-7681}"

# Set git config from GitHub account if logged in
if [ -f "$SECRETS_DIR/GH_TOKEN" ]; then
    docker exec "$CONTAINER_NAME" bash -c '
        if gh auth status >/dev/null 2>&1; then
            USER_DATA=$(gh api user 2>/dev/null)
            if [ -n "$USER_DATA" ]; then
                NAME=$(echo "$USER_DATA" | jq -r ".name // .login")
                LOGIN=$(echo "$USER_DATA" | jq -r ".login")
                EMAIL=$(echo "$USER_DATA" | jq -r ".email // empty")
                [ -z "$EMAIL" ] && EMAIL="${LOGIN}@users.noreply.github.com"
                git config --global user.name "$NAME"
                git config --global user.email "$EMAIL"
            fi
        fi
    '
fi

echo ""
echo "Developer session running at: http://localhost:${PORT}"

# Query mode - send query to the interactive session
if [ -n "$QUERY" ]; then
    echo "Starting session and sending query..."
    docker exec "$CONTAINER_NAME" bash -c '
        if ! tmux has-session -t main 2>/dev/null; then
            tmux -f /dev/null new -d -s main
            tmux set -t main status off
            tmux set -t main mouse on
            tmux send-keys -t main "claude --dangerously-skip-permissions" Enter
        fi
    '
    sleep 3
    docker exec "$CONTAINER_NAME" tmux send-keys -t main "$QUERY" Enter
    sleep 0.5
    docker exec "$CONTAINER_NAME" tmux send-keys -t main Enter
    echo "Query sent: $QUERY"
fi
echo ""
echo "To stop: docker stop $CONTAINER_NAME"

# Open in browser (unless -n flag)
if [ "$NO_OPEN" = false ]; then
    if command -v open >/dev/null 2>&1; then
        open "http://localhost:${PORT}"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:${PORT}"
    fi
fi
