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

    # Hub-spawned workers receive their task via a file; run non-interactively
    if [ -f "/home/developer/.brainbox/task.txt" ]; then
        tmux send-keys -t main "$CLAUDE_CMD --print < /home/developer/.brainbox/task.txt 2>&1 | tee /home/developer/.brainbox/output.log" Enter
    else
        tmux send-keys -t main "$CLAUDE_CMD" Enter
    fi
    exec tmux attach -t main
fi
