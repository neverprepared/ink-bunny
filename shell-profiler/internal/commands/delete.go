package commands

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type DeleteOptions struct {
	ProfileName string
	Force       bool
	DryRun      bool
}

func DeleteProfile(profilesDir string, opts DeleteOptions) error {
	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// If no profile name provided and not forced/dry-run, show interactive selection
	if opts.ProfileName == "" && !opts.Force && !opts.DryRun {
		// Get list of profiles
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
			return fmt.Errorf("no profiles found to delete")
		}

		selected, err := ui.SelectProfile(profiles, "Select profile to delete:")
		if err != nil {
			return err
		}
		opts.ProfileName = selected
	}

	// Check if profile exists
	if _, err := os.Stat(profileDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not exist at: %s", opts.ProfileName, profileDir)
	}

	// Check if currently in this profile
	currentProfile := os.Getenv("WORKSPACE_PROFILE")
	if currentProfile == opts.ProfileName {
		ui.PrintWarning("You are currently in this profile!")
		ui.PrintInfo("The profile will remain active until you leave the directory")
	}

	// Show what will be deleted
	ui.PrintInfo(fmt.Sprintf("Profile to delete: %s", opts.ProfileName))
	fmt.Printf("  Location: %s\n", profileDir)

	// Count files
	fileCount := 0
	dirCount := 0
	filepath.Walk(profileDir, func(_ string, info os.FileInfo, err error) error { //nolint:errcheck // Counting files, errors are not critical
		if err != nil {
			return nil
		}
		if info.IsDir() {
			dirCount++
		} else {
			fileCount++
		}
		return nil
	})

	fmt.Printf("  Files: %d\n", fileCount)
	fmt.Printf("  Directories: %d\n", dirCount)

	// List important files
	envFile := filepath.Join(profileDir, ".env")
	if _, err := os.Stat(envFile); err == nil {
		fmt.Printf("  %s⚠ Contains .env file (may have secrets)%s\n", ui.ColorYellow, ui.ColorReset)
	}

	binDir := filepath.Join(profileDir, "bin")
	if entries, err := os.ReadDir(binDir); err == nil {
		scriptCount := 0
		for _, entry := range entries {
			if !entry.IsDir() {
				info, infoErr := entry.Info()
				if infoErr != nil {
					continue
				}
				if info.Mode()&0111 != 0 {
					scriptCount++
				}
			}
		}
		if scriptCount > 0 {
			fmt.Printf("  %s⚠ Contains %d executable script(s)%s\n", ui.ColorYellow, scriptCount, ui.ColorReset)
		}
	}

	// Dry run
	if opts.DryRun {
		ui.PrintInfo("DRY RUN - Nothing will be deleted")
		fmt.Println()
		fmt.Println("Would delete:")
		count := 0
		filepath.Walk(profileDir, func(path string, info os.FileInfo, err error) error { //nolint:errcheck // Listing files for preview, errors are not critical
			if err != nil {
				return nil
			}
			if !info.IsDir() && count < 20 {
				fmt.Printf("  - %s\n", path)
				count++
			}
			return nil
		})
		if fileCount > 20 {
			fmt.Printf("  ... and %d more files\n", fileCount-20)
		}
		return nil
	}

	// Confirmation
	if !opts.Force {
		confirmed, err := ui.Confirm(
			fmt.Sprintf("This will permanently delete the profile '%s' and all its files! Are you sure?", opts.ProfileName),
			false,
		)
		if err != nil {
			return fmt.Errorf("failed to get confirmation: %w", err)
		}

		if !confirmed {
			ui.PrintInfo("Deletion cancelled")
			return nil
		}
	}

	// Delete profile
	ui.PrintInfo(fmt.Sprintf("Deleting profile: %s", opts.ProfileName))

	if err := os.RemoveAll(profileDir); err != nil {
		return fmt.Errorf("failed to delete profile: %w", err)
	}

	ui.PrintSuccess(fmt.Sprintf("Profile deleted: %s", opts.ProfileName))

	// Check if profiles directory is now empty
	entries, readErr := os.ReadDir(profilesDir)
	if readErr == nil {
		remainingProfiles := 0
		for _, entry := range entries {
			if entry.IsDir() && entry.Name() != ".git" {
				remainingProfiles++
			}
		}
		if remainingProfiles == 0 {
			ui.PrintInfo("No profiles remaining")
		}
	}

	return nil
}
