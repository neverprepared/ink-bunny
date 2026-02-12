# Quick Start Guide

Get up and running with workspace profiles in 5 minutes.

## Prerequisites

1. **Install direnv**:

   ```bash
   # macOS
   brew install direnv

   # Linux (Ubuntu/Debian)
   sudo apt install direnv

   # Linux (Fedora)
   sudo dnf install direnv
   ```

2. **Hook direnv into your shell**:

   **Bash** - Add to `~/.bashrc` or `~/.bash_profile`:

   ```bash
   eval "$(direnv hook bash)"
   ```

   **Zsh** - Add to `~/.zshrc`:

   ```bash
   eval "$(direnv hook zsh)"
   ```

   **Fish** - Add to `~/.config/fish/config.fish`:

   ```fish
   direnv hook fish | source
   ```

3. **Reload your shell**:
   ```bash
   exec $SHELL
   ```

## Create Your First Profile

### Option 1: Interactive Setup (Recommended for First-Time Users)

```bash
profile create my-project --interactive
```

Follow the prompts to configure your profile.

### Option 2: Quick Setup

```bash
# Create a basic profile
profile create my-project

# Or create with git configuration
profile create my-project \
    --git-name "Your Name" \
    --git-email "your.email@example.com"

# Use a template
profile create work-project --template work \
    --git-name "Work Name" \
    --git-email "work@company.com"
```

### Option 3: Use Existing Examples

Three example profiles are already created:

- `profiles/personal` - Personal projects
- `profiles/work` - Work projects
- `profiles/client-acme` - Client projects

## Activate a Profile

1. **Navigate to the profile directory**:

   ```bash
   cd profiles/personal
   ```

2. **Allow direnv** (first time only):

   ```bash
   direnv allow
   ```

   You should see:

   ```
   direnv: loading ~/workspaces/build/workspace-profiles/profiles/personal/.envrc
   direnv: export +GIT_CONFIG_GLOBAL +WORKSPACE_HOME +WORKSPACE_PROFILE ~PATH
   ```

3. **Verify the profile is loaded**:

   ```bash
   echo $WORKSPACE_PROFILE
   # Output: personal

   git config user.name
   # Output: Personal User

   git config user.email
   # Output: personal@example.com
   ```

## Test Profile Switching

Switch between profiles and watch the environment change:

```bash
# Go to personal profile
cd profiles/personal
git config user.email
# Output: personal@example.com

# Switch to work profile
cd ../work
git config user.email
# Output: work@company.com

# Switch to client profile
cd ../client-acme
git config user.email
# Output: dev@acmecorp.com

# Leave all profiles
cd ../..
git config user.email
# Output: (your global git config)
```

## Common Tasks

### Customize Git Configuration

Edit the profile's git config:

```bash
cd profiles/personal
vim dotfiles/.gitconfig
```

Changes take effect immediately for that profile.

### Add Tool-Specific Variables

Edit the profile's `.env` file (dotenv format, no `export` keyword):

```bash
cd profiles/personal
vim .env
```

Add tool-specific path variables and secrets:

```bash
# Tool configurations (path variables)
GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/dotfiles/.gitconfig"
NPM_CONFIG_USERCONFIG="$WORKSPACE_HOME/dotfiles/.npmrc"
DOCKER_CONFIG="$WORKSPACE_HOME/dotfiles/.docker"

# Secrets (API keys, tokens, credentials)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
GITHUB_TOKEN=ghp_your_token
```

The `.env` file is gitignored and automatically loaded by `.envrc` via `dotenv_if_exists`.

### Add direnv Commands to .envrc

For direnv stdlib commands and core variables, edit `.envrc`:

```bash
vim .envrc
```

```bash
# direnv stdlib commands go in .envrc
use node 18
layout python python3.11
PATH_add "$WORKSPACE_HOME/tools"
```

Then reload:

```bash
direnv allow
```

### Add Custom Scripts

Put executable scripts in the `bin/` directory:

```bash
cd profiles/personal
cat > bin/deploy.sh << 'EOF'
#!/bin/bash
echo "Deploying from $WORKSPACE_PROFILE..."
# Your deployment logic here
EOF

chmod +x bin/deploy.sh
```

The `bin/` directory is automatically added to your PATH, so you can run:

```bash
deploy.sh
```

### View Profile Status

Check what's loaded:

```bash
direnv status
```

View environment:

```bash
env | grep WORKSPACE
```

## Working with Projects

### Create a Workspace for an Existing Project

```bash
# Create profile for your project
profile create my-existing-project \
    --git-name "Your Name" \
    --git-email "your@email.com"
```

# Link your existing project directory
cd profiles/my-existing-project
ln -s /path/to/your/existing/project code

# Or work directly in the profile directory
cd profiles/my-existing-project
git clone https://github.com/user/repo.git
```

### Use Nested Directories

You can work in subdirectories and still have the profile active:

```
profiles/work/
├── .envrc                 # Work profile configuration
├── project-a/            # Project A inherits work profile
│   └── .envrc           # Can add project-specific variables
└── project-b/            # Project B inherits work profile
    └── .envrc           # Can add different project-specific variables
```

## Troubleshooting

### direnv not loading

**Check if direnv is hooked**:

```bash
type direnv
# Should show: direnv is a shell function
```

If not, add the hook to your shell config and reload.

**Check if .envrc is allowed**:

```bash
direnv status
```

If blocked, run:

```bash
direnv allow
```

### Git still using global config

**Check environment variable**:

```bash
echo $GIT_CONFIG_GLOBAL
```

Should show path to profile's .gitconfig.

**Verify git is reading it**:

```bash
git config --show-origin user.email
```

Should show:

```
file:/path/to/workspace-profiles/profiles/personal/dotfiles/.gitconfig
```

### Changes not taking effect

After modifying `.envrc`:

```bash
direnv allow
```

After modifying `.gitconfig`:
Changes are immediate, but verify with:

```bash
git config --show-origin --list
```

## Next Steps

1. **Read the full README**: `cat ../README.md`
2. **Explore examples**: Look in `docs/examples/` directory
3. **Customize templates**: Templates are built into the Go CLI
4. **Add more tools**: Configure AWS, Docker, Kubernetes, etc.

## Examples of Advanced Usage

### AWS Profile Integration

```bash
# In .env
AWS_PROFILE="my-profile"
AWS_DEFAULT_REGION="us-east-1"
```

### Node.js Version Management

```bash
# In .envrc (direnv stdlib command)
use node 18
```

```bash
# In .env (tool-specific path variable)
NPM_CONFIG_USERCONFIG="$WORKSPACE_HOME/dotfiles/.npmrc"
```

### Python Virtual Environment

```bash
# In .envrc (direnv stdlib command)
layout python python3.11
```

```bash
# In .env (tool-specific path variable)
PYTHONPATH="$WORKSPACE_HOME/lib"
```

### Docker Configuration

```bash
# In .env
DOCKER_CONFIG="$WORKSPACE_HOME/dotfiles/.docker"
```

### Kubernetes Context

Kubernetes configuration is automatically set up in new profiles:

```bash
# Automatically configured in .env
KUBECONFIG="$WORKSPACE_HOME/dotfiles/.kube/config"
```

To use it, simply copy or generate your kubeconfig:

```bash
# Copy existing kubeconfig
cp ~/.kube/config dotfiles/.kube/config

# Or generate from AWS EKS
aws eks update-kubeconfig --name my-cluster --region us-east-1
# The kubeconfig will be automatically saved to the profile's .kube directory
```

### XDG-Compliant Tools

Many modern CLI tools respect the XDG Base Directory specification, which is automatically configured:

```bash
# Automatically configured in .env
XDG_CONFIG_HOME="$WORKSPACE_HOME/dotfiles/.config"
```

Tools like neovim, tmux, bat, ripgrep, and many others will automatically use profile-specific configs:

```bash
# Create tool-specific configs
mkdir -p dotfiles/.config/nvim
vim dotfiles/.config/nvim/init.vim

# Or copy existing configs
cp -r ~/.config/tmux dotfiles/.config/
```

Common XDG-compliant tools:

- **Neovim**: `dotfiles/.config/nvim/`
- **Tmux**: `dotfiles/.config/tmux/`
- **Bat**: `dotfiles/.config/bat/`
- **Ripgrep**: `dotfiles/.config/ripgrep/`
- **Git** (also supports XDG): `dotfiles/.config/git/`

### SSH Agent

The `SSH_AUTH_SOCK` variable is automatically configured in new profiles, pointing to your SSH agent socket. Set this in `.env` to match your SSH agent setup:

```bash
# Example: 1Password SSH agent (macOS)
SSH_AUTH_SOCK="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"

# Example: Default ssh-agent
# SSH_AUTH_SOCK="$HOME/.ssh/agent.sock"

# Example: macOS Keychain ssh-agent
# SSH_AUTH_SOCK="$HOME/Library/Containers/com.apple.ssh-agent/Data/agent.sock"
```

When the profile is active, the configured SSH agent will automatically be used for Git operations and SSH connections.

#### 1Password SSH Agent Setup (Optional)

If you use 1Password as your SSH agent, you can configure which keys to load:

```bash
# Edit the agent configuration
vim dotfiles/.config/1Password/agent.toml

# Example configuration:
[[ssh-keys]]
vault = "Private"
item = "GitHub SSH Key"
account = "my.1password.com"

# Add multiple keys for different services
[[ssh-keys]]
vault = "Work"
item = "Work GitHub Key"
account = "my.1password.com"
```

Helpful 1Password CLI commands:

```bash
# List items in 1Password to find SSH keys
op item list

# View SSH key details
op item get "GitHub SSH Key" --vault Private
```

## Tips

1. **Use templates** - They provide good defaults
2. **Keep secrets in .env** - Never commit API keys or passwords
3. **Document your profiles** - Update the profile's README.md (in each profile directory)
4. **Use descriptive names** - Profile names should be clear and meaningful
5. **Share examples** - Use `.example` files for team collaboration

## Getting Help

- View command help: `profile create --help`
- Check direnv docs: https://direnv.net/
- Git environment variables: https://git-scm.com/docs/git-config#ENVIRONMENT
