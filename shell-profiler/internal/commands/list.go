package commands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type ListOptions struct {
	Verbose     bool
	ShowConfig  bool
	Interactive bool
}

func ListProfiles(profilesDir string, opts ListOptions) error {

	// Check if profiles directory exists
	if _, err := os.Stat(profilesDir); os.IsNotExist(err) {
		fmt.Printf("%sNo profiles directory found%s\n", ui.ColorYellow, ui.ColorReset)
		fmt.Println("Create your first profile with:")
		fmt.Println("  profile create my-profile")
		return nil
	}

	// Get all profile directories
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
		fmt.Printf("%sNo profiles found%s\n", ui.ColorYellow, ui.ColorReset)
		fmt.Println("Create your first profile with:")
		fmt.Println("  profile create my-profile")
		return nil
	}

	// Interactive mode - show selection menu
	if opts.Interactive {
		selected, err := ui.SelectProfile(profiles, "Select a profile:")
		if err != nil {
			return err
		}

		// Show detailed info for selected profile
		profileDir := filepath.Join(profilesDir, selected)
		return showProfileDetails(profileDir, selected, opts)
	}

	fmt.Printf("%s=== Workspace Profiles ===%s\n", ui.ColorBlue, ui.ColorReset)
	fmt.Println()

	// Check if currently in a profile
	currentProfile := os.Getenv("WORKSPACE_PROFILE")
	if currentProfile != "" {
		fmt.Printf("%sCurrently active profile: %s%s\n", ui.ColorGreen, currentProfile, ui.ColorReset)
		fmt.Printf("  Location: %s\n", os.Getenv("WORKSPACE_HOME"))
		fmt.Println()
	}

	// List profiles
	for _, profileName := range profiles {
		profileDir := filepath.Join(profilesDir, profileName)
		envrcFile := filepath.Join(profileDir, ".envrc")
		gitconfigFile := filepath.Join(profileDir, ".gitconfig")
		readmeFile := filepath.Join(profileDir, "README.md")

		// Profile header
		if currentProfile == profileName {
			fmt.Printf("%s● %s%s %s(active)%s\n", ui.ColorGreen, profileName, ui.ColorReset, ui.ColorYellow, ui.ColorReset)
		} else {
			fmt.Printf("%s○ %s%s\n", ui.ColorCyan, profileName, ui.ColorReset)
		}

		// Show path
		fmt.Printf("  %sPath:%s %s\n", ui.ColorBlue, ui.ColorReset, profileDir)

		// Check if .envrc exists and is allowed
		if _, err := os.Stat(envrcFile); err == nil {
			// Check direnv status
			if cmd := exec.Command("which", "direnv"); cmd.Run() == nil {
				statusCmd := exec.Command("direnv", "status")
				statusCmd.Dir = profileDir
				output, statusErr := statusCmd.Output()
				if statusErr == nil {
					if strings.Contains(string(output), "Found RC allowed true") {
						fmt.Printf("  %s✓ direnv allowed%s\n", ui.ColorGreen, ui.ColorReset)
					} else {
						fmt.Printf("  %s⚠ direnv not allowed%s (run: cd %s && direnv allow)\n", ui.ColorYellow, ui.ColorReset, profileDir)
					}
				}
			}
		} else {
			fmt.Printf("  %s⚠ Missing .envrc%s\n", ui.ColorYellow, ui.ColorReset)
		}

		// Show git configuration
		if _, err := os.Stat(gitconfigFile); err == nil {
			gitName := getGitConfig(gitconfigFile, "user.name")
			gitEmail := getGitConfig(gitconfigFile, "user.email")
			if gitName == "" {
				gitName = "Not set"
			}
			if gitEmail == "" {
				gitEmail = "Not set"
			}
			fmt.Printf("  %sGit:%s %s <%s>\n", ui.ColorBlue, ui.ColorReset, gitName, gitEmail)

			if opts.ShowConfig {
				fmt.Printf("    %sConfig:%s %s\n", ui.ColorBlue, ui.ColorReset, gitconfigFile)
			}
		} else {
			fmt.Printf("  %s⚠ Missing .gitconfig%s\n", ui.ColorYellow, ui.ColorReset)
		}

		// Verbose mode
		if opts.Verbose {
			// Check for README
			if _, err := os.Stat(readmeFile); err == nil {
				readmeContent, readErr := os.ReadFile(readmeFile)
				if readErr != nil {
					continue
				}
				lines := strings.Split(string(readmeContent), "\n")
				for _, line := range lines {
					if strings.HasPrefix(line, "Template:") {
						template := strings.TrimSpace(strings.TrimPrefix(line, "Template:"))
						fmt.Printf("  %sTemplate:%s %s\n", ui.ColorBlue, ui.ColorReset, template)
					}
					if strings.HasPrefix(line, "Created:") {
						created := strings.TrimSpace(strings.TrimPrefix(line, "Created:"))
						fmt.Printf("  %sCreated:%s %s\n", ui.ColorBlue, ui.ColorReset, created)
					}
				}
			}

			// Check for .env file
			envFile := filepath.Join(profileDir, ".env")
			if _, err := os.Stat(envFile); err == nil {
				content, readErr := os.ReadFile(envFile)
				if readErr != nil {
					continue
				}
				lines := strings.Split(string(content), "\n")
				nonEmptyLines := 0
				for _, line := range lines {
					if strings.TrimSpace(line) != "" && !strings.HasPrefix(strings.TrimSpace(line), "#") {
						nonEmptyLines++
					}
				}
				fmt.Printf("  %sEnvironment:%s .env file present (%d lines)\n", ui.ColorBlue, ui.ColorReset, nonEmptyLines)
			}

			// Count files in bin directory
			binDir := filepath.Join(profileDir, "bin")
			if entries, err := os.ReadDir(binDir); err == nil {
				execCount := 0
				for _, entry := range entries {
					if !entry.IsDir() {
						info, infoErr := entry.Info()
						if infoErr != nil {
							continue
						}
						if info.Mode()&0111 != 0 {
							execCount++
						}
					}
				}
				if execCount > 0 {
					fmt.Printf("  %sScripts:%s %d executable script(s) in bin/\n", ui.ColorBlue, ui.ColorReset, execCount)
				}
			}
		}

		fmt.Println()
	}

	// Summary
	fmt.Printf("%sTotal profiles: %d%s\n", ui.ColorBlue, len(profiles), ui.ColorReset)

	if !opts.Verbose {
		fmt.Println()
		fmt.Println("Run with --verbose for more details")
		fmt.Println("Run with --config to show git configuration paths")
	}

	return nil
}

func getGitConfig(configFile, key string) string {
	cmd := exec.Command("git", "config", "--file", configFile, key)
	output, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(output))
}

// showProfileDetails shows detailed information for a single profile
func showProfileDetails(profileDir, profileName string, opts ListOptions) error {
	fmt.Printf("%s=== Profile: %s ===%s\n", ui.ColorBlue, profileName, ui.ColorReset)
	fmt.Println()

	envrcFile := filepath.Join(profileDir, ".envrc")
	gitconfigFile := filepath.Join(profileDir, ".gitconfig")
	readmeFile := filepath.Join(profileDir, "README.md")

	// Show path
	fmt.Printf("  %sPath:%s %s\n", ui.ColorBlue, ui.ColorReset, profileDir)

	// Check if .envrc exists and is allowed
	if _, err := os.Stat(envrcFile); err == nil {
		// Check direnv status
		if cmd := exec.Command("which", "direnv"); cmd.Run() == nil {
			statusCmd := exec.Command("direnv", "status")
			statusCmd.Dir = profileDir
			output, statusErr := statusCmd.Output()
			if statusErr == nil {
				if strings.Contains(string(output), "Found RC allowed true") {
					fmt.Printf("  %s✓ direnv allowed%s\n", ui.ColorGreen, ui.ColorReset)
				} else {
					fmt.Printf("  %s⚠ direnv not allowed%s (run: cd %s && direnv allow)\n", ui.ColorYellow, ui.ColorReset, profileDir)
				}
			}
		}
	} else {
		fmt.Printf("  %s⚠ Missing .envrc%s\n", ui.ColorYellow, ui.ColorReset)
	}

	// Show git configuration
	if _, err := os.Stat(gitconfigFile); err == nil {
		gitName := getGitConfig(gitconfigFile, "user.name")
		gitEmail := getGitConfig(gitconfigFile, "user.email")
		if gitName == "" {
			gitName = "Not set"
		}
		if gitEmail == "" {
			gitEmail = "Not set"
		}
		fmt.Printf("  %sGit:%s %s <%s>\n", ui.ColorBlue, ui.ColorReset, gitName, gitEmail)

		if opts.ShowConfig {
			fmt.Printf("    %sConfig:%s %s\n", ui.ColorBlue, ui.ColorReset, gitconfigFile)
		}
	} else {
		fmt.Printf("  %s⚠ Missing .gitconfig%s\n", ui.ColorYellow, ui.ColorReset)
	}

	// Always show verbose info in interactive mode
	if opts.Verbose || opts.Interactive {
		// Check for README
		if _, err := os.Stat(readmeFile); err == nil {
			readmeContent, readErr := os.ReadFile(readmeFile)
			if readErr == nil {
				lines := strings.Split(string(readmeContent), "\n")
				for _, line := range lines {
					if strings.HasPrefix(line, "Template:") {
						template := strings.TrimSpace(strings.TrimPrefix(line, "Template:"))
						fmt.Printf("  %sTemplate:%s %s\n", ui.ColorBlue, ui.ColorReset, template)
					}
					if strings.HasPrefix(line, "Created:") {
						created := strings.TrimSpace(strings.TrimPrefix(line, "Created:"))
						fmt.Printf("  %sCreated:%s %s\n", ui.ColorBlue, ui.ColorReset, created)
					}
				}
			}
		}

		// Check for .env file
		envFile := filepath.Join(profileDir, ".env")
		if _, err := os.Stat(envFile); err == nil {
			content, readErr := os.ReadFile(envFile)
			if readErr != nil {
				// Continue without showing env file info
			} else {
				lines := strings.Split(string(content), "\n")
				nonEmptyLines := 0
				for _, line := range lines {
					if strings.TrimSpace(line) != "" && !strings.HasPrefix(strings.TrimSpace(line), "#") {
						nonEmptyLines++
					}
				}
				fmt.Printf("  %sEnvironment:%s .env file present (%d lines)\n", ui.ColorBlue, ui.ColorReset, nonEmptyLines)
			}
		}

		// Count files in bin directory
		binDir := filepath.Join(profileDir, "bin")
		if entries, err := os.ReadDir(binDir); err == nil {
			execCount := 0
			for _, entry := range entries {
				if !entry.IsDir() {
					info, infoErr := entry.Info()
					if infoErr != nil {
						continue
					}
					if info.Mode()&0111 != 0 {
						execCount++
					}
				}
			}
			if execCount > 0 {
				fmt.Printf("  %sScripts:%s %d executable script(s) in bin/\n", ui.ColorBlue, ui.ColorReset, execCount)
			}
		}
	}

	fmt.Println()
	return nil
}
