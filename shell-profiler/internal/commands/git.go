package commands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type GitOptions struct {
	ProfileName string
	Remote      string
	Force       bool
}

// InitGit initializes a git repository in the profile directory
func InitGit(profilesDir string, opts GitOptions) error {
	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// Check if profile exists
	if _, err := os.Stat(profileDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not exist at: %s", opts.ProfileName, profileDir)
	}

	// Check if already a git repo
	gitDir := filepath.Join(profileDir, ".git")
	if _, err := os.Stat(gitDir); err == nil {
		ui.PrintWarning("Profile is already a git repository")
		return nil
	}

	ui.PrintInfo(fmt.Sprintf("Initializing git repository for profile: %s", opts.ProfileName))

	// Initialize git repository
	cmd := exec.Command("git", "init")
	cmd.Dir = profileDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to initialize git repository: %w", err)
	}

	// Create initial commit if there are files
	cmd = exec.Command("git", "add", ".")
	cmd.Dir = profileDir
	if err := cmd.Run(); err != nil {
		// Not a fatal error if there's nothing to add
		ui.PrintWarning("No files to add to git")
	}

	cmd = exec.Command("git", "commit", "-m", "Initial commit: profile setup")
	cmd.Dir = profileDir
	if err := cmd.Run(); err != nil {
		// Not a fatal error if there's nothing to commit
		ui.PrintInfo("No changes to commit (this is normal for new profiles)")
	}

	// Add remote if provided
	if opts.Remote != "" {
		cmd = exec.Command("git", "remote", "add", "origin", opts.Remote)
		cmd.Dir = profileDir
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to add remote: %w", err)
		}
		ui.PrintSuccess(fmt.Sprintf("Added remote: %s", opts.Remote))
	}

	ui.PrintSuccess(fmt.Sprintf("Git repository initialized for profile: %s", opts.ProfileName))
	return nil
}

// PullGit pulls changes from the remote repository
func PullGit(profilesDir string, opts GitOptions) error {
	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// Check if profile exists
	if _, err := os.Stat(profileDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not exist at: %s", opts.ProfileName, profileDir)
	}

	// Check if it's a git repo
	gitDir := filepath.Join(profileDir, ".git")
	if _, err := os.Stat(gitDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' is not a git repository (run 'profile git init %s' first)", opts.ProfileName, opts.ProfileName)
	}

	ui.PrintInfo(fmt.Sprintf("Pulling changes for profile: %s", opts.ProfileName))

	// Check if remote exists
	cmd := exec.Command("git", "remote", "get-url", "origin")
	cmd.Dir = profileDir
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("no remote 'origin' configured (add with 'profile git remote %s <url>')", opts.ProfileName)
	}

	// Pull changes
	cmd = exec.Command("git", "pull", "origin", "main")
	cmd.Dir = profileDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	// Try main branch first, then master
	if err := cmd.Run(); err != nil {
		cmd = exec.Command("git", "pull", "origin", "master")
		cmd.Dir = profileDir
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to pull changes: %w", err)
		}
	}

	ui.PrintSuccess(fmt.Sprintf("Pulled changes for profile: %s", opts.ProfileName))
	return nil
}

// PushGit pushes local changes to the remote repository
func PushGit(profilesDir string, opts GitOptions) error {
	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// Check if profile exists
	if _, err := os.Stat(profileDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not exist at: %s", opts.ProfileName, profileDir)
	}

	// Check if it's a git repo
	gitDir := filepath.Join(profileDir, ".git")
	if _, err := os.Stat(gitDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' is not a git repository (run 'profile git init %s' first)", opts.ProfileName, opts.ProfileName)
	}

	ui.PrintInfo(fmt.Sprintf("Pushing changes for profile: %s", opts.ProfileName))

	// Check if remote exists
	cmd := exec.Command("git", "remote", "get-url", "origin")
	cmd.Dir = profileDir
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("no remote 'origin' configured (add with 'profile git remote %s <url>')", opts.ProfileName)
	}

	// Check for uncommitted changes
	cmd = exec.Command("git", "status", "--porcelain")
	cmd.Dir = profileDir
	output, statusErr := cmd.Output()
	if statusErr != nil {
		return fmt.Errorf("failed to check git status: %w", statusErr)
	}
	if len(output) > 0 {
		ui.PrintWarning("You have uncommitted changes. Committing them now...")

		// Add all changes
		cmd = exec.Command("git", "add", ".")
		cmd.Dir = profileDir
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to stage changes: %w", err)
		}

		// Commit
		cmd = exec.Command("git", "commit", "-m", "Update profile configuration")
		cmd.Dir = profileDir
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to commit changes: %w", err)
		}
	}

	// Get current branch
	cmd = exec.Command("git", "branch", "--show-current")
	cmd.Dir = profileDir
	branchOutput, branchErr := cmd.Output()
	if branchErr != nil {
		// Failed to get branch, default to main
		branchOutput = []byte("main")
	}
	branch := strings.TrimSpace(string(branchOutput))
	if branch == "" {
		branch = "main" // default
	}

	// Push changes
	pushArgs := []string{"push", "origin", branch}
	if opts.Force {
		pushArgs = append(pushArgs, "--force")
	}

	cmd = exec.Command("git", pushArgs...)
	cmd.Dir = profileDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to push changes: %w", err)
	}

	ui.PrintSuccess(fmt.Sprintf("Pushed changes for profile: %s", opts.ProfileName))
	return nil
}

// SyncGit syncs the profile (pull then push)
func SyncGit(profilesDir string, opts GitOptions) error {
	ui.PrintInfo(fmt.Sprintf("Syncing profile: %s", opts.ProfileName))

	// First pull
	if err := PullGit(profilesDir, opts); err != nil {
		// If pull fails because there's no remote, that's okay for sync
		if !strings.Contains(err.Error(), "no remote") {
			return fmt.Errorf("failed to pull: %w", err)
		}
		ui.PrintInfo("No remote configured, skipping pull")
	}

	// Then push
	if err := PushGit(profilesDir, opts); err != nil {
		// If push fails because there's no remote, that's okay for sync
		if !strings.Contains(err.Error(), "no remote") {
			return fmt.Errorf("failed to push: %w", err)
		}
		ui.PrintInfo("No remote configured, skipping push")
	}

	ui.PrintSuccess(fmt.Sprintf("Synced profile: %s", opts.ProfileName))
	return nil
}

// SetRemote sets or updates the git remote for a profile
func SetRemote(profilesDir string, opts GitOptions) error {
	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// Check if profile exists
	if _, err := os.Stat(profileDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not exist at: %s", opts.ProfileName, profileDir)
	}

	// Check if it's a git repo
	gitDir := filepath.Join(profileDir, ".git")
	if _, err := os.Stat(gitDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' is not a git repository (run 'profile git init %s' first)", opts.ProfileName, opts.ProfileName)
	}

	if opts.Remote == "" {
		return fmt.Errorf("remote URL is required")
	}

	ui.PrintInfo(fmt.Sprintf("Setting remote for profile: %s", opts.ProfileName))

	// Check if remote already exists
	cmd := exec.Command("git", "remote", "get-url", "origin")
	cmd.Dir = profileDir
	if err := cmd.Run(); err == nil {
		// Remote exists, update it
		cmd = exec.Command("git", "remote", "set-url", "origin", opts.Remote)
		cmd.Dir = profileDir
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to update remote: %w", err)
		}
		ui.PrintSuccess(fmt.Sprintf("Updated remote to: %s", opts.Remote))
	} else {
		// Remote doesn't exist, add it
		cmd = exec.Command("git", "remote", "add", "origin", opts.Remote)
		cmd.Dir = profileDir
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to add remote: %w", err)
		}
		ui.PrintSuccess(fmt.Sprintf("Added remote: %s", opts.Remote))
	}

	return nil
}

// GetGitStatus shows the git status of a profile (or all profiles if no name provided)
func GetGitStatus(profilesDir string, opts GitOptions) error {
	// If no profile name, show status for all profiles
	if opts.ProfileName == "" {
		entries, err := os.ReadDir(profilesDir)
		if err != nil {
			return fmt.Errorf("failed to read profiles directory: %w", err)
		}

		fmt.Printf("%s=== Git Status for All Profiles ===%s\n", ui.ColorBlue, ui.ColorReset)
		fmt.Println()

		foundAny := false
		for _, entry := range entries {
			if !entry.IsDir() || entry.Name() == ".git" {
				continue
			}

			profileDir := filepath.Join(profilesDir, entry.Name())
			gitDir := filepath.Join(profileDir, ".git")
			if _, err := os.Stat(gitDir); os.IsNotExist(err) {
				continue
			}

			foundAny = true
			fmt.Printf("%s=== %s ===%s\n", ui.ColorBlue, entry.Name(), ui.ColorReset)

			// Show git status for this profile
			cmd := exec.Command("git", "status", "--short")
			cmd.Dir = profileDir
			output, statusErr := cmd.Output()
			if statusErr == nil {
				if len(output) > 0 {
					fmt.Print(string(output))
				} else {
					fmt.Println("  (no changes)")
				}
			} else {
				fmt.Println("  (error getting status)")
			}

			// Show remote
			cmd = exec.Command("git", "remote", "get-url", "origin")
			cmd.Dir = profileDir
			if remoteOutput, err := cmd.Output(); err == nil {
				fmt.Printf("  Remote: %s", string(remoteOutput))
			} else {
				fmt.Println("  Remote: (none)")
			}
			fmt.Println()
		}

		if !foundAny {
			fmt.Println("No profiles with git repositories found")
		}
		return nil
	}

	profileDir := filepath.Join(profilesDir, opts.ProfileName)

	// Check if profile exists
	if _, err := os.Stat(profileDir); os.IsNotExist(err) {
		return fmt.Errorf("profile '%s' does not exist at: %s", opts.ProfileName, profileDir)
	}

	// Check if it's a git repo
	gitDir := filepath.Join(profileDir, ".git")
	if _, err := os.Stat(gitDir); os.IsNotExist(err) {
		fmt.Printf("Profile '%s' is not a git repository\n", opts.ProfileName)
		return nil
	}

	fmt.Printf("%s=== Git Status for Profile: %s ===%s\n", ui.ColorBlue, opts.ProfileName, ui.ColorReset)
	fmt.Println()

	// Show git status
	cmd := exec.Command("git", "status")
	cmd.Dir = profileDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to get git status: %w", err)
	}

	// Show remote info
	fmt.Println()
	fmt.Printf("%sRemote Information:%s\n", ui.ColorBlue, ui.ColorReset)
	cmd = exec.Command("git", "remote", "-v")
	cmd.Dir = profileDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Run() //nolint:errcheck // Ignore error - remote might not be configured

	return nil
}
