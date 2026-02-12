# Getting Started with Workspace Profile Switcher

**Complete setup in under 5 minutes!**

## What You've Got

A complete terminal shell switcher system that:

- ✅ Automatically switches environments when you `cd` into directories
- ✅ Manages separate git identities (name, email, GPG keys) per workspace
- ✅ Isolates credentials and secrets per project
- ✅ Supports any tool that uses environment variables
- ✅ Works with bash, zsh, fish, and other shells

## Prerequisites Check

Before starting, install direnv:

```bash
# macOS
brew install direnv

# Ubuntu/Debian
sudo apt install direnv

# Fedora/RHEL
sudo dnf install direnv

# Arch Linux
sudo pacman -S direnv
```

## Step 1: Hook direnv (ONE TIME ONLY)

Add this line to your shell configuration file:

**For Bash** (add to `~/.bashrc` or `~/.bash_profile`):

```bash
eval "$(direnv hook bash)"
```

**For Zsh** (add to `~/.zshrc`):

```bash
eval "$(direnv hook zsh)"
```

**For Fish** (add to `~/.config/fish/config.fish`):

```fish
direnv hook fish | source
```

Then reload your shell:

```bash
source ~/.bashrc  # or ~/.zshrc
# OR
exec $SHELL
```

Verify direnv is hooked:

```bash
type direnv
# Should output: direnv is a shell function
```

## Step 2: Explore What's Already Created

Three example profiles are ready to use:

```bash
# View all profiles
./profile list

# See detailed information
./profile list --verbose
```

You'll see:

- `personal` - Personal projects profile
- `work` - Work projects profile
- `client-acme` - Client projects profile

## Step 3: Try It Out

### Activate the Personal Profile

```bash
# Navigate to the personal profile
cd profiles/personal

# Allow direnv (REQUIRED - first time only)
direnv allow
```

You'll see output like:

```
direnv: loading ~/workspace-profiles/profiles/personal/.envrc
direnv: export +GIT_CONFIG_GLOBAL +WORKSPACE_HOME +WORKSPACE_PROFILE ~PATH
```

### Verify It's Working

```bash
# Check environment variables
echo $WORKSPACE_PROFILE
# Output: personal

# Check git configuration
git config user.name
# Output: Personal User

git config user.email
# Output: personal@example.com
```

### Switch to Work Profile

```bash
# Navigate to work profile
cd ../work

# Allow direnv (first time only)
direnv allow

# Check the new environment
echo $WORKSPACE_PROFILE
# Output: work

git config user.email
# Output: work@company.com
```

**That's it! The environment automatically switched!**

## Step 4: Create Your Own Profile

### Option A: Interactive Creation (Recommended)

```bash
# Navigate back to root
cd ../..

# Create a new profile interactively
./profile create my-project --interactive
```

Follow the prompts to configure your profile.

### Option B: Quick Creation

```bash
./profile create my-project \
    --template personal \
    --git-name "Your Name" \
    --git-email "your@email.com"
```

### Option C: Work Profile with Full Config

```bash
./profile create my-work-project \
    --template work \
    --git-name "Work Name" \
    --git-email "work@company.com"
```

## Step 5: Customize Your Profile

Navigate to your new profile:

```bash
cd profiles/my-project
direnv allow
```

### Add Tool-Specific Variables

Edit the `.env` file (dotenv format, no `export` keyword):

```bash
vim .env
```

Add tool-specific path variables and secrets:

```bash
# Tool configurations (path variables)
GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/dotfiles/.gitconfig"
NPM_CONFIG_USERCONFIG="$WORKSPACE_HOME/dotfiles/.npmrc"
DOCKER_CONFIG="$WORKSPACE_HOME/dotfiles/.docker"

# Secrets (API keys, tokens, credentials)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=secret...
GITHUB_TOKEN=ghp_...
API_KEY=secret-key
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

Save and reload:

```bash
direnv allow
```

### Customize Git Config

Edit git configuration:

```bash
vim dotfiles/.gitconfig
```

Add your preferences:

```ini
[user]
    name = Your Name
    email = your@email.com
    signingkey = YOUR_GPG_KEY  # if using GPG

[commit]
    gpgsign = true  # if using GPG signing

[alias]
    # Add your custom aliases
    co = checkout
    br = branch
    st = status
    # etc.
```

Changes take effect immediately!

### Add Custom Scripts

Put scripts in the `bin/` directory:

```bash
cat > bin/deploy.sh << 'EOF'
#!/bin/bash
echo "Deploying $WORKSPACE_PROFILE..."
# Your deployment commands here
EOF

chmod +x bin/deploy.sh
```

The `bin/` directory is automatically in your PATH, so you can run:

```bash
deploy.sh
```

## Common Workflows

### Working on Multiple Client Projects

```bash
# Create client profiles
./profile create client-alpha --template client --git-email "dev@alpha.com"
./profile create client-beta --template client --git-email "dev@beta.com"

# Switch between them
cd profiles/client-alpha  # Uses dev@alpha.com
cd ../client-beta         # Uses dev@beta.com
```

### Personal vs Work Separation

```bash
# Morning: Work on company projects
cd profiles/work
git clone https://github.com/company/repo.git
cd repo
git commit -m "Work commit"  # Commits as work@company.com

# Evening: Work on personal projects
cd ../../profiles/personal
git clone https://github.com/me/my-project.git
cd my-project
git commit -m "Personal commit"  # Commits as personal@example.com
```

### Multi-Cloud Development

```bash
# Create cloud-specific profiles
./profile create aws-dev
./profile create azure-dev
./profile create gcp-dev

# In each profile's .env, add:
# AWS profile
AWS_PROFILE="my-aws-profile"
AWS_DEFAULT_REGION="us-east-1"

# Azure profile
AZURE_CONFIG_DIR="$WORKSPACE_HOME/dotfiles/.azure"

# GCP profile
CLOUDSDK_CONFIG="$WORKSPACE_HOME/dotfiles/.config/gcloud"
```

## Essential Commands

```bash
# Create new profile
./profile create <name> [options]

# List all profiles
./profile list

# List with details
./profile list --verbose

# Show current profile info
./profile info

# Show direnv status
./profile status

# Delete a profile
./profile delete <name>

# Get help
./profile help
```

## Understanding the Files

### `.envrc` - Core Workspace Identity & direnv Commands

Contains workspace identification and direnv stdlib commands that run when you enter the directory.

**Example:**

```bash
export WORKSPACE_PROFILE="my-project"
export WORKSPACE_HOME="$PWD"
PATH_add bin
dotenv_if_exists .env
```

### `.env` - Tool-Specific Variables & Secrets (Gitignored)

Tool-specific path variables and secret values in dotenv format (no `export` keyword). Automatically loaded by `.envrc` via `dotenv_if_exists`.

**Example:**

```bash
# Tool configurations
GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/dotfiles/.gitconfig"
DOCKER_CONFIG="$WORKSPACE_HOME/dotfiles/.docker"
KUBECONFIG="$WORKSPACE_HOME/dotfiles/.kube/config"

# Secrets
AWS_ACCESS_KEY_ID=AKIA...
API_KEY=secret-key
```

### `dotfiles/.gitconfig` - Git Configuration

Your git settings for this profile.

**Example:**

```ini
[user]
    name = Your Name
    email = your@email.com
```

### `bin/` - Custom Scripts

Executable scripts automatically added to your PATH.

## Troubleshooting

### "direnv: error .envrc is blocked"

**Solution:** You need to allow direnv to load the file:

```bash
direnv allow
```

### Git still using global config

**Solution:**

1. Check environment: `echo $GIT_CONFIG_GLOBAL`
2. Re-allow direnv: `direnv allow`
3. Verify: `git config --show-origin user.email`

### Environment not loading

**Solution:**

1. Check direnv status: `direnv status`
2. Ensure hook is installed: `type direnv`
3. Re-allow: `direnv allow`

### Scripts in bin/ not found

**Solution:**

1. Ensure scripts are executable: `chmod +x bin/*`
2. Re-allow direnv: `direnv allow`
3. Check PATH: `echo $PATH | grep bin`

## Next Steps

### Learn More

- **Full Documentation**: Read [README.md](../README.md)
- **Installation Details**: Read [INSTALL.md](INSTALL.md)
- **Quick Reference**: Read [QUICKSTART.md](QUICKSTART.md)
- **Project Overview**: Read [PROJECT-SUMMARY.md](PROJECT-SUMMARY.md)

### Extend Your Setup

1. Configure AWS, Docker, Kubernetes in `.env` (tool-specific path variables)
2. Add language-specific direnv commands in `.envrc` (`use node`, `layout python`, etc.)
3. Create custom direnv functions in `~/.config/direnv/direnvrc`

### Share with Team

1. Commit `.envrc.example` and `.gitconfig.example` files
2. Add `.env.example` templates
3. Document team-specific setup in profile README
4. Share the workspace-profiles directory (without .env files)

## Pro Tips

1. **Use templates** - Start with `--template` to get good defaults
2. **Keep secrets in .env** - Never commit API keys or passwords
3. **One profile per client** - Isolate credentials and identities
4. **Use descriptive names** - `client-acme` not `proj1`
5. **Review before allowing** - direnv shows what will execute
6. **Update regularly** - Keep git configs current
7. **Backup profiles** - They're just directories - tar them up!

## Safety & Security

✅ **Secrets are isolated** - Each profile has separate credentials
✅ **Explicit approval** - direnv requires manual `allow`
✅ **No cross-contamination** - Environments don't leak
✅ **Git tracked safely** - Secrets are gitignored
✅ **Auditable** - All configs are in plain text files

## Summary

You now have:

- ✅ Automatic environment switching
- ✅ Separate git identities per workspace
- ✅ Isolated credentials and secrets
- ✅ Extensible configuration system
- ✅ Three example profiles ready to use

**Total setup time: ~5 minutes**
**Total profiles created: 3 examples + yours**
**Total magic: Infinite! 🎉**

Ready to start? Pick a profile and run `direnv allow`!
