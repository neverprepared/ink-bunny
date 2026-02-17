# Environment Configuration System

## Overview

Shell-profiler uses a three-file system for environment configuration:

```
.envrc         → Main direnv config (version controlled)
.env           → Base environment variables (version controlled, additive updates)
.envrc.local   → Local overrides (NOT version controlled, gitignored)
```

## File Descriptions

### `.envrc` - Main direnv Configuration

**Purpose**: Core direnv logic and loading sequence

**Status**: ✅ Version controlled, identical across all profiles (except iTerm color)

**Contains**:
- Workspace identification (`WORKSPACE_PROFILE`, `WORKSPACE_HOME`)
- PATH modifications (`PATH_add bin`)
- Global profile loading logic
- 1Password secret resolution with caching
- Loading sequence for `.env` and `.envrc.local`
- Welcome message and iTerm2 tab color

**Template variables**:
- `{{.ProfileName}}` - Only in comments
- `{{.Template}}` - Only for iTerm2 tab color selection
- `{{.CreatedAt}}` - Only in comments

**Updates**: Overwritten by `shell-profiler create/update` - should not be manually edited

**Example**:
```bash
#!/usr/bin/env bash
# Workspace profile: personal
# Template: personal
# Created: 2024-02-16 20:00:00 UTC

export WORKSPACE_PROFILE="personal"
export WORKSPACE_HOME="$PWD"

PATH_add bin

# Load resolved environment (template + secrets)
dotenv_if_exists "$_sp_env"

# Load local overrides
dotenv_if_exists .envrc.local

# Welcome message
log_status "Loaded workspace profile: $WORKSPACE_PROFILE"

# Set iTerm2 tab color (blue #19baff for personal)
if [[ "$TERM_PROGRAM" == "iTerm.app" ]]; then
  echo -ne "\033]6;1;bg;red;brightness;25\a"
  echo -ne "\033]6;1;bg;green;brightness;186\a"
  echo -ne "\033]6;1;bg;blue;brightness;255\a"
  echo -ne "\033]1;[$WORKSPACE_PROFILE]\007"
fi
```

---

### `.env` - Base Environment Variables

**Purpose**: Tool-specific paths and configuration (non-secret)

**Status**: ✅ Version controlled, template-based with user additions preserved

**Contains**:
- Git configuration paths (`GIT_CONFIG_GLOBAL`, `GIT_SSH_COMMAND`)
- XDG base directories (`XDG_CONFIG_HOME`)
- Tool-specific config paths (AWS, Kubernetes, Terraform, Azure, GCP, Claude, Gemini)
- User-added custom variables (preserved during updates)

**Updates**:
- **Create**: Generated from template
- **Update**: **ADDITIVE ONLY** - missing variables are appended, existing content preserved

**Example**:
```bash
# Environment variables for workspace profile: personal
# Template: personal

# Git configuration
GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/.gitconfig"
GIT_SSH_COMMAND="ssh -F $WORKSPACE_HOME/.ssh/config"

# XDG Base Directory specification
XDG_CONFIG_HOME="$WORKSPACE_HOME/.config"

# 1Password SSH Agent
SSH_AUTH_SOCK="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"

# AWS configuration
AWS_CONFIG_FILE="$WORKSPACE_HOME/.aws/config"
AWS_SHARED_CREDENTIALS_FILE="$WORKSPACE_HOME/.aws/credentials"

# Kubernetes configuration
KUBECONFIG="$WORKSPACE_HOME/.kube/config"

# Terraform configuration
TF_CLI_CONFIG_FILE="$WORKSPACE_HOME/.terraformrc"

# Azure CLI configuration
AZURE_CONFIG_DIR="$WORKSPACE_HOME/.azure"

# Google Cloud SDK configuration
CLOUDSDK_CONFIG="$WORKSPACE_HOME/.gcloud"

# Claude Code configuration
CLAUDE_CONFIG_DIR="$WORKSPACE_HOME/.config/claude"

# Gemini CLI configuration
GEMINI_CONFIG_DIR="$WORKSPACE_HOME/.config/gemini"

# ============================================================
# USER-ADDED VARIABLES BELOW (preserved during updates)
# ============================================================

# Custom variables
export NODE_ENV=development
export LOG_LEVEL=debug
export CUSTOM_TOOL_PATH=/usr/local/custom-tool
```

---

### `.envrc.local` - Local Overrides

**Purpose**: Machine-specific or temporary settings

**Status**: ❌ NOT version controlled (gitignored)

**Contains**:
- Local development overrides
- Machine-specific paths
- Temporary environment variables
- Debugging flags
- Local API endpoints

**Updates**: Never touched by `shell-profiler` - manually managed

**Example**:
```bash
# Local overrides for this machine only
# This file is gitignored and NOT version controlled

# Override AWS region for local development
export AWS_DEFAULT_REGION=us-west-2

# Local debugging
export DEBUG=true
export LOG_LEVEL=trace

# Machine-specific paths
export JAVA_HOME=/usr/local/java-17
export ANDROID_HOME=/Users/me/Library/Android/sdk

# Local API endpoints
export API_URL=http://localhost:3000
export DATABASE_URL=postgresql://localhost:5432/mydb_dev

# Temporary feature flags
export FEATURE_NEW_UI=enabled
export FEATURE_BETA_API=true

# Custom aliases (won't work in direnv, but kept for reference)
# alias ll='ls -la'
```

---

## Loading Sequence

When you `cd` into a profile directory:

```
1. direnv reads .envrc
   ↓
2. .envrc sets WORKSPACE_PROFILE and WORKSPACE_HOME
   ↓
3. .envrc loads global/.global/exports.sh (if exists)
   ↓
4. .envrc resolves profile environment:
   - Starts with .env (base template)
   - Appends 1Password secrets from vault
   - Caches result in $TMPDIR/sp-profiles/$WORKSPACE_PROFILE/.env
   ↓
5. .envrc loads cached environment with dotenv_if_exists
   ↓
6. .envrc loads .envrc.local (if exists)
   ↓
7. Welcome message + iTerm2 color
```

---

## File Comparison

| Aspect | .envrc | .env | .envrc.local |
|--------|--------|------|--------------|
| **Purpose** | direnv logic | Base env vars | Local overrides |
| **Version Control** | ✅ Yes | ✅ Yes | ❌ No (gitignored) |
| **Template-based** | ✅ Yes | ✅ Yes | ❌ No (user-managed) |
| **Updates** | Overwritten | Additive only | Never touched |
| **User edits** | ❌ Discouraged | ✅ Preserved | ✅ Expected |
| **Contains secrets** | ❌ No | ❌ No | ⚠️ Maybe (local only) |
| **Profile-specific** | ✅ Yes (iTerm color) | ⚠️ Mostly same | ✅ Yes |

---

## Update Behavior

### shell-profiler create

Creates all files from templates:
- `.envrc` → Full template (with profile name and template type)
- `.env` → Full template (base variables)
- `.envrc.local` → NOT created (user creates as needed)

### shell-profiler update

Updates existing profiles:
- `.envrc` → **OVERWRITTEN** with latest template (preserves profile name/type)
- `.env` → **ADDITIVE** - only appends missing variables
- `.envrc.local` → **NEVER TOUCHED** - preserved as-is

---

## Best Practices

### ✅ DO

1. **Commit `.envrc` and `.env` to git**
   ```bash
   git add .envrc .env
   git commit -m "feat: add workspace profile"
   ```

2. **Add user variables to `.env`**
   ```bash
   # Add at the end of .env
   export MY_CUSTOM_VAR=value
   ```

3. **Use `.envrc.local` for local-only settings**
   ```bash
   # .envrc.local (never committed)
   export DEBUG=true
   export AWS_PROFILE=dev
   ```

4. **Store secrets in 1Password**
   - Vault name: `workspace-<profile-name>`
   - Secrets auto-loaded by `.envrc` into cached `.env`

5. **Run `direnv allow` after changes**
   ```bash
   direnv allow
   ```

### ❌ DON'T

1. **Don't manually edit `.envrc`**
   - It will be overwritten on update
   - Profile-specific logic belongs in `.env` or `.envrc.local`

2. **Don't commit `.envrc.local`**
   - It's gitignored for a reason
   - Machine-specific settings shouldn't be shared

3. **Don't put secrets in `.env`**
   - Use 1Password vault instead
   - Secrets are auto-loaded and cached

4. **Don't delete variables from `.env` manually**
   - Comment them out instead if not needed
   - Updates will re-add required variables

---

## iTerm2 Tab Colors

The only template-specific difference in `.envrc`:

| Template | Color | Hex | Use Case |
|----------|-------|-----|----------|
| **personal** | Blue | `#19baff` | Personal projects |
| **work** | Green | `#28c940` | Work projects |
| **client** | Orange | `#ff9500` | Client projects |
| **basic** | Gray | `#7e7f80` | Default/testing |

Colors help visually distinguish profile types in iTerm2.

---

## Troubleshooting

### Profile not loading
```bash
# Check direnv status
direnv status

# Allow .envrc
direnv allow

# Verify environment
echo $WORKSPACE_PROFILE
```

### Variables not set
```bash
# Check if .env exists
ls -la .env

# Check loading sequence
cat .envrc | grep dotenv

# Manually source for debugging
source .env
```

### 1Password secrets not loading
```bash
# Check op CLI installed
which op

# Check vault exists
op vault list | grep workspace-

# Check cache
ls -la $TMPDIR/sp-profiles/
```

### Local overrides not working
```bash
# Verify .envrc.local exists
ls -la .envrc.local

# Check it's loaded after .env
cat .envrc | grep envrc.local

# Verify it's gitignored
git check-ignore -v .envrc.local
```

---

## Migration Guide

### From old single-file system

If you have an old profile with everything in `.envrc`:

1. **Backup current .envrc**
   ```bash
   cp .envrc .envrc.backup
   ```

2. **Extract user variables**
   ```bash
   # Find custom exports in .envrc
   grep "^export" .envrc > my-vars.txt
   ```

3. **Run update**
   ```bash
   shell-profiler update <profile-name>
   ```

4. **Move user variables to .env**
   ```bash
   # Append to .env
   cat my-vars.txt >> .env
   ```

5. **Test and cleanup**
   ```bash
   direnv allow
   echo $WORKSPACE_PROFILE
   rm my-vars.txt .envrc.backup
   ```

---

## Example Workflow

### Creating a new profile

```bash
# Create profile
shell-profiler create my-project --template work

# Navigate to profile
cd ~/.config/shell-profiler/profiles/my-project

# Allow direnv
direnv allow

# Add custom variables
echo 'export NODE_VERSION=18' >> .env

# Add local overrides
cat > .envrc.local <<'EOF'
# Local dev settings
export DEBUG=true
export API_URL=http://localhost:3000
EOF

# Reload
direnv allow

# Verify
echo $WORKSPACE_PROFILE
echo $NODE_VERSION
echo $DEBUG
```

### Updating an existing profile

```bash
# Update profile (preserves user variables)
shell-profiler update my-project

# Check what was updated
git diff .envrc .env

# If satisfied, commit
git add .envrc .env
git commit -m "chore: update profile to latest template"
```

---

## Summary

- **`.envrc`** = Consistent logic across all profiles (except iTerm color)
- **`.env`** = Base variables (updated additively, user additions preserved)
- **`.envrc.local`** = Local machine overrides (never version controlled)

This three-file system provides:
- ✅ Consistency across profiles
- ✅ Preserved user customizations
- ✅ Machine-specific flexibility
- ✅ Clear separation of concerns
