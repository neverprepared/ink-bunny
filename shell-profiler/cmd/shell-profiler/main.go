package main

import (
	"fmt"
	"os"

	"github.com/neverprepared/shell-profile-manager/internal/cli"
	"github.com/neverprepared/shell-profile-manager/internal/config"
)

func main() {
	// Load configuration (uses defaults if config file doesn't exist)
	cfg, err := config.LoadConfig()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading configuration: %v\n", err)
		fmt.Fprintf(os.Stderr, "Run 'shell-profiler init' to set custom paths\n")
		os.Exit(1)
	}

	// Create CLI instance
	app := cli.NewApp(cfg.ProfilesDir)

	// Run the CLI
	if err := app.Run(os.Args[1:]); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
