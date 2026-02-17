package commands

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type UpdateOptions struct {
	ProfileName string
	Force       bool
	DryRun      bool
	NoBackup    bool
}

// UpdateProfile updates an existing profile with new features
func UpdateProfile(profilesDir string, opts UpdateOptions) error {
	// If no profile name provided, show interactive selection
	if opts.ProfileName == "" {
		entries, err := os.ReadDir(profilesDir)
		if err != nil {
			return fmt.Errorf("failed to read profiles directory: %w", err)
		}

		var profiles []string
		for _, entry := range entries {
			if entry.IsDir() && entry.Name() != ".git" {
				profilePath := filepath.Join(profilesDir, entry.Name())
				envrcPath := filepath.Join(profilePath, ".envrc")
				if _, err := os.Stat(envrcPath); err == nil {
					profiles = append(profiles, entry.Name())
				}
			}
		}

		if len(profiles) == 0 {
			return fmt.Errorf("no profiles found")
		}

		selected, err := ui.SelectProfile(profiles, "Select profile to update:")
		if err != nil {
			return err
		}
		opts.ProfileName = selected
	}

	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// Check if profile exists
	if _, err := os.Stat(profileDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not exist at: %s", opts.ProfileName, profileDir)
	}

	envrcPath := filepath.Join(profileDir, ".envrc")
	if _, err := os.Stat(envrcPath); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not appear to be a valid profile (missing .envrc)", opts.ProfileName)
	}

	ui.PrintInfo(fmt.Sprintf("Updating profile: %s", opts.ProfileName))
	fmt.Printf("  Location: %s\n", profileDir)
	fmt.Println()

	// Create backup unless --no-backup is specified
	if !opts.NoBackup && !opts.DryRun {
		if err := createBackup(profileDir, opts.ProfileName); err != nil {
			ui.PrintWarning(fmt.Sprintf("Failed to create backup: %v", err))
			if !opts.Force {
				confirmed, err := ui.Confirm("Continue without backup?", false)
				if err != nil || !confirmed {
					return fmt.Errorf("update cancelled")
				}
			}
		}
	}

	// Track what was updated
	updates := []string{}

	// Update directories
	if updated, err := updateDirectories(profileDir, opts.DryRun); err != nil {
		return fmt.Errorf("failed to update directories: %w", err)
	} else if len(updated) > 0 {
		updates = append(updates, fmt.Sprintf("Created directories: %s", strings.Join(updated, ", ")))
	}

	// Update .envrc (remove tool-specific vars that belong in .env)
	if updated, err := updateEnvrc(profileDir, opts.ProfileName, opts.DryRun, opts.Force); err != nil {
		return fmt.Errorf("failed to update .envrc: %w", err)
	} else if updated {
		updates = append(updates, "Updated .envrc (moved tool-specific vars to .env)")
	}

	// Update .env with tool-specific environment variables
	if updated, err := updateEnvFile(profileDir, opts.ProfileName, opts.DryRun); err != nil {
		return fmt.Errorf("failed to update .env: %w", err)
	} else if updated {
		updates = append(updates, "Updated .env with tool-specific environment variables")
	}

	// Update .gitignore
	if updated, err := updateGitignore(profileDir, opts.DryRun, opts.Force); err != nil {
		return fmt.Errorf("failed to update .gitignore: %w", err)
	} else if updated {
		updates = append(updates, "Updated .gitignore with new patterns")
	}

	// Remove .env.secrets.tpl (replaced by vault discovery in .envrc)
	if updated, err := removeSecretsTemplate(profileDir, opts.DryRun); err != nil {
		return fmt.Errorf("failed to remove .env.secrets.tpl: %w", err)
	} else if updated {
		updates = append(updates, "Removed .env.secrets.tpl (secrets now auto-discovered from vault)")
	}

	// Replace op inject with vault discovery in .envrc
	if updated, err := updateEnvrcVaultDiscovery(profileDir, opts.ProfileName, opts.DryRun); err != nil {
		return fmt.Errorf("failed to update .envrc with vault discovery: %w", err)
	} else if updated {
		updates = append(updates, "Replaced op inject with vault discovery in .envrc")
	}

	// Summary
	if opts.DryRun {
		ui.PrintInfo("DRY RUN - No changes were made")
		if len(updates) > 0 {
			fmt.Println()
			fmt.Println("Would update:")
			for _, update := range updates {
				fmt.Printf("  - %s\n", update)
			}
		} else {
			fmt.Println("  Profile is already up to date")
		}
	} else {
		if len(updates) > 0 {
			ui.PrintSuccess("Profile updated successfully")
			fmt.Println()
			fmt.Println("Updates applied:")
			for _, update := range updates {
				fmt.Printf("  ✓ %s\n", update)
			}
		} else {
			ui.PrintInfo("Profile is already up to date")
		}
	}

	return nil
}

func createBackup(profileDir, _profileName string) error {
	backupDir := filepath.Join(profileDir, ".backups")
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		return fmt.Errorf("failed to create backup directory: %w", err)
	}

	timestamp := time.Now().Format("2006-01-02_15-04-05")
	backupPath := filepath.Join(backupDir, fmt.Sprintf("update_%s", timestamp))

	// Copy important files
	filesToBackup := []string{
		".envrc",
		".env",
		".env.secrets.tpl",
		".gitconfig",
		".gitignore",
	}

	for _, file := range filesToBackup {
		src := filepath.Join(profileDir, file)
		if _, err := os.Stat(src); err == nil {
			content, err := os.ReadFile(src)
			if err != nil {
				continue
			}

			backupFile := filepath.Join(backupPath, file)
			if err := os.MkdirAll(filepath.Dir(backupFile), 0755); err != nil {
				continue
			}

			if err := os.WriteFile(backupFile, content, 0644); err != nil {
				continue
			}
		}
	}

	ui.PrintInfo(fmt.Sprintf("Backup created: %s", backupPath))
	return nil
}

func updateDirectories(profileDir string, dryRun bool) ([]string, error) {
	requiredDirs := []string{
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

	var created []string
	for _, dir := range requiredDirs {
		fullPath := filepath.Join(profileDir, dir)
		if _, err := os.Stat(fullPath); os.IsNotExist(err) {
			if !dryRun {
				if err := os.MkdirAll(fullPath, 0755); err != nil {
					return nil, fmt.Errorf("failed to create directory %s: %w", dir, err)
				}
			}
			created = append(created, dir)
		}
	}

	// Set SSH directory permissions
	sshDir := filepath.Join(profileDir, ".ssh")
	if _, err := os.Stat(sshDir); err == nil && !dryRun {
		if err := os.Chmod(sshDir, 0700); err != nil {
			// Non-fatal, just warn
			ui.PrintWarning(fmt.Sprintf("Failed to set SSH directory permissions: %v", err))
		}
	}

	return created, nil
}

func updateEnvrc(profileDir, _profileName string, dryRun, _force bool) (bool, error) {
	envrcPath := filepath.Join(profileDir, ".envrc")
	content, err := os.ReadFile(envrcPath)
	if err != nil {
		return false, fmt.Errorf("failed to read .envrc: %w", err)
	}

	envrcContent := string(content)
	updated := false

	// Tool-specific variable names that belong in .env, not .envrc
	toolVars := []string{
		"XDG_CONFIG_HOME",
		"SSH_AUTH_SOCK",
		"GIT_CONFIG_GLOBAL",
		"GIT_SSH_COMMAND",
		"AWS_CONFIG_FILE",
		"AWS_SHARED_CREDENTIALS_FILE",
		"KUBECONFIG",
		"TF_CLI_CONFIG_FILE",
		"TF_PLUGIN_CACHE_DIR",
		"AZURE_CONFIG_DIR",
		"CLOUDSDK_CONFIG",
		"CLAUDE_CONFIG_DIR",
		"GEMINI_CONFIG_DIR",
	}

	// Remove tool-specific export lines and their preceding comments from .envrc
	lines := strings.Split(envrcContent, "\n")
	var cleanedLines []string
	skipNextBlank := false

	for i := 0; i < len(lines); i++ {
		line := lines[i]
		trimmed := strings.TrimSpace(line)

		// Check if this line exports a tool-specific variable
		isToolVar := false
		for _, varName := range toolVars {
			if strings.Contains(trimmed, "export "+varName+"=") || strings.Contains(trimmed, "export "+varName+" =") {
				isToolVar = true
				break
			}
		}

		if isToolVar {
			// Remove preceding comment lines (walk backwards through cleanedLines)
			for len(cleanedLines) > 0 {
				prev := strings.TrimSpace(cleanedLines[len(cleanedLines)-1])
				if strings.HasPrefix(prev, "#") && prev != "#!/usr/bin/env bash" {
					cleanedLines = cleanedLines[:len(cleanedLines)-1]
				} else {
					break
				}
			}
			updated = true
			skipNextBlank = true
			continue
		}

		// Skip extra blank lines left behind after removing vars
		if skipNextBlank && trimmed == "" {
			skipNextBlank = false
			continue
		}
		skipNextBlank = false

		cleanedLines = append(cleanedLines, line)
	}

	// Ensure dotenv_if_exists .env is present
	hasDotenvLoad := false
	for _, line := range cleanedLines {
		if strings.Contains(line, "dotenv_if_exists .env") && !strings.Contains(line, ".envrc") {
			hasDotenvLoad = true
			break
		}
	}

	if !hasDotenvLoad {
		// Insert before "# Load local overrides" or "# Welcome message"
		insertIdx := -1
		for i, line := range cleanedLines {
			if strings.Contains(line, "# Load local overrides") || strings.Contains(line, "dotenv_if_exists .envrc.local") || strings.Contains(line, "# Welcome message") {
				insertIdx = i
				break
			}
		}

		dotenvLines := []string{
			"# Load environment variables from .env file",
			"# Tool-specific paths and secrets belong in .env, not here",
			"dotenv_if_exists .env",
			"",
		}

		if insertIdx >= 0 {
			newLines := make([]string, 0, len(cleanedLines)+len(dotenvLines))
			newLines = append(newLines, cleanedLines[:insertIdx]...)
			newLines = append(newLines, dotenvLines...)
			newLines = append(newLines, cleanedLines[insertIdx:]...)
			cleanedLines = newLines
		} else {
			cleanedLines = append(cleanedLines, dotenvLines...)
		}
		updated = true
	}

	if updated && !dryRun {
		envrcContent = strings.Join(cleanedLines, "\n")
		if err := os.WriteFile(envrcPath, []byte(envrcContent), 0644); err != nil {
			return false, fmt.Errorf("failed to write .envrc: %w", err)
		}
	}

	return updated, nil
}

func updateEnvFile(profileDir, profileName string, dryRun bool) (bool, error) {
	envPath := filepath.Join(profileDir, ".env")
	var envContent string

	if data, err := os.ReadFile(envPath); err == nil {
		envContent = string(data)
	}

	updated := false

	// Define tool-specific variables that should be in .env
	requiredVars := []struct {
		name    string
		value   string
		comment string
	}{
		{"GIT_CONFIG_GLOBAL", `"$WORKSPACE_HOME/.gitconfig"`, "# Git configuration"},
		{"GIT_SSH_COMMAND", `"ssh -F $WORKSPACE_HOME/.ssh/config"`, "# SSH configuration\n# Use workspace-specific SSH config instead of $HOME/.ssh/config"},
		{"XDG_CONFIG_HOME", `"$WORKSPACE_HOME/.config"`, "# XDG Base Directory specification\n# Point all XDG-compliant tools to workspace-specific config"},
		{"SSH_AUTH_SOCK", `"$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"`, "# 1Password SSH Agent\n# Point to 1Password SSH agent socket for SSH key management"},
		{"AWS_CONFIG_FILE", `"$WORKSPACE_HOME/.aws/config"`, "# AWS configuration\n# Point AWS CLI and SDKs to workspace-specific config and credentials"},
		{"AWS_SHARED_CREDENTIALS_FILE", `"$WORKSPACE_HOME/.aws/credentials"`, ""},
		{"KUBECONFIG", `"$WORKSPACE_HOME/.kube/config"`, "# Kubernetes configuration\n# Point kubectl to workspace-specific kubeconfig"},
		{"TF_CLI_CONFIG_FILE", `"$WORKSPACE_HOME/.terraformrc"`, "# Terraform configuration\n# Use workspace-specific Terraform CLI config"},
		{"AZURE_CONFIG_DIR", `"$WORKSPACE_HOME/.azure"`, "# Azure CLI configuration\n# Point Azure CLI to workspace-specific config directory"},
		{"CLOUDSDK_CONFIG", `"$WORKSPACE_HOME/.gcloud"`, "# Google Cloud SDK configuration\n# Point gcloud CLI to workspace-specific config directory"},
		{"CLAUDE_CONFIG_DIR", `"$WORKSPACE_HOME/.config/claude"`, "# Claude Code configuration\n# Point Claude Code to workspace-specific config directory"},
		{"GEMINI_CONFIG_DIR", `"$WORKSPACE_HOME/.config/gemini"`, "# Gemini CLI configuration\n# Point Gemini CLI to workspace-specific config directory"},
	}

	if envContent == "" {
		// Create new .env file with all vars
		envContent = fmt.Sprintf("# Environment variables for workspace profile: %s\n", profileName)
		envContent += "# This file is loaded by direnv via dotenv_if_exists in .envrc\n"
		envContent += "# Add tool-specific paths and non-secret config here (not in .envrc)\n"
		envContent += "# For secrets, use .env.secrets.tpl with op:// references\n"

		for _, v := range requiredVars {
			if v.comment != "" {
				envContent += "\n" + v.comment + "\n"
			}
			envContent += v.name + "=" + v.value + "\n"
		}
		updated = true
	} else {
		// Add missing variables
		for _, v := range requiredVars {
			if !strings.Contains(envContent, v.name+"=") {
				addition := ""
				if v.comment != "" {
					addition += "\n" + v.comment + "\n"
				}
				addition += v.name + "=" + v.value + "\n"
				envContent += addition
				updated = true
			}
		}
	}

	if updated && !dryRun {
		if err := os.WriteFile(envPath, []byte(envContent), 0644); err != nil {
			return false, fmt.Errorf("failed to write .env: %w", err)
		}
	}

	return updated, nil
}

func updateGitignore(profileDir string, dryRun, _force bool) (bool, error) {
	gitignorePath := filepath.Join(profileDir, ".gitignore")
	content, err := os.ReadFile(gitignorePath)
	if err != nil {
		// .gitignore doesn't exist, create it using the same function from create.go
		// We'll create a basic one inline
		if !dryRun {
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
			if err := os.WriteFile(gitignorePath, []byte(gitignoreContent), 0644); err != nil {
				return false, fmt.Errorf("failed to create .gitignore: %w", err)
			}
		}
		return true, nil
	}

	gitignoreContent := string(content)
	updated := false

	// Remove obsolete !.env.secrets.tpl negation
	if strings.Contains(gitignoreContent, "!.env.secrets.tpl") {
		gitignoreContent = strings.ReplaceAll(gitignoreContent, "!.env.secrets.tpl\n", "")
		updated = true
	}

	// Check and add missing patterns
	requiredPatterns := map[string]string{
		".azure/config":              "# Azure CLI credentials and sensitive config",
		".gcloud/configurations":     "# Google Cloud SDK credentials and sensitive config",
		".gcloud/credentials":        "",
		".gcloud/access_tokens.db":   "",
		".gcloud/legacy_credentials": "",
		".gcloud/logs":               "",
		".config/claude/":            "# Claude Code configuration (may contain API keys and sensitive data)",
		".config/gemini/":            "# Gemini CLI configuration (may contain API keys and sensitive data)",
	}

	// Group patterns by comment
	patternsByComment := make(map[string][]string)
	currentComment := ""
	for pattern, comment := range requiredPatterns {
		if comment != "" {
			currentComment = comment
		}
		if patternsByComment[currentComment] == nil {
			patternsByComment[currentComment] = []string{}
		}
		patternsByComment[currentComment] = append(patternsByComment[currentComment], pattern)
	}

	for comment, patterns := range patternsByComment {
		// Check if any pattern from this group is missing
		hasAny := false
		for _, pattern := range patterns {
			if strings.Contains(gitignoreContent, pattern) {
				hasAny = true
				break
			}
		}

		if !hasAny {
			// Find insertion point (after Azure section or at end)
			insertPoint := strings.Index(gitignoreContent, "# Azure CLI credentials")
			if insertPoint == -1 {
				insertPoint = strings.Index(gitignoreContent, "# Terraform")
				if insertPoint == -1 {
					insertPoint = len(gitignoreContent)
				}
			} else {
				// Find end of Azure section
				insertPoint = strings.Index(gitignoreContent[insertPoint:], "\n\n#")
				if insertPoint != -1 {
					insertPoint += insertPoint
				} else {
					insertPoint = strings.Index(gitignoreContent, "# Terraform")
					if insertPoint == -1 {
						insertPoint = len(gitignoreContent)
					}
				}
			}

			before := gitignoreContent[:insertPoint]
			after := gitignoreContent[insertPoint:]

			newSection := ""
			if comment != "" {
				newSection = comment + "\n"
			}
			for _, pattern := range patterns {
				newSection += pattern + "\n"
			}
			newSection += "\n"

			gitignoreContent = before + newSection + after
			updated = true
		}
	}

	if updated && !dryRun {
		if err := os.WriteFile(gitignorePath, []byte(gitignoreContent), 0644); err != nil {
			return false, fmt.Errorf("failed to write .gitignore: %w", err)
		}
	}

	return updated, nil
}

func removeSecretsTemplate(profileDir string, dryRun bool) (bool, error) {
	secretsTplPath := filepath.Join(profileDir, ".env.secrets.tpl")

	if _, err := os.Stat(secretsTplPath); os.IsNotExist(err) {
		return false, nil
	}

	if dryRun {
		return true, nil
	}

	if err := os.Remove(secretsTplPath); err != nil {
		return false, fmt.Errorf("failed to remove .env.secrets.tpl: %w", err)
	}

	return true, nil
}

func updateEnvrcVaultDiscovery(profileDir, profileName string, dryRun bool) (bool, error) {
	envrcPath := filepath.Join(profileDir, ".envrc")
	content, err := os.ReadFile(envrcPath)
	if err != nil {
		return false, fmt.Errorf("failed to read .envrc: %w", err)
	}

	envrcContent := string(content)

	// Already has vault discovery
	if strings.Contains(envrcContent, "op item list") {
		return false, nil
	}

	// Check if old op inject block exists and remove it
	hasOpInject := strings.Contains(envrcContent, "op inject")
	if hasOpInject {
		lines := strings.Split(envrcContent, "\n")
		var cleaned []string
		inBlock := false
		blockDepth := 0

		for _, line := range lines {
			trimmed := strings.TrimSpace(line)

			// Detect start of op inject block (comment or the if statement)
			if !inBlock && (strings.Contains(line, "op inject") || strings.Contains(line, ".env.secrets.tpl")) {
				// Walk back to remove preceding comment lines
				for len(cleaned) > 0 {
					prev := strings.TrimSpace(cleaned[len(cleaned)-1])
					if strings.HasPrefix(prev, "#") || prev == "" {
						cleaned = cleaned[:len(cleaned)-1]
					} else {
						break
					}
				}
				inBlock = true
				blockDepth = 0
			}

			if inBlock {
				if strings.HasPrefix(trimmed, "if ") || strings.HasPrefix(trimmed, "if [") {
					blockDepth++
				}
				if trimmed == "fi" {
					blockDepth--
					if blockDepth <= 0 {
						inBlock = false
					}
				}
				continue
			}

			cleaned = append(cleaned, line)
		}

		envrcContent = strings.Join(cleaned, "\n")
	}

	vaultDiscoveryBlock := fmt.Sprintf(`
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
        # macOS: stat -f %%m gives modification time in seconds since epoch
        _cache_mtime=$(stat -f %%m "$_sp_env" 2>/dev/null || echo 0)
    else
        # Linux: stat -c %%Y gives modification time in seconds since epoch
        _cache_mtime=$(stat -c %%Y "$_sp_env" 2>/dev/null || echo 0)
    fi
    _current_time=$(date +%%s)
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
    _op_vault="workspace-%s"
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
`, strings.ToLower(profileName))

	// Remove old "dotenv_if_exists .env" line (but keep .envrc.local)
	lines := strings.Split(envrcContent, "\n")
	var cleanedLines []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		// Remove "dotenv_if_exists .env" but keep ".envrc.local" and other dotenv lines
		if trimmed == "dotenv_if_exists .env" || strings.Contains(trimmed, "# Load environment variables from .env file") ||
		   (strings.HasPrefix(trimmed, "# Tool-specific") && strings.Contains(trimmed, "belong in .env")) {
			continue
		}
		cleanedLines = append(cleanedLines, line)
	}
	envrcContent = strings.Join(cleanedLines, "\n")

	// Insert vault discovery block before "dotenv_if_exists .envrc.local" or "# Welcome message"
	localIdx := strings.Index(envrcContent, "dotenv_if_exists .envrc.local")
	if localIdx == -1 {
		localIdx = strings.Index(envrcContent, "# Welcome message")
	}
	if localIdx == -1 {
		localIdx = strings.Index(envrcContent, "log_status")
	}

	if localIdx == -1 {
		envrcContent += "\n" + vaultDiscoveryBlock
	} else {
		// Walk back to remove any blank lines
		insertAt := localIdx
		for insertAt > 0 && envrcContent[insertAt-1] == '\n' {
			insertAt--
		}
		envrcContent = envrcContent[:insertAt] + "\n" + vaultDiscoveryBlock + "\n" + envrcContent[insertAt:]
	}

	if dryRun {
		return true, nil
	}

	if err := os.WriteFile(envrcPath, []byte(envrcContent), 0644); err != nil {
		return false, fmt.Errorf("failed to write .envrc: %w", err)
	}

	return true, nil
}
