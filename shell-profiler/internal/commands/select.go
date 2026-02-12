package commands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type SelectOptions struct {
	ProfileName string
	AllowDirenv bool
}

// SelectProfile allows the user to interactively select and switch to a profile
func SelectProfile(profilesDir string, opts SelectOptions) error {
	// Get list of profiles
	entries, err := os.ReadDir(profilesDir)
	if err != nil {
		return fmt.Errorf("failed to read profiles directory: %w", err)
	}

	var profiles []string
	profileDetails := make(map[string]string) // name -> path

	for _, entry := range entries {
		if entry.IsDir() && entry.Name() != ".git" {
			profilePath := filepath.Join(profilesDir, entry.Name())
			envrcPath := filepath.Join(profilePath, ".envrc")
			if _, err := os.Stat(envrcPath); err == nil {
				profiles = append(profiles, entry.Name())
				profileDetails[entry.Name()] = profilePath
			}
		}
	}

	if len(profiles) == 0 {
		return fmt.Errorf("no profiles found")
	}

	// If profile name provided, use it directly
	var selected string
	if opts.ProfileName != "" {
		selected = opts.ProfileName
		// Verify it exists
		if _, exists := profileDetails[selected]; !exists {
			return fmt.Errorf("profile '%s' does not exist", selected)
		}
	} else {
		// Interactive selection
		selected, err = ui.SelectProfile(profiles, "Select a profile to activate:")
		if err != nil {
			return err
		}
	}

	profilePath := profileDetails[selected]

	// Check if currently in this profile
	currentProfile := os.Getenv("WORKSPACE_PROFILE")
	if currentProfile == selected {
		ui.PrintInfo(fmt.Sprintf("You are already in profile '%s'", selected))
		fmt.Printf("  Location: %s\n", profilePath)
		return nil
	}

	// Show profile information
	fmt.Println()
	ui.PrintSuccess(fmt.Sprintf("Selected profile: %s", selected))
	fmt.Printf("  Location: %s\n", profilePath)

	// Check direnv status
	envrcPath := filepath.Join(profilePath, ".envrc")
	if _, err := os.Stat(envrcPath); err == nil {
		// Check if direnv is installed
		if cmd := exec.Command("which", "direnv"); cmd.Run() == nil {
			// Check if direnv is allowed
			statusCmd := exec.Command("direnv", "status")
			statusCmd.Dir = profilePath
			output, statusErr := statusCmd.Output()
			if statusErr != nil {
				// Direnv is installed but status check failed, continue anyway
				return nil
			}
			needsAllow := !strings.Contains(string(output), "Found RC allowed true")

			if needsAllow {
				fmt.Println()
				ui.PrintWarning("direnv needs to be allowed for this profile")
				if opts.AllowDirenv {
					// Try to allow direnv
					allowCmd := exec.Command("direnv", "allow")
					allowCmd.Dir = profilePath
					allowCmd.Stdout = os.Stdout
					allowCmd.Stderr = os.Stderr
					if err := allowCmd.Run(); err != nil {
						ui.PrintWarning(fmt.Sprintf("Failed to allow direnv: %v", err))
						fmt.Println("  You may need to run 'direnv allow' manually")
					} else {
						ui.PrintSuccess("direnv allowed")
					}
				} else {
					fmt.Println("  Run 'direnv allow' after changing to the directory")
				}
			}
		}
	}

	// Show instructions
	fmt.Println()
	ui.PrintInfo("To activate this profile:")
	fmt.Printf("  cd %s\n", profilePath)
	if opts.AllowDirenv {
		fmt.Println("  (direnv will be allowed automatically)")
	} else {
		fmt.Println("  direnv allow  # (first time only)")
	}
	fmt.Println()
	ui.PrintInfo("Or use this command:")
	fmt.Printf("  cd %s && direnv allow\n", profilePath)

	return nil
}
