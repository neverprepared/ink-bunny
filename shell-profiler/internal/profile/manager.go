package profile

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type Manager struct {
	profilesDir string
}

func NewManager(profilesDir string) *Manager {
	return &Manager{
		profilesDir: profilesDir,
	}
}

// ShowInfo displays information about the current workspace profile
func (m *Manager) ShowInfo() error {
	profileName := os.Getenv("WORKSPACE_PROFILE")
	profileHome := os.Getenv("WORKSPACE_HOME")

	if profileName == "" {
		fmt.Println("No workspace profile active")
		fmt.Println()
		fmt.Println("To activate a profile:")
		fmt.Println("  1. cd profiles/<profile-name>")
		fmt.Println("  2. direnv allow (first time only)")
		fmt.Println()
		fmt.Println("Available profiles:")
		// List available profiles
		return m.listProfiles()
	}

	fmt.Println("=== Current Workspace Profile ===")
	fmt.Println()
	fmt.Printf("Profile Name:    %s\n", profileName)
	fmt.Printf("Profile Home:    %s\n", profileHome)
	fmt.Println()

	// Git Configuration
	gitConfig := os.Getenv("GIT_CONFIG_GLOBAL")
	fmt.Println("Git Configuration:")
	fmt.Printf("  Config File:   %s\n", gitConfig)
	if gitConfig != "" {
		if _, err := os.Stat(gitConfig); err == nil {
			// Get git config values
			if name := getGitConfig(gitConfig, "user.name"); name != "" {
				fmt.Printf("  User Name:     %s\n", name)
			} else {
				fmt.Println("  User Name:     Not set")
			}
			if email := getGitConfig(gitConfig, "user.email"); email != "" {
				fmt.Printf("  User Email:    %s\n", email)
			} else {
				fmt.Println("  User Email:    Not set")
			}
			if branch := getGitConfig(gitConfig, "init.defaultBranch"); branch != "" {
				fmt.Printf("  Default Branch: %s\n", branch)
			} else {
				fmt.Println("  Default Branch: Not set")
			}
		} else {
			fmt.Println("  Warning: Config file not found")
		}
	}
	fmt.Println()

	// Environment Variables
	fmt.Println("Environment Variables:")
	for _, env := range os.Environ() {
		if strings.HasPrefix(env, "WORKSPACE_") {
			parts := strings.SplitN(env, "=", 2)
			if len(parts) == 2 {
				fmt.Printf("  %s=%s\n", parts[0], parts[1])
			}
		}
	}
	fmt.Println()

	// PATH additions
	fmt.Println("PATH additions:")
	path := os.Getenv("PATH")
	paths := strings.Split(path, ":")
	for _, p := range paths {
		if strings.Contains(p, profileHome) {
			fmt.Printf("  %s\n", p)
		}
	}

	return nil
}

// listProfiles lists all available profiles
func (m *Manager) listProfiles() error {
	entries, err := os.ReadDir(m.profilesDir)
	if err != nil {
		return fmt.Errorf("failed to read profiles directory: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() && entry.Name() != ".git" {
			profilePath := filepath.Join(m.profilesDir, entry.Name())
			envrcPath := filepath.Join(profilePath, ".envrc")
			if _, err := os.Stat(envrcPath); err == nil {
				fmt.Printf("  - %s\n", entry.Name())
			}
		}
	}

	return nil
}

// getGitConfig reads a git config value from a specific config file
func getGitConfig(configFile, key string) string {
	cmd := exec.Command("git", "config", "--file", configFile, key)
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(output))
}

// ShowDirenvStatus shows the status of direnv
func ShowDirenvStatus() error {
	// Check if direnv is installed
	cmd := exec.Command("which", "direnv")
	if err := cmd.Run(); err != nil {
		fmt.Println("direnv is not installed")
		fmt.Println()
		fmt.Println("Install direnv:")
		fmt.Println("  macOS:  brew install direnv")
		fmt.Println("  Linux:  sudo apt install direnv")
		fmt.Println()
		fmt.Println("Then hook it to your shell:")
		fmt.Println("  bash:   eval \"$(direnv hook bash)\"")
		fmt.Println("  zsh:    eval \"$(direnv hook zsh)\"")
		return nil
	}

	fmt.Println("=== direnv Status ===")
	fmt.Println()

	// Run direnv status
	statusCmd := exec.Command("direnv", "status")
	statusCmd.Stdout = os.Stdout
	statusCmd.Stderr = os.Stderr
	return statusCmd.Run()
}
