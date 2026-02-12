package ui

import (
	"fmt"
	"os"
)

// ANSI color codes
const (
	ColorReset  = "\033[0m"
	ColorRed    = "\033[0;31m"
	ColorGreen  = "\033[0;32m"
	ColorYellow = "\033[1;33m"
	ColorBlue   = "\033[0;34m"
	ColorCyan   = "\033[0;36m"
)

func PrintError(msg string) {
	fmt.Fprintf(os.Stderr, "%sERROR: %s%s\n", ColorRed, msg, ColorReset)
}

func PrintSuccess(msg string) {
	fmt.Printf("%sSUCCESS: %s%s\n", ColorGreen, msg, ColorReset)
}

func PrintInfo(msg string) {
	fmt.Printf("%sINFO: %s%s\n", ColorBlue, msg, ColorReset)
}

func PrintWarning(msg string) {
	fmt.Printf("%sWARNING: %s%s\n", ColorYellow, msg, ColorReset)
}
