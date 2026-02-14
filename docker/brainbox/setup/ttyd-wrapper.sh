#!/bin/bash
# Start tmux session with claude

# Attach to existing session, or create new one with claude
if tmux has-session -t main 2>/dev/null; then
    exec tmux attach -t main
else
    # Create session
    tmux -f /dev/null new -d -s main
    tmux set -t main status off
    tmux set -t main mouse on

    # Start claude (env vars are loaded via BASH_ENV -> .bashrc -> .env)
    CLAUDE_CMD="claude --dangerously-skip-permissions"
    if [ -n "$CLAUDE_MODEL" ]; then
        CLAUDE_CMD="$CLAUDE_CMD --model $CLAUDE_MODEL"
    fi
    tmux send-keys -t main "$CLAUDE_CMD" Enter
    exec tmux attach -t main
fi
