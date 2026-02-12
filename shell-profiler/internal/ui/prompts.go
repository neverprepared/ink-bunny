package ui

import (
	"fmt"

	"github.com/AlecAivazis/survey/v2"
)

// SelectProfile prompts the user to select a profile from a list
func SelectProfile(profiles []string, message string) (string, error) {
	if len(profiles) == 0 {
		return "", fmt.Errorf("no profiles available")
	}

	var selected string
	prompt := &survey.Select{
		Message: message,
		Options: profiles,
	}

	err := survey.AskOne(prompt, &selected)
	if err != nil {
		return "", err
	}

	return selected, nil
}

// SelectTemplate prompts the user to select a template
func SelectTemplate() (string, error) {
	var selected string
	prompt := &survey.Select{
		Message: "Select template:",
		Options: []string{
			"basic - Minimal configuration",
			"personal - Personal projects",
			"work - Work projects",
			"client - Client projects",
		},
		Default: "basic - Minimal configuration",
	}

	err := survey.AskOne(prompt, &selected)
	if err != nil {
		return "", err
	}

	// Extract template name from selection
	switch selected {
	case "personal - Personal projects":
		return "personal", nil
	case "work - Work projects":
		return "work", nil
	case "client - Client projects":
		return "client", nil
	default:
		return "basic", nil
	}
}

// Input prompts the user for text input
func Input(message string, defaultVal string) (string, error) {
	var result string
	prompt := &survey.Input{
		Message: message,
		Default: defaultVal,
	}

	err := survey.AskOne(prompt, &result)
	if err != nil {
		return "", err
	}

	return result, nil
}

// Confirm prompts the user for yes/no confirmation
func Confirm(message string, defaultVal bool) (bool, error) {
	var result bool
	prompt := &survey.Confirm{
		Message: message,
		Default: defaultVal,
	}

	err := survey.AskOne(prompt, &result)
	if err != nil {
		return false, err
	}

	return result, nil
}

// MultiSelect prompts the user to select multiple options
func MultiSelect(message string, options []string) ([]string, error) {
	var selected []string
	prompt := &survey.MultiSelect{
		Message: message,
		Options: options,
	}

	err := survey.AskOne(prompt, &selected)
	if err != nil {
		return nil, err
	}

	return selected, nil
}
