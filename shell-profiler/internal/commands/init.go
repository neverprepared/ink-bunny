package commands

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/neverprepared/shell-profile-manager/internal/config"
	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

type InitOptions struct {
	ProfilesDir string
	Force       bool
	Interactive bool
}

// InitConfig initializes the profile manager configuration
func InitConfig(opts InitOptions) error {
	// Check if config already exists
	configPath, err := config.GetConfigPath()
	if err != nil {
		return err
	}

	if _, err := os.Stat(configPath); err == nil && !opts.Force {
		ui.PrintWarning("Configuration file already exists")
		fmt.Printf("  Location: %s\n", configPath)
		fmt.Println()
		fmt.Print("Overwrite existing configuration? [y/N]: ")

		reader := bufio.NewReader(os.Stdin)
		confirmation, err := reader.ReadString('\n')
		if err != nil {
			return fmt.Errorf("failed to read input: %w", err)
		}
		confirmation = strings.TrimSpace(strings.ToLower(confirmation))

		if confirmation != "y" && confirmation != "yes" {
			ui.PrintInfo("Initialization cancelled")
			return nil
		}
	}

	// Interactive mode
	if opts.Interactive {
		if err := interactiveInit(&opts); err != nil {
			return err
		}
	}

	// Use defaults if not provided
	if opts.ProfilesDir == "" {
		defaultConfig, err := config.GetDefaultConfig()
		if err != nil {
			return fmt.Errorf("failed to get default config: %w", err)
		}
		opts.ProfilesDir = defaultConfig.ProfilesDir
	}

	// Expand paths
	opts.ProfilesDir = expandPath(opts.ProfilesDir)

	// Create directories if they don't exist
	if err := os.MkdirAll(opts.ProfilesDir, 0755); err != nil {
		return fmt.Errorf("failed to create profiles directory: %w", err)
	}

	// Save config
	cfg := &config.Config{
		ProfilesDir: opts.ProfilesDir,
	}

	if err := config.SaveConfig(cfg); err != nil {
		return fmt.Errorf("failed to save config: %w", err)
	}

	ui.PrintSuccess("Profile manager initialized successfully")
	fmt.Println()
	fmt.Printf("  Profiles directory: %s\n", opts.ProfilesDir)
	fmt.Printf("  Config file: %s\n", configPath)
	fmt.Println()
	ui.PrintInfo("Next steps:")
	fmt.Println("  1. Create your first profile: profile create my-profile")
	fmt.Println("  2. Navigate to it: cd <profiles-dir>/my-profile")
	fmt.Println("  3. Allow direnv: direnv allow")

	return nil
}

func interactiveInit(opts *InitOptions) error {
	fmt.Println("Profile Manager Initialization")
	fmt.Println()

	// Get profiles directory
	defaultConfig, err := config.GetDefaultConfig()
	if err != nil {
		return fmt.Errorf("failed to get default config: %w", err)
	}
	fmt.Printf("Profiles directory [default: %s]: ", defaultConfig.ProfilesDir)
	reader := bufio.NewReader(os.Stdin)
	input, err := reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("failed to read input: %w", err)
	}
	input = strings.TrimSpace(input)

	if input == "" {
		opts.ProfilesDir = defaultConfig.ProfilesDir
	} else {
		opts.ProfilesDir = input
	}

	fmt.Println()
	return nil
}

// expandPath expands ~ and environment variables in a path
func expandPath(path string) string {
	// Expand ~
	if strings.HasPrefix(path, "~") {
		homeDir, err := os.UserHomeDir()
		if err == nil {
			path = filepath.Join(homeDir, path[1:])
		}
	}

	// Expand environment variables
	path = os.ExpandEnv(path)

	// Clean the path
	return filepath.Clean(path)
}
