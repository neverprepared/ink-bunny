package commands

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"time"

	"github.com/neverprepared/shell-profile-manager/internal/templates"
	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type CreateOptions struct {
	ProfileName string
	Template    string
	GitName     string
	GitEmail    string
	Force       bool
	Interactive bool
	DryRun      bool
	InitGit     bool
	GitRemote   string
}

func CreateProfile(profilesDir string, opts CreateOptions) error {
	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// Validate profile name
	if opts.ProfileName == "" {
		return fmt.Errorf("profile name is required")
	}

	matched, err := regexp.MatchString(`^[a-zA-Z0-9_-]+$`, opts.ProfileName)
	if err != nil {
		return fmt.Errorf("failed to validate profile name: %w", err)
	}
	if !matched {
		return fmt.Errorf("profile name can only contain letters, numbers, hyphens, and underscores")
	}

	// Validate template
	validTemplates := map[string]bool{
		"basic": true, "personal": true, "work": true, "client": true,
	}
	if !validTemplates[opts.Template] {
		return fmt.Errorf("invalid template: %s (must be: basic, personal, work, or client)", opts.Template)
	}

	// Check if profile exists
	if _, err := os.Stat(profileDir); err == nil && !opts.Force {
		return fmt.Errorf("profile '%s' already exists at: %s (use --force to overwrite)", opts.ProfileName, profileDir)
	}

	// Interactive mode
	if opts.Interactive {
		if err := interactiveSetup(&opts); err != nil {
			return err
		}
	}

	// Dry run
	if opts.DryRun {
		ui.PrintInfo("DRY RUN - Nothing will be created")
		fmt.Println()
		fmt.Println("Would create:")
		fmt.Printf("  Profile directory: %s\n", profileDir)
		fmt.Printf("  .envrc file with WORKSPACE_PROFILE=%s\n", opts.ProfileName)
		fmt.Printf("  .gitconfig with template: %s\n", opts.Template)
		if opts.GitName != "" {
			fmt.Printf("  Git user.name: %s\n", opts.GitName)
		}
		if opts.GitEmail != "" {
			fmt.Printf("  Git user.email: %s\n", opts.GitEmail)
		}
		return nil
	}

	// Create profile
	ui.PrintInfo(fmt.Sprintf("Creating profile: %s (template: %s)", opts.ProfileName, opts.Template))

	// Create directories
	dirs := []string{
		".config/1Password",
		".config/claude",
		".config/gemini",
		".ssh",
		".aws",
		".azure",
		".gcloud",
		".kube",
		"bin",
		"code",
	}

	for _, dir := range dirs {
		fullPath := filepath.Join(profileDir, dir)
		if err := os.MkdirAll(fullPath, 0755); err != nil {
			return fmt.Errorf("failed to create directory %s: %w", fullPath, err)
		}
	}

	// Set SSH directory permissions
	sshDir := filepath.Join(profileDir, ".ssh")
	if err := os.Chmod(sshDir, 0700); err != nil {
		return fmt.Errorf("failed to set SSH directory permissions: %w", err)
	}

	// Create .envrc
	if err := createEnvrc(profileDir, opts); err != nil {
		return fmt.Errorf("failed to create .envrc: %w", err)
	}

	// Create .env with tool-specific environment variables
	if err := createEnvFile(profileDir, opts); err != nil {
		return fmt.Errorf("failed to create .env: %w", err)
	}

	// Create .gitconfig
	if err := createGitconfig(profileDir, opts); err != nil {
		return fmt.Errorf("failed to create .gitconfig: %w", err)
	}

	// Create SSH config (only if it doesn't exist)
	if err := createSSHConfig(profileDir, opts); err != nil {
		return fmt.Errorf("failed to create SSH config: %w", err)
	}

	// Create known_hosts
	knownHostsPath := filepath.Join(profileDir, ".ssh/known_hosts")
	if _, err := os.Stat(knownHostsPath); os.IsNotExist(err) {
		if err := os.WriteFile(knownHostsPath, []byte{}, 0600); err != nil {
			return fmt.Errorf("failed to create known_hosts: %w", err)
		}
	}

	// Create 1Password config
	if err := create1PasswordConfig(profileDir, opts); err != nil {
		return fmt.Errorf("failed to create 1Password config: %w", err)
	}

	// Create SSH wrapper
	if err := createSSHWrapper(profileDir); err != nil {
		return fmt.Errorf("failed to create SSH wrapper: %w", err)
	}

	// Create .gitignore
	if err := createGitignore(profileDir); err != nil {
		return fmt.Errorf("failed to create .gitignore: %w", err)
	}

	// Create README
	if err := createREADME(profileDir, opts); err != nil {
		return fmt.Errorf("failed to create README: %w", err)
	}

	// Create .env.example
	if err := createEnvExample(profileDir); err != nil {
		return fmt.Errorf("failed to create .env.example: %w", err)
	}

	// Initialize git if requested
	if opts.InitGit {
		gitOpts := GitOptions{
			ProfileName: opts.ProfileName,
			Remote:      opts.GitRemote,
		}
		if err := InitGit(profilesDir, gitOpts); err != nil {
			ui.PrintWarning(fmt.Sprintf("Failed to initialize git: %v", err))
		}
	}

	ui.PrintSuccess(fmt.Sprintf("Profile created successfully: %s", opts.ProfileName))
	fmt.Println()
	ui.PrintInfo("Next steps:")
	fmt.Printf("  1. cd %s\n", profileDir)
	fmt.Println("  2. direnv allow")
	fmt.Println("  3. Edit .gitconfig as needed")
	fmt.Printf("  4. echo $WORKSPACE_PROFILE to verify\n")
	fmt.Println()
	ui.PrintInfo(fmt.Sprintf("Profile location: %s", profileDir))

	return nil
}

func interactiveSetup(opts *CreateOptions) error {
	// Template selection
	template, err := ui.SelectTemplate()
	if err != nil {
		return fmt.Errorf("failed to select template: %w", err)
	}
	opts.Template = template

	// Git configuration
	gitName, err := ui.Input("Git user name (press Enter to skip):", "")
	if err != nil {
		return fmt.Errorf("failed to get git name: %w", err)
	}
	if gitName != "" {
		opts.GitName = gitName
	}

	gitEmail, err := ui.Input("Git user email (press Enter to skip):", "")
	if err != nil {
		return fmt.Errorf("failed to get git email: %w", err)
	}
	if gitEmail != "" {
		opts.GitEmail = gitEmail
	}

	// Ask about git initialization
	initGit, err := ui.Confirm("Initialize git repository after creation?", false)
	if err != nil {
		return fmt.Errorf("failed to get git init preference: %w", err)
	}
	opts.InitGit = initGit

	if opts.InitGit {
		remote, err := ui.Input("Git remote URL (press Enter to skip):", "")
		if err != nil {
			return fmt.Errorf("failed to get git remote: %w", err)
		}
		if remote != "" {
			opts.GitRemote = remote
		}
	}

	return nil
}

func createEnvrc(profileDir string, opts CreateOptions) error {
	ui.PrintInfo("Creating .envrc...")

	envrcContent, err := templates.RenderEnvrc(opts.ProfileName, opts.Template)
	if err != nil {
		return fmt.Errorf("failed to render .envrc template: %w", err)
	}

	envrcPath := filepath.Join(profileDir, ".envrc")
	return os.WriteFile(envrcPath, []byte(envrcContent), 0644)
}

func createEnvFile(profileDir string, opts CreateOptions) error {
	ui.PrintInfo("Creating .env...")

	envContent, err := templates.RenderEnv(opts.ProfileName, opts.Template)
	if err != nil {
		return fmt.Errorf("failed to render .env template: %w", err)
	}

	envPath := filepath.Join(profileDir, ".env")
	return os.WriteFile(envPath, []byte(envContent), 0644)
}

func createGitconfig(profileDir string, opts CreateOptions) error {
	ui.PrintInfo("Creating .gitconfig...")

	gitconfigContent, err := templates.RenderGitconfig(opts.ProfileName, opts.Template, opts.GitName, opts.GitEmail)
	if err != nil {
		return fmt.Errorf("failed to render .gitconfig template: %w", err)
	}

	gitconfigPath := filepath.Join(profileDir, ".gitconfig")
	return os.WriteFile(gitconfigPath, []byte(gitconfigContent), 0644)
}

func createSSHConfig(profileDir string, opts CreateOptions) error {
	sshConfigPath := filepath.Join(profileDir, ".ssh/config")

	// Check if .ssh/config already exists - if so, skip creation
	if _, err := os.Stat(sshConfigPath); err == nil {
		ui.PrintWarning("SSH config already exists, skipping creation")
		return nil
	}

	ui.PrintInfo("Creating SSH config...")
	profileAbsPath, err := filepath.Abs(profileDir)
	if err != nil {
		return fmt.Errorf("failed to get absolute path: %w", err)
	}

	sshConfigContent := fmt.Sprintf(`# SSH configuration for workspace profile: %s
# This config is used instead of ~/.ssh/config when this profile is active
#
# Note: SSH config files don't support environment variable expansion.
# All paths are absolute paths to ensure they work regardless of current directory.

# Default settings for all hosts
Host *
    # Use workspace-specific known_hosts file
    UserKnownHostsFile %s/.ssh/known_hosts

    # Security settings
    AddKeysToAgent yes
    IdentitiesOnly yes

    # 1Password SSH Agent (commented out by default)
    # IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"

    # Connection settings
    ServerAliveInterval 60
    ServerAliveCountMax 3

    # Compression
    Compression yes

# Example: GitHub with profile-specific key
# Host github.com
#     HostName github.com
#     User git
#     IdentityFile %s/.ssh/id_ed25519_github
#     IdentitiesOnly yes

# Example: GitLab with profile-specific key
# Host gitlab.com
#     HostName gitlab.com
#     User git
#     IdentityFile %s/.ssh/id_ed25519_gitlab
#     IdentitiesOnly yes

# Example: Personal server
# Host myserver
#     HostName example.com
#     User myuser
#     Port 22
#     IdentityFile %s/.ssh/id_ed25519_server

# Example: Jump host (bastion)
# Host bastion
#     HostName bastion.example.com
#     User admin
#     IdentityFile %s/.ssh/id_ed25519_bastion
#
# Host internal-server
#     HostName internal.example.com
#     User admin
#     ProxyJump bastion
#     IdentityFile %s/.ssh/id_ed25519_internal
`, opts.ProfileName, profileAbsPath, profileAbsPath, profileAbsPath, profileAbsPath, profileAbsPath, profileAbsPath)

	if err := os.WriteFile(sshConfigPath, []byte(sshConfigContent), 0600); err != nil {
		return err
	}

	ui.PrintSuccess("Created SSH config")
	return nil
}

func create1PasswordConfig(profileDir string, opts CreateOptions) error {
	ui.PrintInfo("Creating 1Password agent configuration...")

	configContent := fmt.Sprintf(`# 1Password SSH Agent configuration for workspace profile: %s
# This config is used when this profile is active

# SSH Agent configuration
[[ssh-keys]]
# Example: Add your SSH keys from 1Password
# vault = "Private"
# item = "GitHub SSH Key"
# account = "my.1password.com"

# Multiple keys can be configured
# [[ssh-keys]]
# vault = "Work"
# item = "Work GitHub Key"

# CLI configuration
# [cli]
# Uncomment to configure CLI authentication
# account = "my.1password.com"

# Notes:
# - SSH keys stored in 1Password can be used for Git operations
# - The SSH agent will automatically load keys when profile is active
# - Use 'op item list' to find vault and item names
# - See: https://developer.1password.com/docs/ssh/agent/
`, opts.ProfileName)

	configPath := filepath.Join(profileDir, ".config/1Password/agent.toml")
	return os.WriteFile(configPath, []byte(configContent), 0600)
}

func createSSHWrapper(profileDir string) error {
	ui.PrintInfo("Creating SSH wrapper script...")

	wrapperContent := `#!/usr/bin/env bash
# SSH wrapper that uses workspace-specific SSH config
# This script is in PATH before system ssh, ensuring profile isolation

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_HOME="$(dirname "$SCRIPT_DIR")"

# Use workspace-specific SSH config
exec /usr/bin/ssh -F "$WORKSPACE_HOME/.ssh/config" "$@"
`

	wrapperPath := filepath.Join(profileDir, "bin/ssh")
	if err := os.WriteFile(wrapperPath, []byte(wrapperContent), 0755); err != nil {
		return err
	}

	return nil
}

func createGitignore(profileDir string) error {
	ui.PrintInfo("Creating .gitignore...")

	gitignoreContent := `# Workspace profile gitignore

# Environment files with secrets
.env
.envrc.local

# SSH keys and sensitive files
.ssh/id_*
.ssh/*.pem
.ssh/*.key
.ssh/known_hosts

# AWS credentials and sensitive config
.aws/credentials
.aws/cli/cache
.aws/sso/cache

# Azure CLI credentials and sensitive config
.azure/config
.azure/clouds.config
.azure/accessTokens.json
.azure/msal_token_cache.json
.azure/azureProfile.json

# Google Cloud SDK credentials and sensitive config
.gcloud/configurations/
.gcloud/credentials
.gcloud/access_tokens.db
.gcloud/legacy_credentials/
.gcloud/logs/

# Claude Code configuration (may contain API keys and sensitive data)
.config/claude/

# Gemini CLI configuration (may contain API keys and sensitive data)
.config/gemini/

# Terraform
.terraform/
.terraform.lock.hcl
*.tfstate
*.tfstate.*
*.tfvars
.terraform.d/plugin-cache/
.terraform.d/checkpoint_cache
.terraform.d/checkpoint_signature

# Terragrunt
.terragrunt-cache/
*.tfplan

# Kubernetes
.kube/cache
.kube/http-cache

# OS files
.DS_Store
Thumbs.db

# Editor files
.vscode/
.idea/
*.swp
*.swo
*~

# Build artifacts
bin/
dist/
build/
*.log
`

	gitignorePath := filepath.Join(profileDir, ".gitignore")
	return os.WriteFile(gitignorePath, []byte(gitignoreContent), 0644)
}

func createREADME(profileDir string, opts CreateOptions) error {
	ui.PrintInfo("Creating README.md...")

	created := time.Now().UTC().Format("2006-01-02 15:04:05 UTC")
	homeDir, err := os.UserHomeDir()
	if err != nil {
		homeDir = "" // Fall back to not abbreviating path
	}
	displayPath := profileDir
	if homeDir != "" && len(profileDir) > len(homeDir) && profileDir[:len(homeDir)] == homeDir {
		displayPath = "~" + profileDir[len(homeDir):]
	}

	readmeContent := "# Workspace Profile: " + opts.ProfileName + "\n\n" +
		"Template: " + opts.Template + "\n" +
		"Created: " + created + "\n\n" +
		"## Setup\n\n" +
		"1. Navigate to this directory:\n" +
		"   ```bash\n" +
		"   cd \"" + displayPath + "\"\n" +
		"   ```\n\n" +
		"2. Allow direnv (first time only):\n" +
		"   ```bash\n" +
		"   direnv allow\n" +
		"   ```\n\n" +
		"3. Verify the profile is loaded:\n" +
		"   ```bash\n" +
		"   echo $WORKSPACE_PROFILE\n" +
		"   git config user.email\n" +
		"   ```\n\n" +
		"## Customization\n\n" +
		"- Edit .gitconfig for git settings\n" +
		"- Edit .ssh/config for SSH configuration\n" +
		"- Edit .envrc for environment variables\n" +
		"- Add scripts to bin/ directory (automatically in PATH)\n" +
		"- Add secrets to .env file (gitignored)\n" +
		"- Add SSH keys to .ssh/ directory\n\n" +
		"## Environment Variables\n\n" +
		"### Workspace\n" +
		"- WORKSPACE_PROFILE: " + opts.ProfileName + "\n" +
		"- WORKSPACE_HOME: Path to this directory\n" +
		"- XDG_CONFIG_HOME: Path to profile-specific XDG config directory (.config)\n\n" +
		"### Git\n" +
		"- GIT_CONFIG_GLOBAL: Path to custom .gitconfig\n" +
		"- Git automatically uses bin/ssh wrapper (first in PATH) for SSH operations\n\n" +
		"### AWS\n" +
		"- AWS_CONFIG_FILE: Path to profile-specific AWS config\n" +
		"- AWS_SHARED_CREDENTIALS_FILE: Path to profile-specific AWS credentials\n\n" +
		"### Kubernetes\n" +
		"- KUBECONFIG: Path to profile-specific kubeconfig file\n\n" +
		"### Terraform\n" +
		"- TF_CLI_CONFIG_FILE: Path to profile-specific Terraform CLI config\n" +
		"- TF_PLUGIN_CACHE_DIR: (Optional) Path to Terraform plugin cache\n\n" +
		"### Azure\n" +
		"- AZURE_CONFIG_DIR: Path to profile-specific Azure CLI config directory\n" +
		"- Azure CLI will automatically use profile-specific settings and credentials\n\n" +
		"### Google Cloud\n" +
		"- CLOUDSDK_CONFIG: Path to profile-specific Google Cloud SDK config directory\n" +
		"- gcloud CLI will automatically use profile-specific settings and credentials\n\n" +
		"### Claude Code\n" +
		"- CLAUDE_CONFIG_DIR: Path to profile-specific Claude Code config directory\n" +
		"- Claude Code will automatically use profile-specific settings\n\n" +
		"### Gemini CLI\n" +
		"- GEMINI_CONFIG_DIR: Path to profile-specific Gemini CLI config directory\n" +
		"- Gemini CLI will automatically use profile-specific settings\n\n" +
		"## Next Steps\n\n" +
		"1. Update git configuration in .gitconfig:\n" +
		"   - Set your name and email\n" +
		"   - Configure GPG signing if needed\n" +
		"   - Add custom aliases\n\n" +
		"2. Configure SSH in .ssh/config:\n" +
		"   - Add host-specific settings\n" +
		"   - Configure SSH keys for this profile\n" +
		"   - Set up jump hosts if needed\n\n" +
		"3. Add SSH keys (optional):\n" +
		"   ```bash\n" +
		"   ssh-keygen -t ed25519 -f .ssh/id_ed25519_" + opts.ProfileName + " -C \"email@example.com\"\n" +
		"   ```\n\n" +
		"4. Configure 1Password SSH Agent in .config/1Password/agent.toml:\n" +
		"   - Uncomment and configure SSH keys from your 1Password vaults\n" +
		"   - Use 'op item list' to find vault and item names\n" +
		"   - Keys will be automatically loaded when profile is active\n\n" +
		"5. Configure AWS credentials in .aws/:\n" +
		"   - Edit .aws/config for AWS profiles\n" +
		"   - Add credentials to .env or .aws/credentials\n" +
		"   - AWS CLI will automatically use profile-specific settings\n\n" +
		"6. Configure Azure CLI in .azure/:\n" +
		"   - Run 'az login' to authenticate (credentials stored in .azure/)\n" +
		"   - Azure CLI will automatically use profile-specific settings\n" +
		"   - Use 'az account list' to see available subscriptions\n" +
		"   - Use 'az account set --subscription <name>' to set active subscription\n\n" +
		"7. Configure Google Cloud SDK in .gcloud/:\n" +
		"   - Run 'gcloud auth login' to authenticate (credentials stored in .gcloud/)\n" +
		"   - Run 'gcloud config set project <project-id>' to set active project\n" +
		"   - gcloud CLI will automatically use profile-specific settings\n" +
		"   - Use 'gcloud config list' to see current configuration\n" +
		"   - Use 'gcloud config configurations list' to see available configurations\n\n" +
		"8. Configure Claude Code in .config/claude/:\n" +
		"   - Claude Code will automatically use profile-specific settings\n" +
		"   - Settings, extensions, and preferences are isolated per profile\n" +
		"   - Configuration files are stored in .config/claude/\n\n" +
		"9. Configure Gemini CLI in .config/gemini/:\n" +
		"   - Gemini CLI will automatically use profile-specific settings\n" +
		"   - API keys and preferences are isolated per profile\n" +
		"   - Configuration files are stored in .config/gemini/\n\n" +
		"10. Configure Kubernetes in .kube/:\n" +
		"   - Copy or generate kubeconfig to .kube/config\n" +
		"   - kubectl will automatically use profile-specific kubeconfig\n\n" +
		"11. XDG-compliant tools (optional):\n" +
		"   - Many tools respect XDG_CONFIG_HOME (neovim, tmux, bat, etc.)\n" +
		"   - Add configs to .config/<tool>/\n" +
		"   - Example: .config/nvim/init.vim\n\n" +
		"12. Add project-specific environment variables to .envrc\n\n" +
		"13. Create .env for secrets (AWS keys, API tokens, Azure credentials, GCP credentials, Claude API keys, Gemini API keys, etc.)\n\n" +
		"14. Add custom scripts to bin/ directory\n"

	readmePath := filepath.Join(profileDir, "README.md")
	return os.WriteFile(readmePath, []byte(readmeContent), 0644)
}

func createEnvExample(profileDir string) error {
	ui.PrintInfo("Creating .env.example...")

	envExampleContent := `# Example environment variables
# Copy this to .env and fill in your non-secret config
# Secrets are loaded automatically from 1Password vault (workspace-<profile>)

# AWS credentials
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key
# AWS_DEFAULT_REGION=us-east-1

# Azure credentials (optional - can also use 'az login')
# AZURE_CLIENT_ID=your-client-id
# AZURE_CLIENT_SECRET=your-client-secret
# AZURE_TENANT_ID=your-tenant-id
# AZURE_SUBSCRIPTION_ID=your-subscription-id

# Google Cloud credentials (optional - can also use 'gcloud auth login')
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
# GCP_PROJECT=your-project-id
# GCP_REGION=us-central1
# GCP_ZONE=us-central1-a

# Claude Code / Anthropic API credentials
# ANTHROPIC_API_KEY=your-anthropic-api-key

# Gemini CLI / Google AI API credentials
# GEMINI_API_KEY=your-gemini-api-key
# GOOGLE_AI_API_KEY=your-google-ai-api-key

# API keys
# API_KEY=your-api-key
# API_SECRET=your-api-secret

# Database
# DATABASE_URL=postgresql://localhost:5432/mydb
# REDIS_URL=redis://localhost:6379
`

	envExamplePath := filepath.Join(profileDir, ".env.example")
	return os.WriteFile(envExamplePath, []byte(envExampleContent), 0644)
}

