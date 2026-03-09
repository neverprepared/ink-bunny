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

    # Start Claude interactively; hub-spawned workers get their task injected
    # as the first prompt so the session stays alive for follow-up queries.
    tmux send-keys -t main "$CLAUDE_CMD" Enter
    if [ -f "/home/developer/.brainbox/task.txt" ]; then
        # Wait for Claude to start, then send the task as the first prompt
        sleep 5
        tmux send-keys -t main "$(cat /home/developer/.brainbox/task.txt)" Enter
    fi
    exec tmux attach -t main
fi
