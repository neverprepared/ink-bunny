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
    # --plugin-dir mirrors the host wrapper: claude --plugin-dir .../reflex
    CLAUDE_CMD="claude --plugin-dir /opt/reflex/share/reflex --dangerously-skip-permissions"
    if [ -n "$CLAUDE_MODEL" ]; then
        CLAUDE_CMD="$CLAUDE_CMD --model $CLAUDE_MODEL"
    fi

    # Start Claude interactively; hub-spawned workers get their task injected
    # as the first prompt so the session stays alive for follow-up queries.
    tmux send-keys -t main "$CLAUDE_CMD" Enter
    # Poll for BOTH task.txt existence AND Claude at an idle prompt (up to 120s).
    # task.txt is written by configure() after the container starts, so we must
    # not check for it before the loop — it may not exist yet under load.
    #
    # We wait for a stable "❯ " prompt with NO pending dialog text on the same
    # line, then sleep 3 s and re-verify before sending.  This avoids firing
    # during the startup /agents and /mcp dialogs which briefly show "❯" then
    # swallow the next keystroke.
    READY=0
    for i in $(seq 1 60); do
        sleep 2
        if [ -f "/home/developer/.brainbox/task.txt" ] && \
           tmux capture-pane -t main -p 2>/dev/null | grep -qE "^❯ *$"; then
            READY=$((READY + 1))
            if [ "$READY" -ge 2 ]; then
                # Collapse newlines to spaces — tmux send-keys fires Enter on
                # every newline character, which breaks multi-line task content.
                TASK_ONELINER=$(tr '\n' ' ' < /home/developer/.brainbox/task.txt | sed 's/  */ /g; s/^ //; s/ $//')
                tmux send-keys -t main "$TASK_ONELINER" Enter
                break
            fi
        else
            READY=0
        fi
    done
    exec tmux attach -t main
fi
