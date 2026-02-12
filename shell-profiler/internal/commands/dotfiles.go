package commands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type DotfilesOptions struct {
	ProfileName string
	FileName    string
	Editor      string
}

// ListDotfiles lists all dotfiles in a profile
func ListDotfiles(profilesDir string, opts DotfilesOptions) error {
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

		selected, err := ui.SelectProfile(profiles, "Select profile to list dotfiles:")
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

	// Find all dotfiles
	dotfiles := findDotfiles(profileDir)

	if len(dotfiles) == 0 {
		ui.PrintInfo(fmt.Sprintf("No dotfiles found in profile '%s'", opts.ProfileName))
		return nil
	}

	fmt.Printf("%s=== Dotfiles in profile: %s ===%s\n", ui.ColorBlue, opts.ProfileName, ui.ColorReset)
	fmt.Println()

	for _, dotfile := range dotfiles {
		relPath, relErr := filepath.Rel(profileDir, dotfile.Path)
		if relErr != nil {
			relPath = dotfile.Path
		}
		fmt.Printf("  %s%s%s\n", ui.ColorCyan, relPath, ui.ColorReset)

		// Show file size
		info, err := os.Stat(dotfile.Path)
		if err == nil {
			size := info.Size()
			sizeStr := formatFileSize(size)
			fmt.Printf("    %sSize:%s %s\n", ui.ColorBlue, ui.ColorReset, sizeStr)
		}

		// Show last modified
		if err == nil {
			modTime := info.ModTime().Format("2006-01-02 15:04:05")
			fmt.Printf("    %sModified:%s %s\n", ui.ColorBlue, ui.ColorReset, modTime)
		}

		// Show description if available
		if dotfile.Description != "" {
			fmt.Printf("    %sDescription:%s %s\n", ui.ColorBlue, ui.ColorReset, dotfile.Description)
		}

		fmt.Println()
	}

	fmt.Printf("%sTotal: %d dotfile(s)%s\n", ui.ColorBlue, len(dotfiles), ui.ColorReset)

	return nil
}

// EditDotfile opens a dotfile for editing
func EditDotfile(profilesDir string, opts DotfilesOptions) error {
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

		selected, err := ui.SelectProfile(profiles, "Select profile:")
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

	// Find all dotfiles
	dotfiles := findDotfiles(profileDir)

	if len(dotfiles) == 0 {
		return fmt.Errorf("no dotfiles found in profile '%s'", opts.ProfileName)
	}

	// If no file name provided, show interactive selection
	if opts.FileName == "" {
		var fileOptions []string
		for _, dotfile := range dotfiles {
			relPath, relErr := filepath.Rel(profileDir, dotfile.Path)
			if relErr != nil {
				relPath = dotfile.Path
			}
			display := relPath
			if dotfile.Description != "" {
				display = fmt.Sprintf("%s - %s", relPath, dotfile.Description)
			}
			fileOptions = append(fileOptions, display)
		}

		selected, err := ui.SelectProfile(fileOptions, "Select dotfile to edit:")
		if err != nil {
			return err
		}

		// Extract the file path from the selection
		parts := strings.SplitN(selected, " - ", 2)
		opts.FileName = parts[0]
	}

	// Find the full path
	var targetPath string
	for _, dotfile := range dotfiles {
		relPath, relErr := filepath.Rel(profileDir, dotfile.Path)
		if relErr != nil {
			relPath = dotfile.Path
		}
		if relPath == opts.FileName || dotfile.Path == opts.FileName {
			targetPath = dotfile.Path
			break
		}
	}

	if targetPath == "" {
		return fmt.Errorf("dotfile '%s' not found in profile '%s'", opts.FileName, opts.ProfileName)
	}

	// Determine editor
	editor := opts.Editor
	if editor == "" {
		editor = os.Getenv("EDITOR")
		if editor == "" {
			editor = os.Getenv("VISUAL")
			if editor == "" {
				// Default to common editors
				if _, err := exec.LookPath("vim"); err == nil {
					editor = "vim"
				} else if _, err := exec.LookPath("nano"); err == nil {
					editor = "nano"
				} else if _, err := exec.LookPath("vi"); err == nil {
					editor = "vi"
				} else {
					return fmt.Errorf("no editor found. Set EDITOR or VISUAL environment variable")
				}
			}
		}
	}

	// Open editor
	ui.PrintInfo(fmt.Sprintf("Opening %s with %s...", opts.FileName, editor))
	fmt.Printf("  Path: %s\n", targetPath)
	fmt.Println()

	cmd := exec.Command(editor, targetPath)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to open editor: %w", err)
	}

	ui.PrintSuccess(fmt.Sprintf("Finished editing %s", opts.FileName))

	return nil
}

type DotfileInfo struct {
	Path        string
	Description string
}

func findDotfiles(profileDir string) []DotfileInfo {
	var dotfiles []DotfileInfo

	// Known dotfiles with descriptions
	knownFiles := map[string]string{
		".envrc":                       "direnv configuration - environment variables",
		".gitconfig":                   "Git configuration - user name, email, aliases",
		".gitignore":                   "Git ignore patterns",
		".ssh/config":                  "SSH client configuration",
		".aws/config":                  "AWS CLI configuration",
		".aws/credentials":             "AWS credentials (secrets)",
		".azure/config":                "Azure CLI configuration",
		".azure/clouds.config":         "Azure CLI cloud configuration",
		".gcloud/configurations":       "Google Cloud SDK configurations",
		".gcloud/credentials":          "Google Cloud SDK credentials",
		".config/claude":               "Claude Code configuration",
		".config/gemini":               "Gemini CLI configuration",
		".kube/config":                 "Kubernetes configuration",
		".terraformrc":                 "Terraform CLI configuration",
		".config/1Password/agent.toml": "1Password SSH agent configuration",
		".env":                         "Environment variables (secrets)",
		".env.example":                 "Environment variables template",
		".envrc.local":                 "Local direnv overrides",
	}

	// Check for known files and directories
	for relPath, description := range knownFiles {
		fullPath := filepath.Join(profileDir, relPath)
		if _, err := os.Stat(fullPath); err == nil {
			// Include both files and directories
			dotfiles = append(dotfiles, DotfileInfo{
				Path:        fullPath,
				Description: description,
			})
		}
	}

	// Also find any other hidden files/directories in the root
	entries, err := os.ReadDir(profileDir)
	if err == nil {
		for _, entry := range entries {
			name := entry.Name()
			// Skip if already found or if it's a directory we've already checked
			if !strings.HasPrefix(name, ".") {
				continue
			}

			// Skip common non-dotfile entries
			if name == "." || name == ".." || name == ".git" {
				continue
			}

			fullPath := filepath.Join(profileDir, name)

			// Check if we already have this file
			alreadyFound := false
			for _, existing := range dotfiles {
				if existing.Path == fullPath {
					alreadyFound = true
					break
				}
			}
			if alreadyFound {
				continue
			}

			// Add if it's a file
			if !entry.IsDir() {
				dotfiles = append(dotfiles, DotfileInfo{
					Path:        fullPath,
					Description: "",
				})
			}
		}
	}

	return dotfiles
}

func formatFileSize(size int64) string {
	const unit = 1024
	if size < unit {
		return fmt.Sprintf("%d B", size)
	}
	div, exp := int64(unit), 0
	for n := size / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(size)/float64(div), "KMGTPE"[exp])
}
