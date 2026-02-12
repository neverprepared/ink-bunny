package cli

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/neverprepared/shell-profile-manager/internal/commands"
	"github.com/neverprepared/shell-profile-manager/internal/profile"
	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type App struct {
	profilesDir string
}

func NewApp(profilesDir string) *App {
	return &App{
		profilesDir: profilesDir,
	}
}

// requireDirenv checks that direnv is installed and available on PATH.
// Returns an error with installation instructions if not found.
func (a *App) requireDirenv() error {
	_, err := exec.LookPath("direnv")
	if err != nil {
		return fmt.Errorf("direnv is required but not found in PATH\n\n  Install direnv:\n    brew install direnv    # macOS/Linux (Homebrew)\n    apt install direnv     # Debian/Ubuntu\n\n  Then add the shell hook to your shell config:\n    eval \"$(direnv hook bash)\"   # ~/.bashrc\n    eval \"$(direnv hook zsh)\"    # ~/.zshrc\n\n  See https://direnv.net/ for more details")
	}
	return nil
}

func (a *App) Run(args []string) error {
	if len(args) == 0 {
		a.showHelp()
		return nil
	}

	command := args[0]
	args = args[1:]

	// Commands that require direnv to be installed
	switch command {
	case "help", "--help", "-h", "init":
		// These commands don't require direnv
	default:
		if err := a.requireDirenv(); err != nil {
			return err
		}
	}

	switch command {
	case "init":
		return a.handleInit(args)
	case "create", "new", "add":
		return a.handleCreate(args)
	case "update", "upgrade":
		return a.handleUpdate(args)
	case "list", "ls":
		return a.handleList(args)
	case "select", "use":
		return a.handleSelect(args)
	case "delete", "remove", "rm":
		return a.handleDelete(args)
	case "restore":
		return a.handleRestore(args)
	case "info", "current", "show":
		return a.handleInfo(args)
	case "status":
		return a.handleStatus(args)
	case "sync":
		return a.handleSync(args)
	case "dotfiles":
		return a.handleDotfiles(args)
	case "help", "--help", "-h":
		a.showHelp()
		return nil
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", command)
		a.showHelp()
		return fmt.Errorf("unknown command: %s", command)
	}
}

func (a *App) handleInit(args []string) error {
	opts := commands.InitOptions{}

	// Parse arguments
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "-h", "--help":
			a.showInitHelp()
			return nil
		case "-f", "--force":
			opts.Force = true
		case "--profiles-dir":
			if i+1 < len(args) {
				opts.ProfilesDir = args[i+1]
				i++
			}
		case "--interactive", "-i":
			opts.Interactive = true
		}
	}

	return commands.InitConfig(opts)
}

func (a *App) handleCreate(args []string) error {
	opts := commands.CreateOptions{
		Template: "basic",
	}

	// Track if any non-interactive flags are provided
	hasNonInteractiveFlags := false

	// Parse arguments
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "-h", "--help":
			a.showCreateHelp()
			return nil
		case "-f", "--force":
			opts.Force = true
			hasNonInteractiveFlags = true
		case "-t", "--template":
			if i+1 < len(args) {
				opts.Template = args[i+1]
				i++
				hasNonInteractiveFlags = true
			}
		case "--git-name":
			if i+1 < len(args) {
				opts.GitName = args[i+1]
				i++
				hasNonInteractiveFlags = true
			}
		case "--git-email":
			if i+1 < len(args) {
				opts.GitEmail = args[i+1]
				i++
				hasNonInteractiveFlags = true
			}
		case "--interactive", "-i":
			opts.Interactive = true
		case "--no-interactive":
			opts.Interactive = false
			hasNonInteractiveFlags = true
		case "--dry-run":
			opts.DryRun = true
			hasNonInteractiveFlags = true
		case "--init-git":
			opts.InitGit = true
			hasNonInteractiveFlags = true
		case "--git-remote":
			if i+1 < len(args) {
				opts.GitRemote = args[i+1]
				opts.InitGit = true
				i++
				hasNonInteractiveFlags = true
			}
		default:
			if opts.ProfileName == "" && !strings.HasPrefix(arg, "-") {
				opts.ProfileName = arg
			}
		}
	}

	if opts.ProfileName == "" {
		return fmt.Errorf("profile name is required")
	}

	// If no non-interactive flags provided, enable interactive mode
	if !hasNonInteractiveFlags {
		opts.Interactive = true
	}

	return commands.CreateProfile(a.profilesDir, opts)
}

func (a *App) handleUpdate(args []string) error {
	opts := commands.UpdateOptions{}

	// Parse arguments
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "-h", "--help":
			a.showUpdateHelp()
			return nil
		case "-f", "--force":
			opts.Force = true
		case "--dry-run":
			opts.DryRun = true
		case "--no-backup":
			opts.NoBackup = true
		default:
			if opts.ProfileName == "" && !strings.HasPrefix(arg, "-") {
				opts.ProfileName = arg
			}
		}
	}

	// Profile name is optional - will show interactive selection if not provided
	return commands.UpdateProfile(a.profilesDir, opts)
}

func (a *App) handleList(args []string) error {
	opts := commands.ListOptions{
		Interactive: true, // Default to interactive
	}

	// Parse arguments
	for _, arg := range args {
		switch arg {
		case "-v", "--verbose":
			opts.Verbose = true
			opts.Interactive = false // Verbose disables interactive
		case "-c", "--config":
			opts.ShowConfig = true
			opts.Interactive = false // Config disables interactive
		case "-i", "--interactive":
			opts.Interactive = true
		case "--no-interactive":
			opts.Interactive = false
		case "-h", "--help":
			a.showListHelp()
			return nil
		}
	}

	return commands.ListProfiles(a.profilesDir, opts)
}

func (a *App) handleDelete(args []string) error {
	opts := commands.DeleteOptions{}

	// Parse arguments
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "-h", "--help":
			a.showDeleteHelp()
			return nil
		case "-f", "--force":
			opts.Force = true
		case "--dry-run":
			opts.DryRun = true
		case "--no-interactive":
			// This is handled in DeleteProfile - if profile name is provided, interactive is skipped
		default:
			if opts.ProfileName == "" && !strings.HasPrefix(arg, "-") {
				opts.ProfileName = arg
			}
		}
	}

	return commands.DeleteProfile(a.profilesDir, opts)
}

func (a *App) handleRestore(args []string) error {
	return fmt.Errorf("restore command is not yet implemented in Go")
}

func (a *App) handleSync(args []string) error {
	if len(args) == 0 {
		a.showSyncHelp()
		return nil
	}

	syncCommand := args[0]
	args = args[1:]

	// Help command doesn't need profile name
	if syncCommand == "help" || syncCommand == "-h" || syncCommand == "--help" {
		a.showSyncHelp()
		return nil
	}

	opts := commands.GitOptions{}

	// Parse common options
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "--force", "-f":
			opts.Force = true
		case "--remote":
			if i+1 < len(args) {
				opts.Remote = args[i+1]
				i++
			}
		case "-h", "--help":
			a.showSyncHelp()
			return nil
		default:
			if opts.ProfileName == "" && !strings.HasPrefix(arg, "-") {
				opts.ProfileName = arg
			}
		}
	}

	// Check for --no-interactive flag
	noInteractive := false
	for _, arg := range args {
		if arg == "--no-interactive" {
			noInteractive = true
			break
		}
	}

	// Status command can work without profile name (shows all profiles)
	if syncCommand == "status" && opts.ProfileName == "" {
		return commands.GetGitStatus(a.profilesDir, opts)
	}

	// For other commands, if no profile name provided and not --no-interactive, show interactive selection
	if opts.ProfileName == "" && !noInteractive {
		// Get list of profiles
		entries, err := os.ReadDir(a.profilesDir)
		if err != nil {
			return fmt.Errorf("failed to read profiles directory: %w", err)
		}

		var profiles []string
		for _, entry := range entries {
			if entry.IsDir() && entry.Name() != ".git" {
				profilePath := filepath.Join(a.profilesDir, entry.Name())
				envrcPath := filepath.Join(profilePath, ".envrc")
				if _, err := os.Stat(envrcPath); err == nil {
					profiles = append(profiles, entry.Name())
				}
			}
		}

		if len(profiles) == 0 {
			return fmt.Errorf("no profiles found")
		}

		selected, err := ui.SelectProfile(profiles, fmt.Sprintf("Select profile for sync %s:", syncCommand))
		if err != nil {
			return err
		}
		opts.ProfileName = selected
	}

	switch syncCommand {
	case "init":
		// Parse remote if provided
		for i := 0; i < len(args); i++ {
			if args[i] == "--remote" && i+1 < len(args) {
				opts.Remote = args[i+1]
				break
			}
		}
		return commands.InitGit(a.profilesDir, opts)
	case "pull":
		return commands.PullGit(a.profilesDir, opts)
	case "push":
		return commands.PushGit(a.profilesDir, opts)
	case "sync":
		return commands.SyncGit(a.profilesDir, opts)
	case "remote":
		// For remote command, the URL might be the last argument
		if opts.Remote == "" && len(args) > 0 {
			// Find the remote URL (last non-flag argument)
			for i := len(args) - 1; i >= 0; i-- {
				if !strings.HasPrefix(args[i], "-") && args[i] != opts.ProfileName {
					opts.Remote = args[i]
					break
				}
			}
		}
		return commands.SetRemote(a.profilesDir, opts)
	case "status":
		return commands.GetGitStatus(a.profilesDir, opts)
	default:
		fmt.Fprintf(os.Stderr, "Unknown sync command: %s\n\n", syncCommand)
		a.showSyncHelp()
		return fmt.Errorf("unknown sync command: %s", syncCommand)
	}
}

func (a *App) handleInfo(_args []string) error {
	// This can be implemented in Go since it reads environment variables
	pm := profile.NewManager(a.profilesDir)
	return pm.ShowInfo()
}

func (a *App) handleSelect(args []string) error {
	opts := commands.SelectOptions{}

	// Parse arguments
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "-h", "--help":
			a.showSelectHelp()
			return nil
		case "--allow-direnv":
			opts.AllowDirenv = true
		default:
			if opts.ProfileName == "" && !strings.HasPrefix(arg, "-") {
				opts.ProfileName = arg
			}
		}
	}

	return commands.SelectProfile(a.profilesDir, opts)
}

func (a *App) handleStatus(_args []string) error {
	// Check if direnv is installed and show status
	return profile.ShowDirenvStatus()
}

func (a *App) handleDotfiles(args []string) error {
	if len(args) == 0 {
		a.showDotfilesHelp()
		return nil
	}

	subcommand := args[0]
	args = args[1:]

	opts := commands.DotfilesOptions{}

	// Parse common options
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "--profile", "-p":
			if i+1 < len(args) {
				opts.ProfileName = args[i+1]
				i++
			}
		case "--file", "-f":
			if i+1 < len(args) {
				opts.FileName = args[i+1]
				i++
			}
		case "--editor", "-e":
			if i+1 < len(args) {
				opts.Editor = args[i+1]
				i++
			}
		case "-h", "--help":
			a.showDotfilesHelp()
			return nil
		default:
			// First non-flag argument could be profile name
			if opts.ProfileName == "" && !strings.HasPrefix(arg, "-") {
				opts.ProfileName = arg
			}
		}
	}

	switch subcommand {
	case "list", "ls":
		return commands.ListDotfiles(a.profilesDir, opts)
	case "edit", "e":
		return commands.EditDotfile(a.profilesDir, opts)
	case "help", "-h", "--help":
		a.showDotfilesHelp()
		return nil
	default:
		fmt.Fprintf(os.Stderr, "Unknown dotfiles command: %s\n\n", subcommand)
		a.showDotfilesHelp()
		return fmt.Errorf("unknown dotfiles command: %s", subcommand)
	}
}

func (a *App) showHelp() {
	helpText := `Workspace Profile Manager

Manage workspace profiles with direnv for environment-specific configurations.

Usage: shell-profiler <command> [arguments]

Commands:
    init [options]             Initialize the profile manager configuration
        Options:
            --profiles-dir <path>    Set profiles directory path
            --interactive            Interactive setup
            --force                  Overwrite existing configuration

    create <name> [options]     Create a new workspace profile
        Options:
            --template <type>       Use template: personal, work, client, basic
            --git-name <name>       Set git user name
            --git-email <email>     Set git user email
            --interactive           Interactive setup (default if no flags provided)
            --no-interactive        Disable interactive mode
            --force                 Overwrite existing profile

    update [name] [options]     Update an existing profile with new features
        Options:
            --dry-run              Preview changes without applying
            --force                 Overwrite existing files
            --no-backup            Skip creating backup
        Note: Interactive selection by default if name is omitted

    select [name] [options]     Select and switch to a profile
        Options:
            --allow-direnv          Automatically allow direnv for selected profile
        Note: Interactive selection if name is omitted

    list [options]              List all workspace profiles
        Options:
            --verbose               Show detailed information (disables interactive)
            --config                Show git configuration (disables interactive)
            --no-interactive         Disable interactive mode
        Note: Interactive by default unless flags are provided

    delete [name] [options]     Delete a workspace profile
        Options:
            --force                 Skip confirmation prompt (disables interactive)
            --dry-run              Preview deletion without deleting (disables interactive)
            --no-interactive        Disable interactive mode
        Note: Interactive selection by default if name is omitted

    restore <name> [options]    Restore a profile from backup
        Options:
            --force                 Skip confirmation prompt
            --dry-run              Preview restore without restoring
            --file <file>           Restore only a specific file
            --backup-date <date>    Restore from specific dated backup

    info                        Show information about the current profile
    status                      Show direnv status
    dotfiles <command> [name]    Manage shell-profiler dotfiles
        Commands:
            list                    List all dotfiles in a profile
            edit                    Edit a dotfile interactively
        Options:
            --profile, -p <name>    Profile name (interactive if omitted)
            --file, -f <name>       File name (interactive if omitted)
            --editor, -e <name>     Editor to use (default: $EDITOR or vim)
        Note: Interactive by default if profile/file name is omitted
    sync <command> [name]       Sync operations for profiles
        Commands:
            init [--remote <url>]    Initialize repository
            pull                     Pull changes from remote
            push [--force]          Push changes to remote
            sync                    Pull then push (sync)
            remote <url>            Set or update remote URL
            status                  Show sync status
        Options:
            --no-interactive         Disable interactive shell-profiler selection
        Note: Interactive selection by default if name is omitted (except status)
    help                        Show this help message

Examples:
    # Create interactively (default behavior)
    shell-profiler create my-project

    # Create with specific options (disables interactive)
    shell-profiler create my-project --git-name "John Doe" --git-email "john@example.com"

    # Force interactive even with some flags
    shell-profiler create my-project --template work --interactive

    # Interactive shell-profiler selection (default)
    shell-profiler list

    # List all profiles (non-interactive)
    shell-profiler list --verbose

    # Select a profile to switch to
    shell-profiler select
    shell-profiler select my-project

    # Delete a profile
    shell-profiler delete old-project

    # Restore from backup (will list available backups)
    shell-profiler restore my-project
    shell-profiler restore my-project --backup-date 2024-11-29_14-30-45
    shell-profiler restore my-project --file .envrc

    # Show current shell-profiler info
    shell-profiler info

    # Manage dotfiles (interactive by default)
    shell-profiler dotfiles list              # Interactive shell-profiler selection
    shell-profiler dotfiles list my-project  # List dotfiles in specific profile
    shell-profiler dotfiles edit              # Interactive profile and file selection
    shell-profiler dotfiles edit my-project   # Interactive file selection
    shell-profiler dotfiles edit my-project .gitconfig  # Edit specific file

    # Sync operations (interactive selection if name omitted)
    shell-profiler sync pull              # Interactive selection
    shell-profiler sync push              # Interactive selection
    shell-profiler sync init my-project --remote https://github.com/user/my-project.git
    shell-profiler sync pull my-project
    shell-profiler sync push my-project
    shell-profiler sync sync my-project
    shell-profiler sync status my-project

Getting Started:
    1. Initialize:          shell-profiler init (or shell-profiler init --interactive)
    2. Create a profile:    shell-profiler create my-project --interactive
    3. Navigate to it:      cd <profiles-dir>/my-project
    4. Allow direnv:        direnv allow
    5. Verify:              shell-profiler info

For more information, see:
    - docs/QUICKSTART.md - Quick start guide
    - README.md          - Full documentation
    - docs/examples/     - Example configurations
`
	fmt.Print(helpText)
}

func (a *App) showSyncHelp() {
	helpText := `Sync Operations for Profiles

Usage: shell-profiler sync <command> [profile-name] [options]

Commands:
    init [--remote <url>]    Initialize repository in profile directory
        Options:
            --remote <url>       Add remote URL during initialization
        Note: If profile-name is omitted, interactive selection will be shown

    pull                     Pull changes from remote repository
        Note: Requires remote to be configured
        Note: If profile-name is omitted, interactive selection will be shown

    push [--force]          Push local changes to remote repository
        Options:
            --force              Force push (use with caution)
        Note: Automatically commits uncommitted changes
        Note: If profile-name is omitted, interactive selection will be shown

    sync                    Sync profile (pull then push)
        Note: Handles cases where remote is not configured
        Note: If profile-name is omitted, interactive selection will be shown

    remote <url>            Set or update the remote URL
        Arguments:
            <url>                Remote URL (required)
        Note: If profile-name is omitted, interactive selection will be shown

    status                  Show sync status and remote information
        Note: If profile-name is omitted, shows status for all profiles

Examples:
    # Initialize repository
    shell-profiler sync init my-project

    # Initialize with remote
    shell-profiler sync init my-project --remote https://github.com/user/my-project.git

    # Pull latest changes
    shell-profiler sync pull my-project

    # Push local changes
    shell-profiler sync push my-project

    # Sync (pull then push)
    shell-profiler sync sync my-project

    # Set remote URL
    shell-profiler sync remote my-project https://github.com/user/my-project.git

    # Check sync status
    shell-profiler sync status my-project

Notes:
    - Profiles are assumed to be in private repositories
    - Local files created by 'shell-profiler create' are not affected
    - Uncommitted changes are automatically committed before push
    - Sync will pull then push, handling missing remotes gracefully
`
	fmt.Print(helpText)
}

func (a *App) showCreateHelp() {
	helpText := `Usage: shell-profiler create <profile-name> [options]

Create a new workspace profile with direnv configuration.

Arguments:
    profile-name        Name of the profile to create (required)

Options:
    -h, --help          Show this help message
    -f, --force         Overwrite existing profile if it exists
    -t, --template      Use a specific template: personal, work, or client
                        (default: basic)
    --git-name NAME     Set git user.name in .gitconfig
    --git-email EMAIL   Set git user.email in .gitconfig
    --interactive       Prompt for all configuration values
    --dry-run          Show what would be created without creating it
    --init-git         Initialize git repository after creation
    --git-remote <url> Initialize git repository with remote URL

Examples:
    # Create a basic profile
    shell-profiler create my-project

    # Create a work profile with git configuration
    shell-profiler create acme-corp --template work \\
        --git-name "John Doe" \\
        --git-email "john.doe@acme.com"

    # Interactive setup
    shell-profiler create my-project --interactive

    # Preview what would be created
    shell-profiler create my-project --dry-run

    # Create with git initialization
    shell-profiler create my-project --init-git
    shell-profiler create my-project --git-remote https://github.com/user/my-project.git

Templates:
    personal    - Personal projects with minimal configuration
    work        - Work projects with corporate settings
    client      - Client projects with isolated credentials
    basic       - Minimal configuration (default)

Secrets Management:
    Profiles include a .env.secrets.tpl file for 1Password integration.
    Store secrets as op:// references (safe to commit), resolved at runtime
    by "op inject" in .envrc. See .env.secrets.tpl for usage instructions.
`
	fmt.Print(helpText)
}

func (a *App) showSelectHelp() {
	helpText := `Usage: shell-profiler select [profile-name] [options]

Select and switch to a workspace profile.

This command helps you select a profile and provides instructions on how to
activate it. The profile is activated by changing to its directory, which
automatically loads the profile's environment via direnv.

Arguments:
    profile-name        Name of the profile to select (optional - interactive selection if omitted)

Options:
    -h, --help          Show this help message
    --allow-direnv      Automatically allow direnv for the selected profile

Examples:
    # Interactive selection
    shell-profiler select

    # Select specific profile
    shell-profiler select my-project

    # Select and allow direnv automatically
    shell-profiler select my-project --allow-direnv

After selection, you'll see instructions to activate the profile:
    cd <profile-path>
    direnv allow  # (first time only)
`
	fmt.Print(helpText)
}

func (a *App) showListHelp() {
	helpText := `Usage: shell-profiler list [options]

List all workspace profiles with their configurations.

Interactive mode is enabled by default. Use flags to disable it.

Options:
    -h, --help          Show this help message
    -v, --verbose       Show detailed information (disables interactive)
    -c, --config        Show git configuration (disables interactive)
    --no-interactive    Disable interactive mode

Examples:
    shell-profiler list                # Interactive selection menu (default)
    shell-profiler list --verbose      # Show detailed information for all profiles
    shell-profiler list --config       # Show git configuration for all profiles
    shell-profiler list --no-interactive  # List all profiles without interactive menu
`
	fmt.Print(helpText)
}

func (a *App) showDeleteHelp() {
	helpText := `Usage: shell-profiler delete [profile-name] [options]

Delete a workspace profile and all its files.

Interactive selection is enabled by default if profile name is omitted.

Arguments:
    profile-name        Name of the profile to delete (optional - interactive selection if omitted)

Options:
    -h, --help          Show this help message
    -f, --force         Skip confirmation prompt (disables interactive)
    --dry-run          Show what would be deleted without deleting (disables interactive)
    --no-interactive    Disable interactive mode

Examples:
    # Interactive selection (default)
    shell-profiler delete

    # Delete a profile (with confirmation)
    shell-profiler delete old-project

    # Delete without confirmation
    shell-profiler delete old-project --force

    # Preview what would be deleted
    shell-profiler delete old-project --dry-run

Safety:
    - You will be prompted for confirmation unless --force is used
    - The profile directory and all its contents will be deleted
    - This operation cannot be undone
`
	fmt.Print(helpText)
}

func (a *App) showDotfilesHelp() {
	helpText := `Usage: shell-profiler dotfiles <command> [profile-name] [options]

Manage dotfiles in workspace profiles.

Commands:
    list, ls              List all dotfiles in a profile
    edit, e                Edit a dotfile interactively

Options:
    -h, --help            Show this help message
    -p, --profile <name>  Profile name (interactive selection if omitted)
    -f, --file <name>      File name (interactive selection if omitted)
    -e, --editor <name>   Editor to use (default: $EDITOR, $VISUAL, or vim)

Examples:
    # Interactive profile and file selection
    shell-profiler dotfiles list
    shell-profiler dotfiles edit

    # List dotfiles in specific profile
    shell-profiler dotfiles list my-project

    # Edit specific file (interactive shell-profiler selection)
    shell-profiler dotfiles edit --file .gitconfig

    # Edit specific file in specific profile
    shell-profiler dotfiles edit my-project .gitconfig

    # Use custom editor
    shell-profiler dotfiles edit my-project .envrc --editor code

Supported Dotfiles:
    .envrc                    - direnv configuration
    .gitconfig                - Git configuration
    .gitignore                - Git ignore patterns
    .ssh/config               - SSH client configuration
    .aws/config               - AWS CLI configuration
    .aws/credentials          - AWS credentials
    .azure/config             - Azure CLI configuration
    .azure/clouds.config      - Azure CLI cloud configuration
    .gcloud/configurations   - Google Cloud SDK configurations
    .gcloud/credentials      - Google Cloud SDK credentials
    .config/claude          - Claude Code configuration
    .config/gemini          - Gemini CLI configuration
    .kube/config              - Kubernetes configuration
    .terraformrc              - Terraform CLI configuration
    .config/1Password/agent.toml - 1Password SSH agent config
    .env                      - Environment variables (non-secret config)
    .env.secrets.tpl          - 1Password secret references (op:// URIs, safe to commit)
    .env.example              - Environment variables template
    .envrc.local              - Local direnv overrides

Note: Interactive mode is enabled by default if profile or file name is omitted.
`
	fmt.Print(helpText)
}

func (a *App) showUpdateHelp() {
	helpText := `Usage: shell-profiler update [profile-name] [options]

Update an existing profile with new features and configurations.

This command adds missing directories, environment variables, and configuration
files to existing profiles. Useful when new features are added to the profile
manager (e.g., Azure CLI, Google Cloud SDK support).

Arguments:
    profile-name        Name of the profile to update (optional - interactive selection if omitted)

Options:
    -h, --help          Show this help message
    -f, --force         Overwrite existing files without prompting
    --dry-run          Preview changes without applying them
    --no-backup        Skip creating backup before updating

Examples:
    # Interactive selection
    shell-profiler update

    # Update specific profile
    shell-profiler update my-project

    # Preview changes without applying
    shell-profiler update my-project --dry-run

    # Update without creating backup
    shell-profiler update my-project --no-backup

What gets updated:
    - Missing directories (.azure, .gcloud, etc.)
    - Missing environment variables in .envrc
    - Missing patterns in .gitignore
    - SSH directory permissions

Backup:
    By default, a backup is created in .backups/update_<timestamp>/ before making changes.
    Use --no-backup to skip this.
`
	fmt.Print(helpText)
}

func (a *App) showInitHelp() {
	helpText := `Usage: shell-profiler init [options]

Initialize the profile manager configuration.

This command creates a ~/.profile-manager configuration file that stores
the path to your profiles directory. If not initialized, the tool will use
the default path: ~/workspaces/profiles

Options:
    -h, --help              Show this help message
    -f, --force             Overwrite existing configuration
    -i, --interactive       Interactive setup (prompt for paths)
    --profiles-dir <path>   Set profiles directory path

Examples:
    # Initialize with default path
    shell-profiler init

    # Interactive initialization
    shell-profiler init --interactive

    # Initialize with custom path
    shell-profiler init --profiles-dir ~/my-profiles

    # Overwrite existing configuration
    shell-profiler init --force

Configuration:
    The configuration is stored in ~/.profile-manager with the following format:
    
    profiles_dir=<path>
    
    You can edit this file manually if needed. Paths can use ~ for home directory
    and environment variables will be expanded.
`
	fmt.Print(helpText)
}
