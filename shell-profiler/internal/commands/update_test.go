package commands

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// --- updateEnvrc tests ---

func TestUpdateEnvrc_RemovesToolVars(t *testing.T) {
	tmpDir := t.TempDir()
	envrcContent := `#!/usr/bin/env bash
export WORKSPACE_PROFILE="test"

# Git configuration
export GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/.gitconfig"

# AWS configuration
export AWS_CONFIG_FILE="$WORKSPACE_HOME/.aws/config"

# Welcome message
log_status "done"
`
	profileDir := tmpDir
	if err := os.WriteFile(filepath.Join(profileDir, ".envrc"), []byte(envrcContent), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateEnvrc(profileDir, "test", false, false)
	if err != nil {
		t.Fatalf("updateEnvrc() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when tool vars are present")
	}

	data, _ := os.ReadFile(filepath.Join(profileDir, ".envrc"))
	content := string(data)

	if strings.Contains(content, "export GIT_CONFIG_GLOBAL=") {
		t.Error("should have removed GIT_CONFIG_GLOBAL export")
	}
	if strings.Contains(content, "export AWS_CONFIG_FILE=") {
		t.Error("should have removed AWS_CONFIG_FILE export")
	}
}

func TestUpdateEnvrc_PreservesShebangAndNonToolLines(t *testing.T) {
	tmpDir := t.TempDir()
	envrcContent := `#!/usr/bin/env bash
export WORKSPACE_PROFILE="test"
export WORKSPACE_HOME="$PWD"

# Git configuration
export GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/.gitconfig"

# Custom user var
export MY_CUSTOM_VAR="hello"

# Welcome message
log_status "done"
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".envrc"), []byte(envrcContent), 0644); err != nil {
		t.Fatal(err)
	}

	_, err := updateEnvrc(tmpDir, "test", false, false)
	if err != nil {
		t.Fatalf("updateEnvrc() error: %v", err)
	}

	data, _ := os.ReadFile(filepath.Join(tmpDir, ".envrc"))
	content := string(data)

	if !strings.Contains(content, "#!/usr/bin/env bash") {
		t.Error("should preserve shebang")
	}
	if !strings.Contains(content, `export WORKSPACE_PROFILE="test"`) {
		t.Error("should preserve WORKSPACE_PROFILE")
	}
	if !strings.Contains(content, `export MY_CUSTOM_VAR="hello"`) {
		t.Error("should preserve custom vars")
	}
}

func TestUpdateEnvrc_AddsDotenvIfMissing(t *testing.T) {
	tmpDir := t.TempDir()
	envrcContent := `#!/usr/bin/env bash
export WORKSPACE_PROFILE="test"

# Welcome message
log_status "done"
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".envrc"), []byte(envrcContent), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateEnvrc(tmpDir, "test", false, false)
	if err != nil {
		t.Fatalf("updateEnvrc() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when dotenv_if_exists is missing")
	}

	data, _ := os.ReadFile(filepath.Join(tmpDir, ".envrc"))
	content := string(data)

	if !strings.Contains(content, "dotenv_if_exists .env") {
		t.Error("should add dotenv_if_exists .env")
	}
}

func TestUpdateEnvrc_NoChangeWhenClean(t *testing.T) {
	tmpDir := t.TempDir()
	envrcContent := `#!/usr/bin/env bash
export WORKSPACE_PROFILE="test"
dotenv_if_exists .env
dotenv_if_exists .envrc.local
log_status "done"
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".envrc"), []byte(envrcContent), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateEnvrc(tmpDir, "test", false, false)
	if err != nil {
		t.Fatalf("updateEnvrc() error: %v", err)
	}
	if updated {
		t.Error("expected update=false when envrc is already clean")
	}
}

// --- updateEnvFile tests ---

func TestUpdateEnvFile_CreatesNewWhenMissing(t *testing.T) {
	tmpDir := t.TempDir()

	updated, err := updateEnvFile(tmpDir, "test", false)
	if err != nil {
		t.Fatalf("updateEnvFile() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when .env doesn't exist")
	}

	data, err := os.ReadFile(filepath.Join(tmpDir, ".env"))
	if err != nil {
		t.Fatalf("read .env: %v", err)
	}

	content := string(data)
	requiredVars := []string{
		"GIT_CONFIG_GLOBAL=",
		"GIT_SSH_COMMAND=",
		"AWS_CONFIG_FILE=",
		"KUBECONFIG=",
		"CLAUDE_CONFIG_DIR=",
		"GEMINI_CONFIG_DIR=",
	}
	for _, v := range requiredVars {
		if !strings.Contains(content, v) {
			t.Errorf(".env should contain %q", v)
		}
	}
}

func TestUpdateEnvFile_AddsMissingVars(t *testing.T) {
	tmpDir := t.TempDir()

	// Create .env with only some vars
	existingContent := `# Existing env
GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/.gitconfig"
AWS_CONFIG_FILE="$WORKSPACE_HOME/.aws/config"
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".env"), []byte(existingContent), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateEnvFile(tmpDir, "test", false)
	if err != nil {
		t.Fatalf("updateEnvFile() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when vars are missing")
	}

	data, _ := os.ReadFile(filepath.Join(tmpDir, ".env"))
	content := string(data)

	if !strings.Contains(content, "CLAUDE_CONFIG_DIR=") {
		t.Error("should add missing CLAUDE_CONFIG_DIR")
	}
	if !strings.Contains(content, "GEMINI_CONFIG_DIR=") {
		t.Error("should add missing GEMINI_CONFIG_DIR")
	}
}

func TestUpdateEnvFile_NoChangeWhenAllPresent(t *testing.T) {
	tmpDir := t.TempDir()

	allVars := `GIT_CONFIG_GLOBAL="x"
GIT_SSH_COMMAND="x"
XDG_CONFIG_HOME="x"
SSH_AUTH_SOCK="x"
AWS_CONFIG_FILE="x"
AWS_SHARED_CREDENTIALS_FILE="x"
KUBECONFIG="x"
TF_CLI_CONFIG_FILE="x"
AZURE_CONFIG_DIR="x"
CLOUDSDK_CONFIG="x"
CLAUDE_CONFIG_DIR="x"
GEMINI_CONFIG_DIR="x"
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".env"), []byte(allVars), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateEnvFile(tmpDir, "test", false)
	if err != nil {
		t.Fatalf("updateEnvFile() error: %v", err)
	}
	if updated {
		t.Error("expected update=false when all vars present")
	}
}

// --- updateGitignore tests ---

func TestUpdateGitignore_CreatesWhenMissing(t *testing.T) {
	tmpDir := t.TempDir()

	updated, err := updateGitignore(tmpDir, false, false)
	if err != nil {
		t.Fatalf("updateGitignore() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when .gitignore doesn't exist")
	}

	if _, err := os.Stat(filepath.Join(tmpDir, ".gitignore")); err != nil {
		t.Error(".gitignore should be created")
	}
}

func TestUpdateGitignore_RemovesEnvSecretsTplNegation(t *testing.T) {
	tmpDir := t.TempDir()

	existing := `.env
!.env.secrets.tpl
.ssh/id_*
.config/claude/
.config/gemini/
.azure/config
.gcloud/configurations
.gcloud/credentials
.gcloud/access_tokens.db
.gcloud/legacy_credentials
.gcloud/logs
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".gitignore"), []byte(existing), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateGitignore(tmpDir, false, false)
	if err != nil {
		t.Fatalf("updateGitignore() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when negation needs removal")
	}

	data, _ := os.ReadFile(filepath.Join(tmpDir, ".gitignore"))
	content := string(data)

	if strings.Contains(content, "!.env.secrets.tpl") {
		t.Error("should have removed !.env.secrets.tpl negation")
	}
}

func TestUpdateGitignore_AddsMissingPatterns(t *testing.T) {
	tmpDir := t.TempDir()

	// Minimal gitignore without cloud patterns
	existing := `.env
.ssh/id_*
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".gitignore"), []byte(existing), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateGitignore(tmpDir, false, false)
	if err != nil {
		t.Fatalf("updateGitignore() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when patterns are missing")
	}

	data, _ := os.ReadFile(filepath.Join(tmpDir, ".gitignore"))
	content := string(data)

	if !strings.Contains(content, ".config/claude/") {
		t.Error("should add .config/claude/ pattern")
	}
}

// --- removeSecretsTemplate tests ---

func TestRemoveSecretsTemplate_RemovesExisting(t *testing.T) {
	tmpDir := t.TempDir()

	tplPath := filepath.Join(tmpDir, ".env.secrets.tpl")
	if err := os.WriteFile(tplPath, []byte("SECRET=op://vault/item"), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := removeSecretsTemplate(tmpDir, false)
	if err != nil {
		t.Fatalf("removeSecretsTemplate() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true when file exists")
	}
	if _, err := os.Stat(tplPath); !os.IsNotExist(err) {
		t.Error("file should be removed")
	}
}

func TestRemoveSecretsTemplate_ReturnsFalseWhenMissing(t *testing.T) {
	tmpDir := t.TempDir()

	updated, err := removeSecretsTemplate(tmpDir, false)
	if err != nil {
		t.Fatalf("removeSecretsTemplate() error: %v", err)
	}
	if updated {
		t.Error("expected update=false when file doesn't exist")
	}
}

func TestRemoveSecretsTemplate_DryRunDoesNotDelete(t *testing.T) {
	tmpDir := t.TempDir()

	tplPath := filepath.Join(tmpDir, ".env.secrets.tpl")
	if err := os.WriteFile(tplPath, []byte("SECRET=op://vault/item"), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := removeSecretsTemplate(tmpDir, true)
	if err != nil {
		t.Fatalf("removeSecretsTemplate() error: %v", err)
	}
	if !updated {
		t.Error("dry run should still report update=true")
	}
	if _, err := os.Stat(tplPath); err != nil {
		t.Error("dry run should not delete the file")
	}
}

// --- updateEnvrcVaultDiscovery tests ---

func TestUpdateEnvrcVaultDiscovery_InsertsBlock(t *testing.T) {
	tmpDir := t.TempDir()

	envrcContent := `#!/usr/bin/env bash
export WORKSPACE_PROFILE="test"
dotenv_if_exists .env
dotenv_if_exists .envrc.local
log_status "done"
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".envrc"), []byte(envrcContent), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateEnvrcVaultDiscovery(tmpDir, "test", false)
	if err != nil {
		t.Fatalf("updateEnvrcVaultDiscovery() error: %v", err)
	}
	if !updated {
		t.Error("expected update=true")
	}

	data, _ := os.ReadFile(filepath.Join(tmpDir, ".envrc"))
	content := string(data)

	if !strings.Contains(content, "op item list") {
		t.Error("should insert vault discovery block with 'op item list'")
	}
	if !strings.Contains(content, `_op_vault="workspace-test"`) {
		t.Error("should contain vault name derived from profile name")
	}
}

func TestUpdateEnvrcVaultDiscovery_NoChangeWhenPresent(t *testing.T) {
	tmpDir := t.TempDir()

	envrcContent := `#!/usr/bin/env bash
export WORKSPACE_PROFILE="test"
dotenv_if_exists .env
# vault discovery
op item list --vault "$_op_vault"
log_status "done"
`
	if err := os.WriteFile(filepath.Join(tmpDir, ".envrc"), []byte(envrcContent), 0644); err != nil {
		t.Fatal(err)
	}

	updated, err := updateEnvrcVaultDiscovery(tmpDir, "test", false)
	if err != nil {
		t.Fatalf("updateEnvrcVaultDiscovery() error: %v", err)
	}
	if updated {
		t.Error("expected update=false when vault discovery already present")
	}
}

// --- updateDirectories tests ---

func TestUpdateDirectories_CreatesMissing(t *testing.T) {
	tmpDir := t.TempDir()

	// Create profile dir with only some subdirs
	profileDir := tmpDir
	os.MkdirAll(filepath.Join(profileDir, ".ssh"), 0755)
	os.MkdirAll(filepath.Join(profileDir, "bin"), 0755)

	created, err := updateDirectories(profileDir, false)
	if err != nil {
		t.Fatalf("updateDirectories() error: %v", err)
	}
	if len(created) == 0 {
		t.Error("expected some directories to be created")
	}

	// Verify all required dirs exist now
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
	for _, dir := range requiredDirs {
		fullPath := filepath.Join(profileDir, dir)
		if _, err := os.Stat(fullPath); err != nil {
			t.Errorf("directory %q should exist after update: %v", dir, err)
		}
	}
}

func TestUpdateDirectories_SetsSSHPermissions(t *testing.T) {
	tmpDir := t.TempDir()

	// Create .ssh with wrong permissions
	sshDir := filepath.Join(tmpDir, ".ssh")
	os.MkdirAll(sshDir, 0755)

	_, err := updateDirectories(tmpDir, false)
	if err != nil {
		t.Fatalf("updateDirectories() error: %v", err)
	}

	info, _ := os.Stat(sshDir)
	if info.Mode().Perm() != 0700 {
		t.Errorf(".ssh permissions = %o, want 0700", info.Mode().Perm())
	}
}
