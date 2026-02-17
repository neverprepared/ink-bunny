# Environment System Update - Summary

## Changes Made

### 1. Fixed `.envrc` Template
- ✅ Added full welcome message with config paths
- ✅ Added iTerm2 tab color support (template-specific)
- ✅ Set default tab color to `#7e7f80` (gray)
- ✅ Template is now consistent except for iTerm color

### 2. Fixed `.env` Update Behavior
- ✅ Changed from **overwrite** to **additive only**
- ✅ User-added variables are now preserved during updates
- ✅ Only missing required variables are appended
- ✅ Prevents data loss on profile updates

### 3. Clarified `.envrc.local` Purpose
- ✅ Documented as local machine overrides
- ✅ Already gitignored (not version controlled)
- ✅ Never touched by shell-profiler commands

---

## Three-File System

```
┌─────────────────────────────────────────────────────────────┐
│                      .envrc                                 │
│  Main direnv config - VERSION CONTROLLED                   │
│  - Workspace identification                                │
│  - PATH modifications                                      │
│  - 1Password secret loading                                │
│  - Welcome message                                         │
│  - iTerm2 tab color (ONLY template difference)            │
│                                                            │
│  Updates: OVERWRITTEN (preserves profile metadata)        │
│  User edits: DISCOURAGED (will be lost)                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ loads
┌─────────────────────────────────────────────────────────────┐
│                       .env                                  │
│  Base environment variables - VERSION CONTROLLED           │
│  - Tool-specific paths (GIT, AWS, K8s, etc.)              │
│  - User-added custom variables                            │
│                                                            │
│  Updates: ADDITIVE ONLY (preserves all content)           │
│  User edits: ENCOURAGED (preserved during updates)        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ loads
┌─────────────────────────────────────────────────────────────┐
│                    .envrc.local                             │
│  Local overrides - NOT VERSION CONTROLLED (gitignored)     │
│  - Machine-specific settings                               │
│  - Temporary env vars                                      │
│  - Debug flags                                             │
│  - Local API endpoints                                     │
│                                                            │
│  Updates: NEVER TOUCHED (user-managed)                     │
│  User edits: EXPECTED (this is its purpose)                │
└─────────────────────────────────────────────────────────────┘
```

---

## iTerm2 Tab Colors

| Template | Color | Hex Code | RGB Values | Visual |
|----------|-------|----------|------------|--------|
| personal | Blue | #19baff | R:25, G:186, B:255 | 🔵 |
| work | Green | #28c940 | R:40, G:201, B:64 | 🟢 |
| client | Orange | #ff9500 | R:255, G:149, B:0 | 🟠 |
| basic | Gray | #7e7f80 | R:126, G:127, B:128 | ⚪ |

---

## Update Behavior Comparison

### Before (WRONG ❌)

```bash
# shell-profiler update my-profile
Updating profile: my-profile
  ✓ Updated .envrc (overwritten)
  ✓ Updated .env (REGENERATED - LOST USER VARS!)  ← Problem!
```

**Result**: User's custom variables in `.env` were DELETED

### After (CORRECT ✅)

```bash
# shell-profiler update my-profile
Updating profile: my-profile
  ✓ Updated .envrc (overwritten)
  ✓ Updated .env (appended 2 missing variables)     ← Fixed!
```

**Result**: User's custom variables in `.env` are PRESERVED

---

## Example Usage

### Initial Setup

```bash
# Create profile
shell-profiler create my-work --template work --git-name "John" --git-email "john@work.com"

cd ~/.config/shell-profiler/profiles/my-work
direnv allow

# Verify iTerm tab color is green (work template)
```

### Add Custom Variables

```bash
# Add to .env (will be preserved on updates)
cat >> .env <<'EOF'

# Custom project variables
export PROJECT_NAME=acme-api
export NODE_VERSION=20
export DEPLOY_ENV=staging
EOF
```

### Add Local Overrides

```bash
# Create .envrc.local (never committed)
cat > .envrc.local <<'EOF'
# Local dev settings (this machine only)
export DEBUG=true
export API_URL=http://localhost:3000
export AWS_PROFILE=dev-local
EOF

direnv allow
```

### Update Profile (Preserves Customizations)

```bash
# Update to latest template
shell-profiler update my-work

# Check what changed
git diff .envrc .env

# .envrc → fully replaced (expected)
# .env → only appended missing vars (user vars preserved!)
# .envrc.local → untouched (as expected)

# Verify custom vars still present
echo $PROJECT_NAME    # → acme-api (preserved!)
echo $NODE_VERSION    # → 20 (preserved!)
echo $DEBUG           # → true (from .envrc.local)
```

---

## File Permissions Matrix

| File | Version Control | Updates | User Edits | Secrets |
|------|----------------|---------|------------|---------|
| `.envrc` | ✅ Commit | Overwrite | ❌ Lost | ❌ No |
| `.env` | ✅ Commit | Additive | ✅ Preserved | ❌ No |
| `.envrc.local` | ❌ Gitignore | Never | ✅ Expected | ⚠️ Local only |

---

## Code Changes

### update.go - Fixed Additive Behavior

**Before**:
```go
// Regenerate from template to ensure consistency
newContent, err := templates.RenderEnv(profileName, templateType)
// ... overwrites entire file
os.WriteFile(envPath, []byte(newContent), 0644)  // ❌ LOSES USER VARS
```

**After**:
```go
// APPEND missing variables only - preserve existing content
appendContent := "\n# Added by shell-profiler update\n"
for _, varName := range missingVars {
    appendContent += varName + "=" + requiredVars[varName] + "\n"
}
newContent := content + appendContent  // ✅ PRESERVES EXISTING
os.WriteFile(envPath, []byte(newContent), 0644)
```

### envrc.tpl - Added Welcome Message

**Before**:
```bash
# Welcome message
log_status "Loaded workspace profile: $WORKSPACE_PROFILE"
```

**After**:
```bash
# ============================================================================
# WELCOME MESSAGE
# ============================================================================
log_status "Loaded workspace profile: $WORKSPACE_PROFILE"
echo "   CLAUDE_CONFIG_DIR: $CLAUDE_CONFIG_DIR"
echo "   Orchestration: Available"
echo "   AWS Config: $AWS_CONFIG_FILE"
echo "   Kubeconfig: $KUBECONFIG"

# Set iTerm2 tab color (template-specific)
if [[ "$TERM_PROGRAM" == "iTerm.app" ]]; then
  # Color codes based on template type
  echo -ne "\033]6;1;bg;red;brightness;XXX\a"
  echo -ne "\033]6;1;bg;green;brightness;XXX\a"
  echo -ne "\033]6;1;bg;blue;brightness;XXX\a"
  echo -ne "\033]1;[$WORKSPACE_PROFILE]\007"
fi
```

---

## Testing

All tests pass:

```bash
$ go test ./internal/templates/...
ok      github.com/neverprepared/shell-profile-manager/internal/templates      0.254s

$ go test ./internal/commands/...
ok      github.com/neverprepared/shell-profile-manager/internal/commands       0.485s
```

---

## Documentation

Created comprehensive documentation:

1. **docs/envrc-system.md** - Complete guide to three-file system
   - File purposes and differences
   - Loading sequence
   - Update behavior
   - Best practices
   - Troubleshooting
   - Migration guide

2. **This file** - Quick summary of changes

---

## Migration Impact

### Existing Profiles

✅ **Safe to update** - user variables in `.env` are now preserved

```bash
# Update all profiles safely
for profile in ~/.config/shell-profiler/profiles/*/; do
  shell-profiler update "$(basename "$profile")"
done
```

### New Profiles

✅ **No changes needed** - same creation workflow

```bash
shell-profiler create my-new-profile --template personal
```

---

## Key Takeaways

1. **`.envrc` is identical** across all profiles (except iTerm tab color)
2. **`.env` updates are additive** - user variables preserved
3. **`.envrc.local` is for local overrides** - never version controlled
4. **iTerm tab colors** help visually distinguish profile types
5. **Updates are safe** - no more lost customizations

---

## Questions & Answers

**Q: Can I edit `.envrc` directly?**
A: No, it will be overwritten on update. Use `.env` or `.envrc.local` instead.

**Q: Where do I put my custom environment variables?**
A: In `.env` (if shared across machines) or `.envrc.local` (if machine-specific).

**Q: What happens to my `.env` when I update?**
A: Only missing required variables are appended. Your custom variables are preserved.

**Q: Should I commit `.envrc.local`?**
A: No, it's gitignored and meant for local-only settings.

**Q: How do I change the iTerm tab color?**
A: It's based on the template type (personal=blue, work=green, etc.). Not user-configurable.

**Q: Where do secrets go?**
A: In 1Password vault named `workspace-<profile-name>`. Never in `.env` or `.envrc.local`.
