package cli

import (
	"github.com/neverprepared/shell-profile-manager/internal/ui"
)

// Re-export color constants and functions for convenience
const (
	ColorReset  = ui.ColorReset
	ColorRed    = ui.ColorRed
	ColorGreen  = ui.ColorGreen
	ColorYellow = ui.ColorYellow
	ColorBlue   = ui.ColorBlue
	ColorCyan   = ui.ColorCyan
)

func PrintError(msg string) {
	ui.PrintError(msg)
}

func PrintSuccess(msg string) {
	ui.PrintSuccess(msg)
}

func PrintInfo(msg string) {
	ui.PrintInfo(msg)
}

func PrintWarning(msg string) {
	ui.PrintWarning(msg)
}
