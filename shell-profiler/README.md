# Workspace Profile Switcher

[![CI](https://github.com/neverprepared/ink-bunny/actions/workflows/ci.yml/badge.svg)](https://github.com/neverprepared/ink-bunny/actions/workflows/ci.yml)
[![Release](https://github.com/neverprepared/ink-bunny/actions/workflows/release.yml/badge.svg)](https://github.com/neverprepared/ink-bunny/actions/workflows/release.yml)
[![Go Report Card](https://goreportcard.com/badge/github.com/neverprepared/shell-profile-manager)](https://goreportcard.com/report/github.com/neverprepared/shell-profile-manager)

A terminal shell switcher using direnv to manage workspace-specific environment variables and tool configurations.

## Installation

### Homebrew (macOS/Linux)

```bash
brew install neverprepared/ink-bunny/shell-profiler
```

### From Source

```bash
git clone https://github.com/neverprepared/ink-bunny.git
cd ink-bunny/shell-profiler
make build
```

### From Releases

Download a pre-built binary from the [releases page](https://github.com/neverprepared/ink-bunny/releases) for your platform.

## Overview

This system allows you to maintain separate profiles for different workspaces, each with their own:

- Environment variables
- Git configuration
- Tool configurations
- Shell settings

When you navigate into a workspace directory, direnv automatically loads the profile's environment variables, including custom paths to dotfiles like `.gitconfig`.

## Directory Structure

```
workspace-profiles/
├── README.md
├── profiles/
│   ├── personal/
│   │   ├── .envrc              # Workspace core vars + direnv commands
│   │   ├── .env                # Tool-specific path variables
│   │   └── dotfiles/
│   │       └── .gitconfig
│   ├── work/
│   │   ├── .envrc
│   │   ├── .env
│   │   └── dotfiles/
│   │       └── .gitconfig
│   └── client-acme/
│       ├── .envrc
│       ├── .env
│       └── dotfiles/
│           └── .gitconfig
└── docs/
    └── examples/
        ├── .envrc.example
        ├── .env.example
        └── .gitconfig.example
```

## Prerequisites

1. **Install direnv**:

   ```bash
   # macOS
   brew install direnv

   # Linux (Ubuntu/Debian)
   sudo apt install direnv
   ```

2. **Hook direnv into your shell**:

   Add to `~/.bashrc` or `~/.bash_profile`:

   ```bash
   eval "$(direnv hook bash)"
   ```

   Or for `~/.zshrc`:

   ```bash
   eval "$(direnv hook zsh)"
   ```

3. **Reload your shell**:
   ```bash
   source ~/.bashrc  # or ~/.zshrc
   ```

## Quick Start

1. **Create a new workspace profile**:

   ```bash
   shell-profiler create my-project
   ```

2. **Navigate to your workspace**:

   ```bash
   cd profiles/my-project
   ```

3. **Allow direnv** (first time only):

   ```bash
   direnv allow
   ```

4. **Verify the profile is loaded**:
   ```bash
   echo $WORKSPACE_PROFILE
   echo $WORKSPACE_HOME
   ```

## How It Works

### Environment Variables

When you enter a workspace directory, direnv loads two files:

**`.envrc`** — Core workspace identity and direnv commands:

- **`WORKSPACE_PROFILE`**: Name of the current profile (e.g., "personal", "work")
- **`WORKSPACE_HOME`**: Absolute path to the workspace directory
- `PATH_add bin` and other direnv stdlib commands
- Loads `.env` via `dotenv_if_exists`

**`.env`** — Tool-specific path variables (dotenv format, no `export`):

- **`GIT_CONFIG_GLOBAL`**: Path to profile-specific `.gitconfig`
- **`GIT_SSH_COMMAND`**: SSH command with profile-specific config
- **`KUBECONFIG`**, **`AWS_CONFIG_FILE`**, **`AZURE_CONFIG_DIR`**, etc.
- Secrets and API tokens

### Git Configuration

Each profile has its own `.gitconfig` file. When the profile is active, git uses this custom configuration via the `GIT_CONFIG_GLOBAL` environment variable.

This allows you to have different:

- User names and emails
- GPG signing keys
- Aliases and core settings
- Remote URLs and credentials

### Tool Integration

Profiles ship with built-in support for the following tools:

- **Git**: `GIT_CONFIG_GLOBAL`, `GIT_SSH_COMMAND` for identity and SSH isolation
- **SSH**: `SSH_AUTH_SOCK` for agent socket, profile-specific `known_hosts`
- **XDG**: `XDG_CONFIG_HOME` for XDG-compliant tools (neovim, tmux, bat, ripgrep)
- **Kubernetes**: `KUBECONFIG` for cluster configuration
- **AWS**: `AWS_PROFILE`, `AWS_CONFIG_FILE`, `AWS_SHARED_CREDENTIALS_FILE`
- **Google Cloud**: `CLOUDSDK_CONFIG`, `GOOGLE_APPLICATION_CREDENTIALS`
- **Azure**: `AZURE_CONFIG_DIR`
- **Docker**: `DOCKER_CONFIG`

The same pattern extends to any tool that reads environment variables. See `docs/examples/.env.example` for the full list of supported variables.

> **We welcome pull requests** that add first-class support for additional tools and ecosystems. If you configure a tool via environment variables in your own profiles, consider contributing it back so others can benefit.

## Creating a New Profile

### Manual Method

1. Create profile directory:

   ```bash
   mkdir -p profiles/my-profile/dotfiles
   ```

2. Create `.envrc`:

   ```bash
   cat > profiles/my-profile/.envrc << 'EOF'
   # Set workspace identification
   export WORKSPACE_PROFILE="my-profile"
   export WORKSPACE_HOME="$PWD"

   # Add custom bin directory to PATH
   PATH_add bin

   # Load tool-specific variables from .env
   dotenv_if_exists .env
   EOF
   ```

3. Create `.env` (tool-specific path variables):

   ```bash
   cat > profiles/my-profile/.env << 'EOF'
   GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/dotfiles/.gitconfig"
   GIT_SSH_COMMAND="ssh -F $WORKSPACE_HOME/dotfiles/.ssh/config"
   XDG_CONFIG_HOME="$WORKSPACE_HOME/dotfiles/.config"
   EOF
   ```

4. Create `.gitconfig`:

   ```bash
   cat > profiles/my-profile/dotfiles/.gitconfig << 'EOF'
   [user]
       name = Your Name
       email = your.email@example.com

   [core]
       editor = vim

   [init]
       defaultBranch = main
   EOF
   ```

5. Allow direnv:
   ```bash
   cd profiles/my-profile
   direnv allow
   ```

### Using the Helper Script

```bash
shell-profiler create my-profile
cd profiles/my-profile
# Edit dotfiles/.gitconfig as needed
direnv allow
```

## Usage Examples

### Switching Between Work and Personal Projects

```bash
# Work on personal project
cd ~/workspaces/build/profiles/personal
# Git now uses personal email: personal@example.com

# Switch to work project
cd ~/workspaces/build/profiles/work
# Git now uses work email: work@company.com
```

### Verifying Active Profile

```bash
# Check which profile is active
echo "Profile: $WORKSPACE_PROFILE"
echo "Home: $WORKSPACE_HOME"

# Verify git configuration
git config user.email
git config user.name
```

### Multiple Client Workspaces

Create separate profiles for different clients, each with their own git configuration, SSH keys, and credentials:

```bash
shell-profiler create client-acme
shell-profiler create client-globex
shell-profiler create client-initech
```

## Advanced Configuration

### Custom direnv Functions

Create `~/.config/direnv/direnvrc` to add reusable functions:

```bash
# Load a profile by name
use_workspace_profile() {
    local profile_name=$1
    export WORKSPACE_PROFILE="$profile_name"
    export WORKSPACE_HOME="$(pwd)"

    # Load tool-specific variables from .env
    dotenv_if_exists .env
}
```

Then in your `.envrc`:

```bash
use_workspace_profile "client-acme"
```

Tool-specific variables (git, SSH, AWS, etc.) are managed in the `.env` file rather than `.envrc`.

### Nested Workspaces

You can nest `.envrc` files. Child directories inherit parent environment variables and can override them:

```
profiles/work/
├── .envrc                    # Work profile base
└── projects/
    ├── project-a/
    │   └── .envrc           # Inherits work, adds project-specific vars
    └── project-b/
        └── .envrc           # Inherits work, adds project-specific vars
```

### Security Considerations

1. **Never commit `.envrc` files with secrets** - use `.env` files that are gitignored
2. **Review `.envrc` files before allowing** - direnv shows you what will be executed
3. **Use `.envrc.example`** - commit templates, not actual configurations
4. **Revoke access when needed**: `direnv deny`

## Troubleshooting

### direnv not loading

- Check if hook is added to shell config: `type direnv`
- Verify `.envrc` is allowed: `direnv status`
- Re-allow: `direnv allow .`

### Git still using global config

- Check environment variable: `echo $GIT_CONFIG_GLOBAL`
- Verify file exists: `ls -la $GIT_CONFIG_GLOBAL`
- Test git config: `git config --show-origin user.email`

### Environment variables not persisting

- direnv only affects the current shell session
- Child processes inherit the environment
- Opening a new terminal requires re-entering the directory

## Contributing

This project was built with Go, direnv, and standard Unix tooling. We encourage contributions that:

- Add support for new tools and ecosystems (language runtimes, cloud providers, databases, etc.)
- Improve profile templates and example configurations
- Fix bugs or improve documentation

Pull requests are welcome. See `CLAUDE.md` for development guidelines and `docs/examples/` for the current set of tool integrations.

## References

- [direnv Documentation](https://direnv.net/)
- [Git Environment Variables](https://git-scm.com/docs/git-config#ENVIRONMENT)
- [direnv Stdlib](https://direnv.net/man/direnv-stdlib.1.html)
