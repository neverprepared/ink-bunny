# Installation Guide

Complete installation and setup guide for the Workspace Profile Switcher.

## Prerequisites

### 1. Install direnv

**macOS** (using Homebrew):

```bash
brew install direnv
```

**Linux (Ubuntu/Debian)**:

```bash
sudo apt update
sudo apt install direnv
```

**Linux (Fedora/RHEL)**:

```bash
sudo dnf install direnv
```

**Linux (Arch)**:

```bash
sudo pacman -S direnv
```

**From Source**:

```bash
curl -sfL https://direnv.net/install.sh | bash
```

### 2. Hook direnv into Your Shell

After installing direnv, you need to hook it into your shell. Add the appropriate line to your shell's configuration file:

**Bash** (`~/.bashrc` or `~/.bash_profile`):

```bash
eval "$(direnv hook bash)"
```

**Zsh** (`~/.zshrc`):

```bash
eval "$(direnv hook zsh)"
```

**Fish** (`~/.config/fish/config.fish`):

```fish
direnv hook fish | source
```

**Tcsh** (`~/.cshrc`):

```tcsh
eval `direnv hook tcsh`
```

**Elvish** (`~/.elvish/rc.elv`):

```elvish
eval (direnv hook elvish)
```

### 3. Reload Your Shell

After adding the hook, reload your shell configuration:

```bash
# For bash
source ~/.bashrc

# For zsh
source ~/.zshrc

# Or simply start a new terminal session
exec $SHELL
```

### 4. Verify Installation

Check that direnv is properly installed and hooked:

```bash
# Check direnv version
direnv version

# Check if hook is loaded
type direnv
# Should output: direnv is a shell function
```

## Setup

### Option 1: Quick Setup

If you just want to get started quickly:

```bash

# Create your first profile
shell-profiler create my-project --interactive

# Activate the profile
cd ~/workspaces/profiles/my-project
direnv allow

# Verify it works
shell-profiler info
```

### Option 2: Manual Review

If you want to review and customize before using:

1. **Review the documentation**:

   ```bash
   cat ../README.md
   cat QUICKSTART.md
   ```

2. **Create a profile**:

   ```bash
   shell-profiler create my-project \
       --template personal \
       --git-name "Your Name" \
       --git-email "your@email.com"
   ```

3. **Review the generated files**:

   ```bash
   cd ~/workspaces/profiles/my-project
   cat .envrc
   cat .gitconfig
   ```

4. **Allow direnv**:

   ```bash
   direnv allow
   ```

5. **Test it**:
   ```bash
   echo $WORKSPACE_PROFILE
   git config user.email
   ```

## Post-Installation Configuration

### Optional: Add Global direnv Configuration

You can create `~/.config/direnv/direnvrc` for custom functions that will be available in all `.envrc` files:

```bash
mkdir -p ~/.config/direnv
cat > ~/.config/direnv/direnvrc << 'EOF'
# Custom direnv functions

# Simplified profile setup
use_profile() {
    local profile_name=$1
    export WORKSPACE_PROFILE="$profile_name"
    export WORKSPACE_HOME="$(pwd)"
    export GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/.gitconfig"
}

# AWS profile helper
use_aws() {
    export AWS_PROFILE=$1
    log_status "Using AWS profile: $AWS_PROFILE"
}

# Node version helper (requires nvm)
use_node() {
    local version=$1
    if command -v nvm &> /dev/null; then
        nvm use "$version"
    fi
}

# Python virtual environment helper
use_venv() {
    local venv_path=${1:-.venv}
    if [[ -d "$venv_path" ]]; then
        export VIRTUAL_ENV="$(pwd)/$venv_path"
        PATH_add "$VIRTUAL_ENV/bin"
        log_status "Activated Python venv: $venv_path"
    fi
}
EOF
```

### Optional: Set direnv Global Options

Create `~/.config/direnv/config.toml`:

```toml
[global]
# Load .env files automatically
load_dotenv = true

# Show what environment variables changed
warn_timeout = "5s"

# Customize log output
[log]
format = "direnv: %s"
```

### Optional: Shell Aliases

Add to your shell config (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
# Workspace profile aliases
alias wp='cd ~/workspaces/profiles'
alias wpl='shell-profiler list'
alias wpc='shell-profiler create'
alias wpi='shell-profiler info'

# Quick profile switching
alias wpwork='cd ~/workspaces/profiles/work'
alias wppersonal='cd ~/workspaces/profiles/personal'
```

## Verification

Run through this checklist to ensure everything is working:

- [ ] direnv is installed: `direnv version`
- [ ] direnv is hooked: `type direnv` shows it's a function
- [ ] Can create profiles: `shell-profiler create test --dry-run`
- [ ] Can list profiles: `shell-profiler list`
- [ ] Can activate profile: Navigate to profile and run `direnv allow`
- [ ] Environment loads: `echo $WORKSPACE_PROFILE` shows profile name
- [ ] Git config works: `git config user.email` shows profile email

## Troubleshooting

### direnv command not found

**Problem**: Shell can't find direnv after installation.

**Solution**:

1. Check if direnv is in PATH: `which direnv`
2. If installed from source, ensure installation directory is in PATH
3. Try reinstalling via package manager

### Hook not working

**Problem**: direnv hook is not activated in shell.

**Solution**:

1. Verify hook is in shell config file
2. Ensure you reloaded shell: `source ~/.bashrc` or `exec $SHELL`
3. Check for shell config syntax errors

### .envrc not loading

**Problem**: Environment variables not set when entering directory.

**Solution**:

1. Check direnv status: `direnv status`
2. Allow the directory: `direnv allow`
3. Verify .envrc has correct syntax
4. Check for errors: `bash -n .envrc`

### Git still using global config

**Problem**: git ignores the profile's .gitconfig.

**Solution**:

1. Verify environment variable: `echo $GIT_CONFIG_GLOBAL`
2. Check file exists: `ls -la $GIT_CONFIG_GLOBAL`
3. Test git: `git config --show-origin user.email`
4. Re-allow direnv: `direnv allow`

### Permission denied

**Problem**: Can't execute profile command.

**Solution**:

```bash
chmod +x shell-profiler
```

## Uninstallation

To completely remove the workspace profile system:

1. **Delete all profiles** (backup if needed):

   ```bash
   shell-profiler delete <profile-name>
   # Or manually:
   rm -rf ~/workspaces/profiles/
   ```

2. **Remove the shell-profiler config**:

   ```bash
   rm -f ~/.profile-manager
   ```

3. **Remove direnv hook** (optional):

   - Edit your shell config file
   - Remove the `eval "$(direnv hook ...)"` line
   - Reload shell

4. **Uninstall direnv** (optional):

   ```bash
   # macOS
   brew uninstall direnv

   # Linux (Ubuntu/Debian)
   sudo apt remove direnv

   # Linux (Fedora)
   sudo dnf remove direnv
   ```

## Getting Help

- **Documentation**: See [README.md](../README.md) and [QUICKSTART.md](QUICKSTART.md)
- **Command help**: Run `shell-profiler help` or `shell-profiler create --help`
- **direnv docs**: https://direnv.net/
- **Git environment variables**: https://git-scm.com/docs/git-config#ENVIRONMENT

## Next Steps

1. Read [QUICKSTART.md](QUICKSTART.md) for usage examples
2. Read [README.md](../README.md) for comprehensive documentation
3. Create your first profile: `shell-profiler create my-profile`
4. Customize templates and examples for your workflow
