#!/usr/bin/env bash
# Workspace profile: {{.ProfileName}}
# Template: {{.Template}}
# Created: {{.CreatedAt}}

# Workspace identification
export WORKSPACE_PROFILE="{{.ProfileName}}"
export WORKSPACE_HOME="$PWD"

# Add custom bin directory to PATH (before system paths)
# The bin/ssh wrapper uses the profile-specific SSH config
# Git will automatically use bin/ssh since it's first in PATH
PATH_add bin

# Load global profile settings (exports only)
# Environment variables work with direnv, aliases and functions do not
GLOBAL_DIR="$(cd "$(dirname "$PWD")/.global" 2>/dev/null && pwd)"
if [[ -d "$GLOBAL_DIR" ]]; then
    # Source exports (environment variables work with direnv)
    if [[ -f "$GLOBAL_DIR/exports.sh" && -r "$GLOBAL_DIR/exports.sh" ]]; then
        source "$GLOBAL_DIR/exports.sh"
    fi
fi

# Resolve profile environment (template .env + 1Password secrets)
# Cached in volatile storage with configurable expiration
_sp_cache="${TMPDIR:-/tmp}/sp-profiles/${WORKSPACE_PROFILE}"
_sp_env="${_sp_cache}/.env"
_sp_cache_hours="${SP_CACHE_HOURS:-2}"  # Default: 2 hours

# Check if cache exists and is fresh
_refresh_cache=false
if [ ! -f "$_sp_env" ]; then
    _refresh_cache=true
elif command -v stat &>/dev/null; then
    # Check cache age (in hours)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: stat -f %m gives modification time in seconds since epoch
        _cache_mtime=$(stat -f %m "$_sp_env" 2>/dev/null || echo 0)
    else
        # Linux: stat -c %Y gives modification time in seconds since epoch
        _cache_mtime=$(stat -c %Y "$_sp_env" 2>/dev/null || echo 0)
    fi
    _current_time=$(date +%s)
    _cache_age_hours=$(( (_current_time - _cache_mtime) / 3600 ))
    if [ "$_cache_age_hours" -ge "$_sp_cache_hours" ]; then
        _refresh_cache=true
        log_status "Cache expired (${_cache_age_hours}h old, max ${_sp_cache_hours}h)"
    fi
fi

if [ "$_refresh_cache" = true ]; then
    mkdir -p "$_sp_cache" && chmod 700 "$_sp_cache"
    # Start with template (tool paths, non-secret config)
    cp .env "$_sp_env"
    # Append 1Password secrets
    _op_vault="workspace-${WORKSPACE_PROFILE}"
    if command -v op &>/dev/null && command -v jq &>/dev/null; then
        _op_ids=$(op item list --vault "$_op_vault" --format json 2>/dev/null | jq -r '.[].id' 2>/dev/null)
        if [ -n "$_op_ids" ]; then
            # Start progress indicator (background process that prints dots)
            (
                while true; do
                    printf "." >&2
                    sleep 1
                done
            ) &
            _progress_pid=$!

            echo "" >> "$_sp_env"
            for _op_id in $_op_ids; do
                op item get "$_op_id" --format json 2>/dev/null | jq -r '
                    .title as $t |
                    .fields[] |
                    select(.value != "" and .value != null and .label != "" and .label != null and .id != "notesPlain" and .type != "OTP") |
                    ($t + "_" + .label | gsub("[^A-Za-z0-9]"; "_") | gsub("_+"; "_") | gsub("^_|_$"; "") | ascii_upcase) + "=" + (.value | @sh)
                ' >> "$_sp_env" 2>/dev/null
            done

            # Stop progress indicator
            kill $_progress_pid 2>/dev/null
            wait $_progress_pid 2>/dev/null
            printf "\n" >&2

            log_status "Loaded secrets from 1Password vault: $_op_vault"
        fi
    fi
    chmod 600 "$_sp_env"
fi

# Load the resolved environment (template + secrets)
dotenv_if_exists "$_sp_env"

# Load local overrides
dotenv_if_exists .envrc.local

# ============================================================================
# WELCOME MESSAGE
# ============================================================================
log_status "Loaded workspace profile: $WORKSPACE_PROFILE"
echo "   CLAUDE_CONFIG_DIR: $CLAUDE_CONFIG_DIR"
echo "   Orchestration: Available"
echo "   AWS Config: $AWS_CONFIG_FILE"
echo "   Kubeconfig: $KUBECONFIG"

# Set iTerm2 tab color{{if eq .Template "personal"}} (blue #19baff){{else if eq .Template "work"}} (green #28c940){{else if eq .Template "client"}} (orange #ff9500){{else}} (gray #7e7f80){{end}}
if [[ "$TERM_PROGRAM" == "iTerm.app" ]]; then
{{if eq .Template "personal"}}  # Personal: Blue (#19baff)
  echo -ne "\033]6;1;bg;red;brightness;25\a"
  echo -ne "\033]6;1;bg;green;brightness;186\a"
  echo -ne "\033]6;1;bg;blue;brightness;255\a"
{{else if eq .Template "work"}}  # Work: Green (#28c940)
  echo -ne "\033]6;1;bg;red;brightness;40\a"
  echo -ne "\033]6;1;bg;green;brightness;201\a"
  echo -ne "\033]6;1;bg;blue;brightness;64\a"
{{else if eq .Template "client"}}  # Client: Orange (#ff9500)
  echo -ne "\033]6;1;bg;red;brightness;255\a"
  echo -ne "\033]6;1;bg;green;brightness;149\a"
  echo -ne "\033]6;1;bg;blue;brightness;0\a"
{{else}}  # Basic: Gray (#7e7f80)
  echo -ne "\033]6;1;bg;red;brightness;126\a"
  echo -ne "\033]6;1;bg;green;brightness;127\a"
  echo -ne "\033]6;1;bg;blue;brightness;128\a"
{{end}}  echo -ne "\033]1;[$WORKSPACE_PROFILE]\007"
fi
