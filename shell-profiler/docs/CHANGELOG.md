# Workspace Profile Switcher - Changelog

## [Unreleased]

### Changed

- **`.envrc`/`.env` Split**: Restructured profile creation to separate concerns between `.envrc` and `.env`
  - `.envrc` now contains only core workspace identity (`WORKSPACE_PROFILE`, `WORKSPACE_HOME`) and direnv stdlib commands (`PATH_add`, `dotenv_if_exists`)
  - `.env` now contains all tool-specific path variables (`GIT_CONFIG_GLOBAL`, `GIT_SSH_COMMAND`, `KUBECONFIG`, `AWS_CONFIG_FILE`, `XDG_CONFIG_HOME`, `SSH_AUTH_SOCK`, etc.)
  - `.env` uses dotenv format (no `export` keyword) and is loaded automatically via `dotenv_if_exists .env`
  - Updated `create` and `update` commands to generate the new split structure
  - Updated all documentation (README, QUICKSTART, GETTING-STARTED, PROJECT-SUMMARY)
  - Updated example files (`.envrc.example`, new `.env.example`)

### Added

- **XDG Base Directory Support**: Automatically configured XDG_CONFIG_HOME in new profiles

  - `XDG_CONFIG_HOME` environment variable now automatically set to `$WORKSPACE_HOME/dotfiles/.config`
  - XDG-compliant tools (neovim, tmux, bat, ripgrep, etc.) now use profile-specific configs
  - Updated QUICKSTART.md with XDG configuration steps and common tool examples
  - Added `.config` directory creation to profile creation

- **1Password SSH Agent Configuration**: Automatically configured in all profiles

  - `SSH_AUTH_SOCK` environment variable now automatically set to 1Password agent socket
  - Profile-specific 1Password agent configuration at `dotfiles/.config/1Password/agent.toml`
  - Template includes SSH keys configuration examples and CLI setup
  - Proper file permissions (600) set automatically
  - Updated QUICKSTART.md with 1Password SSH agent configuration steps
  - Added to profile creation for seamless integration

- **Kubernetes Configuration**: Automatically configured KUBECONFIG in new profiles

  - `KUBECONFIG` environment variable now automatically set to `$WORKSPACE_HOME/dotfiles/.kube/config`
  - Updated README with Kubernetes configuration steps
  - Added examples for copying/generating kubeconfig files

- **Update Command Integration**: Added `update` command to main profile CLI

  - New `./profile update <name>` command for updating existing profiles
  - Supports `--dry-run`, `--force`, and `--no-backup` options
  - Automatically adds missing environment variables and directories to existing profiles

- **Terraform and Terragrunt Support Removed**: Simplified profile configuration
  - Removed all `TF_*` and `TG_*` environment variables from profile templates
  - Removed `.terraform.d/plugin-cache` and `.terragrunt-cache` directory creation
  - Removed Terraform configuration file (`.terraformrc`) generation
  - Removed Terragrunt configuration file (`.terragrunt-config.hcl`) generation
  - Users who need Terraform/Terragrunt can manually add configuration to their profiles
  - This simplifies the default profile setup and reduces complexity

## [1.2.0] - AWS, Terraform, and Terragrunt Support

### Added

- **AWS CLI Configuration Isolation**: Every profile can now have isolated AWS configurations

  - Profile-specific AWS config at `dotfiles/.aws/config`
  - Profile-specific AWS credentials at `dotfiles/.aws/credentials` (gitignored)
  - Environment variables: `AWS_CONFIG_FILE`, `AWS_SHARED_CREDENTIALS_FILE`, `AWS_PROFILE`
  - Example configuration: `docs/examples/.aws-config.example` with SSO, role assumption, multi-region patterns

- **Terraform Configuration Isolation**: Profile-specific Terraform configurations

  - Profile-specific Terraform CLI config at `dotfiles/.terraformrc`
  - Profile-specific plugin cache at `.terraform.d/plugin-cache/`
  - Environment variables: `TF_CLI_CONFIG_FILE`, `TF_DATA_DIR`, `TF_PLUGIN_CACHE_DIR`
  - Example configuration: `docs/examples/.terraformrc.example` with plugin cache and credentials

- **Terragrunt Configuration Isolation**: Profile-specific Terragrunt cache and settings

  - Profile-specific Terragrunt cache at `.terragrunt-cache/`
  - Environment variables: `TERRAGRUNT_DOWNLOAD`, `TERRAGRUNT_SOURCE_UPDATE`
  - Example configuration: `docs/examples/.terragrunt-config.example` with environment variables and patterns

- **Kubernetes Configuration Support**: Added directory structure

  - Profile-specific kubeconfig directory at `dotfiles/.kube/`
  - Environment variable: `KUBECONFIG` (example in `.envrc.example`)

- **Enhanced .gitignore**: Added comprehensive patterns for:

  - AWS credentials and cache files
  - Terraform state files, variables, and cache directories
  - Terragrunt cache directories and plan files
  - Kubernetes cache files

- **Directory Structure Updates**:
  - Profile creation now creates: `dotfiles/.aws/`, `dotfiles/.kube/`, `.terraform.d/plugin-cache/`, `.terragrunt-cache/`
  - All three example profiles regenerated with new directory structure

### Updated

- `docs/examples/.envrc.example`: Added commented examples for AWS, Terraform, Terragrunt, and Kubernetes environment variables

## [1.1.1] - SSH Configuration Path Fix

### Fixed

- **WORKSPACE_HOME Path Issue**: Changed from `$(pwd)` to `$PWD` in `.envrc`
  - `$(pwd)` was evaluated at direnv load time, causing incorrect path resolution
  - `$PWD` is a shell variable that direnv evaluates correctly
  - SSH config now properly resolves to `$WORKSPACE_HOME/dotfiles/.ssh/config`
  - All three example profiles regenerated with fix

## [1.1.0] - SSH Configuration Support

### Added

- **SSH Configuration Isolation**: Every profile now has its own SSH configuration

  - Profile-specific SSH config at `dotfiles/.ssh/config`
  - Profile-specific known_hosts at `dotfiles/.ssh/known_hosts`
  - Proper permissions set automatically (700 for .ssh directory, 600 for config files)

- **SSH Wrapper Function**: Added to every `.envrc` file

  - `ssh()` function that uses `ssh -F $WORKSPACE_HOME/dotfiles/.ssh/config`
  - Ensures user's `$HOME/.ssh/config` is never used when profile is active
  - Function is exported with `export -f ssh` for availability in subshells

- **GIT_SSH_COMMAND**: Environment variable set in `.envrc`

  - Ensures git operations use profile-specific SSH config
  - Works seamlessly with git clone, push, pull, fetch operations

- **Comprehensive SSH Examples**: Created `docs/examples/.ssh-config.example`
  - Git hosting services (GitHub, GitLab, Bitbucket)
  - Development servers
  - Jump host/bastion configurations
  - Cloud provider examples (AWS, GCP, Azure)
  - Port forwarding examples
  - Security best practices

### Modified

- **Profile creation**: Updated to create SSH infrastructure

  - Creates `dotfiles/.ssh/` directory with proper permissions
  - Generates SSH config file with examples
  - Creates empty known_hosts file
  - Updates `.gitignore` to protect SSH keys while keeping config template
  - Adds SSH configuration instructions to profile README

- **docs/examples/.envrc.example**: Enhanced with SSH configuration section
  - Added `GIT_SSH_COMMAND` export
  - Added `ssh()` wrapper function with detailed comments
  - Added commented examples for `scp()` and `sftp()` wrappers

### Regenerated

- All three example profiles recreated with SSH support:
  - `profiles/personal` - Personal User <personal@example.com>
  - `profiles/work` - Work User <work@company.com>
  - `profiles/client-acme` - ACME Developer <dev@acmecorp.com>

### Security

- SSH private keys are gitignored (patterns: `id_*`, `*.pem`, `*.key`)
- SSH config template is tracked in git (safe, contains no secrets)
- known_hosts file is gitignored (contains server fingerprints)
- Proper file permissions enforced (700/600)

## [1.0.0] - Initial Release

### Features

- Automatic environment switching with direnv
- Separate git identities per workspace
- Profile templates (personal, work, client, basic)
- Environment variable isolation
- Custom script support via bin/ directories
- Secrets management with .env files
- Comprehensive documentation

### Components

- Main CLI: `./profile` command
- CLI commands: create, list, delete, info, status, git
- Three example profiles
- Complete documentation set (README, QUICKSTART, INSTALL, etc.)
- Configuration templates

### Integration

- direnv for automatic environment loading
- Git configuration via GIT_CONFIG_GLOBAL
- Path management via PATH_add
- Shell hook support (bash, zsh, fish)
