package commands

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCreateProfile_EmptyName(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "",
		Template:    "basic",
	})
	if err == nil {
		t.Fatal("expected error for empty name")
	}
	if !strings.Contains(err.Error(), "profile name is required") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestCreateProfile_InvalidChars(t *testing.T) {
	tmpDir := t.TempDir()

	invalidNames := []string{"test/profile", "test profile", "test.profile", "test@work"}
	for _, name := range invalidNames {
		err := CreateProfile(tmpDir, CreateOptions{
			ProfileName: name,
			Template:    "basic",
		})
		if err == nil {
			t.Errorf("expected error for name %q", name)
		}
		if err != nil && !strings.Contains(err.Error(), "can only contain") {
			t.Errorf("name %q: unexpected error: %v", name, err)
		}
	}
}

func TestCreateProfile_ValidNames(t *testing.T) {
	validNames := []string{"my-profile", "work_2", "test123", "A", "a-b_c"}
	for _, name := range validNames {
		tmpDir := t.TempDir()
		err := CreateProfile(tmpDir, CreateOptions{
			ProfileName: name,
			Template:    "basic",
		})
		if err != nil {
			t.Errorf("name %q should be valid, got error: %v", name, err)
		}
	}
}

func TestCreateProfile_InvalidTemplate(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "invalid",
	})
	if err == nil {
		t.Fatal("expected error for invalid template")
	}
	if !strings.Contains(err.Error(), "invalid template") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestCreateProfile_AllTemplates(t *testing.T) {
	templates := []string{"basic", "personal", "work", "client"}
	for _, tmpl := range templates {
		tmpDir := t.TempDir()
		err := CreateProfile(tmpDir, CreateOptions{
			ProfileName: "test",
			Template:    tmpl,
		})
		if err != nil {
			t.Errorf("template %q should be valid, got error: %v", tmpl, err)
		}
	}
}

func TestCreateProfile_ExistingWithoutForce(t *testing.T) {
	tmpDir := t.TempDir()
	profileDir := filepath.Join(tmpDir, "existing")
	if err := os.MkdirAll(profileDir, 0755); err != nil {
		t.Fatal(err)
	}

	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "existing",
		Template:    "basic",
		Force:       false,
	})
	if err == nil {
		t.Fatal("expected error for existing profile without force")
	}
	if !strings.Contains(err.Error(), "already exists") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestCreateProfile_ExistingWithForce(t *testing.T) {
	tmpDir := t.TempDir()
	profileDir := filepath.Join(tmpDir, "existing")
	if err := os.MkdirAll(profileDir, 0755); err != nil {
		t.Fatal(err)
	}

	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "existing",
		Template:    "basic",
		Force:       true,
	})
	if err != nil {
		t.Errorf("force overwrite should succeed, got error: %v", err)
	}
}

func TestCreateProfile_DryRun(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "drytest",
		Template:    "basic",
		DryRun:      true,
	})
	if err != nil {
		t.Fatalf("dry run should succeed, got error: %v", err)
	}

	profileDir := filepath.Join(tmpDir, "drytest")
	if _, err := os.Stat(profileDir); !os.IsNotExist(err) {
		t.Error("dry run should not create any directories")
	}
}

func TestCreateProfile_DirectoryStructure(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	profileDir := filepath.Join(tmpDir, "test")
	expectedDirs := []string{
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

	for _, dir := range expectedDirs {
		fullPath := filepath.Join(profileDir, dir)
		info, err := os.Stat(fullPath)
		if err != nil {
			t.Errorf("directory %q should exist: %v", dir, err)
			continue
		}
		if !info.IsDir() {
			t.Errorf("%q should be a directory", dir)
		}
	}
}

func TestCreateProfile_SSHPermissions(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	sshDir := filepath.Join(tmpDir, "test", ".ssh")
	info, err := os.Stat(sshDir)
	if err != nil {
		t.Fatalf("stat .ssh: %v", err)
	}

	perm := info.Mode().Perm()
	if perm != 0700 {
		t.Errorf(".ssh permissions = %o, want 0700", perm)
	}
}

func TestCreateProfile_EnvrcContent(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "myprof",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	envrcPath := filepath.Join(tmpDir, "myprof", ".envrc")
	data, err := os.ReadFile(envrcPath)
	if err != nil {
		t.Fatalf("read .envrc: %v", err)
	}

	content := string(data)
	if !strings.Contains(content, `WORKSPACE_PROFILE="myprof"`) {
		t.Error(".envrc should contain WORKSPACE_PROFILE")
	}
	if !strings.Contains(content, `WORKSPACE_HOME="$PWD"`) {
		t.Error(".envrc should contain WORKSPACE_HOME")
	}
}

func TestCreateProfile_EnvFileContent(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	envPath := filepath.Join(tmpDir, "test", ".env")
	data, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("read .env: %v", err)
	}

	content := string(data)
	expectedVars := []string{
		"GIT_CONFIG_GLOBAL=",
		"AWS_CONFIG_FILE=",
		"KUBECONFIG=",
		"AZURE_CONFIG_DIR=",
		"CLOUDSDK_CONFIG=",
		"CLAUDE_CONFIG_DIR=",
		"GEMINI_CONFIG_DIR=",
	}
	for _, v := range expectedVars {
		if !strings.Contains(content, v) {
			t.Errorf(".env should contain %q", v)
		}
	}
}

func TestCreateProfile_GitconfigContent(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "personal",
		GitName:     "Test User",
		GitEmail:    "test@example.com",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	data, err := os.ReadFile(filepath.Join(tmpDir, "test", ".gitconfig"))
	if err != nil {
		t.Fatalf("read .gitconfig: %v", err)
	}

	content := string(data)
	if !strings.Contains(content, "name = Test User") {
		t.Error(".gitconfig should contain user.name")
	}
	if !strings.Contains(content, "email = test@example.com") {
		t.Error(".gitconfig should contain user.email")
	}
}

func TestCreateProfile_GitconfigTemplatePersonal(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "personal",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	data, err := os.ReadFile(filepath.Join(tmpDir, "test", ".gitconfig"))
	if err != nil {
		t.Fatalf("read .gitconfig: %v", err)
	}

	content := string(data)
	if !strings.Contains(content, "helper = cache --timeout=3600") {
		t.Error("personal template should have credential cache timeout=3600")
	}
}

func TestCreateProfile_GitconfigTemplateWork(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "work",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	data, err := os.ReadFile(filepath.Join(tmpDir, "test", ".gitconfig"))
	if err != nil {
		t.Fatalf("read .gitconfig: %v", err)
	}

	content := string(data)
	if !strings.Contains(content, "helper = cache --timeout=7200") {
		t.Error("work template should have credential cache timeout=7200")
	}
}

func TestCreateProfile_SSHConfigContainsAbsPath(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	data, err := os.ReadFile(filepath.Join(tmpDir, "test", ".ssh", "config"))
	if err != nil {
		t.Fatalf("read .ssh/config: %v", err)
	}

	content := string(data)
	profileDir := filepath.Join(tmpDir, "test")
	if !strings.Contains(content, profileDir) {
		t.Errorf(".ssh/config should contain absolute path %q", profileDir)
	}
}

func TestCreateProfile_SSHWrapperExecutable(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	wrapperPath := filepath.Join(tmpDir, "test", "bin", "ssh")
	info, err := os.Stat(wrapperPath)
	if err != nil {
		t.Fatalf("stat bin/ssh: %v", err)
	}

	perm := info.Mode().Perm()
	if perm&0111 == 0 {
		t.Errorf("bin/ssh should be executable, got permissions %o", perm)
	}
}

func TestCreateProfile_GitignoreExists(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	gitignorePath := filepath.Join(tmpDir, "test", ".gitignore")
	if _, err := os.Stat(gitignorePath); err != nil {
		t.Errorf(".gitignore should exist: %v", err)
	}
}

func TestCreateProfile_EnvExampleExists(t *testing.T) {
	tmpDir := t.TempDir()
	err := CreateProfile(tmpDir, CreateOptions{
		ProfileName: "test",
		Template:    "basic",
	})
	if err != nil {
		t.Fatalf("CreateProfile() error: %v", err)
	}

	envExamplePath := filepath.Join(tmpDir, "test", ".env.example")
	if _, err := os.Stat(envExamplePath); err != nil {
		t.Errorf(".env.example should exist: %v", err)
	}
}
