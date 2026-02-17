package templates

import (
	"strings"
	"testing"
)

func TestRenderEnvrc(t *testing.T) {
	tests := []struct {
		name         string
		profileName  string
		templateType string
		wantContains []string
	}{
		{
			name:         "basic profile",
			profileName:  "test-profile",
			templateType: "basic",
			wantContains: []string{
				"# Workspace profile: test-profile",
				"# Template: basic",
				"export WORKSPACE_PROFILE=\"test-profile\"",
				"export WORKSPACE_HOME=\"$PWD\"",
				"PATH_add bin",
				"dotenv_if_exists \"$_sp_env\"",
				"dotenv_if_exists .envrc.local",
				"log_status \"Loaded workspace profile: $WORKSPACE_PROFILE\"",
				"echo \"   CLAUDE_CONFIG_DIR: $CLAUDE_CONFIG_DIR\"",
				"echo \"   Orchestration: Available\"",
				"echo \"   AWS Config: $AWS_CONFIG_FILE\"",
				"echo \"   Kubeconfig: $KUBECONFIG\"",
				"if [[ \"$TERM_PROGRAM\" == \"iTerm.app\" ]]; then",
				"# Basic: Gray (#7e7f80)",
				"echo -ne \"\\033]6;1;bg;red;brightness;126\\a\"",
				"echo -ne \"\\033]6;1;bg;green;brightness;127\\a\"",
				"echo -ne \"\\033]6;1;bg;blue;brightness;128\\a\"",
			},
		},
		{
			name:         "work profile",
			profileName:  "my-work",
			templateType: "work",
			wantContains: []string{
				"# Workspace profile: my-work",
				"# Template: work",
				"export WORKSPACE_PROFILE=\"my-work\"",
				"# Work: Green (#28c940)",
				"echo -ne \"\\033]1;[$WORKSPACE_PROFILE]\\007\"",
			},
		},
		{
			name:         "personal profile",
			profileName:  "my-personal",
			templateType: "personal",
			wantContains: []string{
				"# Workspace profile: my-personal",
				"# Template: personal",
				"# Personal: Blue (#19baff)",
				"echo -ne \"\\033]6;1;bg;red;brightness;25\\a\"",
				"echo -ne \"\\033]6;1;bg;green;brightness;186\\a\"",
				"echo -ne \"\\033]6;1;bg;blue;brightness;255\\a\"",
			},
		},
		{
			name:         "client profile",
			profileName:  "client-project",
			templateType: "client",
			wantContains: []string{
				"# Workspace profile: client-project",
				"# Template: client",
				"# Client: Orange (#ff9500)",
				"echo -ne \"\\033]6;1;bg;red;brightness;255\\a\"",
				"echo -ne \"\\033]6;1;bg;green;brightness;149\\a\"",
				"echo -ne \"\\033]6;1;bg;blue;brightness;0\\a\"",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := RenderEnvrc(tt.profileName, tt.templateType)
			if err != nil {
				t.Errorf("RenderEnvrc() error = %v", err)
				return
			}

			for _, want := range tt.wantContains {
				if !strings.Contains(got, want) {
					t.Errorf("RenderEnvrc() missing expected content: %q", want)
				}
			}

			// Verify it starts with shebang
			if !strings.HasPrefix(got, "#!/usr/bin/env bash") {
				t.Error("RenderEnvrc() should start with shebang")
			}
		})
	}
}

func TestRenderEnv(t *testing.T) {
	tests := []struct {
		name         string
		profileName  string
		templateType string
		wantContains []string
	}{
		{
			name:         "basic env file",
			profileName:  "test-profile",
			templateType: "basic",
			wantContains: []string{
				"# Environment variables for workspace profile: test-profile",
				"# Template: basic",
				"GIT_CONFIG_GLOBAL=\"$WORKSPACE_HOME/.gitconfig\"",
				"GIT_SSH_COMMAND=\"ssh -F $WORKSPACE_HOME/.ssh/config\"",
				"XDG_CONFIG_HOME=\"$WORKSPACE_HOME/.config\"",
				"AWS_CONFIG_FILE=\"$WORKSPACE_HOME/.aws/config\"",
				"KUBECONFIG=\"$WORKSPACE_HOME/.kube/config\"",
				"CLAUDE_CONFIG_DIR=\"$WORKSPACE_HOME/.config/claude\"",
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := RenderEnv(tt.profileName, tt.templateType)
			if err != nil {
				t.Errorf("RenderEnv() error = %v", err)
				return
			}

			for _, want := range tt.wantContains {
				if !strings.Contains(got, want) {
					t.Errorf("RenderEnv() missing expected content: %q", want)
				}
			}
		})
	}
}

func TestRenderGitconfig(t *testing.T) {
	tests := []struct {
		name         string
		profileName  string
		templateType string
		gitName      string
		gitEmail     string
		wantContains []string
		wantName     string
		wantEmail    string
	}{
		{
			name:         "with git credentials",
			profileName:  "test-profile",
			templateType: "personal",
			gitName:      "John Doe",
			gitEmail:     "john@example.com",
			wantContains: []string{
				"# Git configuration for workspace profile: test-profile",
				"# Template: personal",
				"# Personal project settings",
				"[user]",
				"[alias]",
			},
			wantName:  "John Doe",
			wantEmail: "john@example.com",
		},
		{
			name:         "work template",
			profileName:  "work-profile",
			templateType: "work",
			gitName:      "Jane Smith",
			gitEmail:     "jane@company.com",
			wantContains: []string{
				"# Work project settings",
				"# gpgsign = true",
			},
			wantName:  "Jane Smith",
			wantEmail: "jane@company.com",
		},
		{
			name:         "client template",
			profileName:  "client-profile",
			templateType: "client",
			gitName:      "",
			gitEmail:     "",
			wantContains: []string{
				"# Client project settings",
			},
			wantName:  "Your Name",
			wantEmail: "your.email@example.com",
		},
		{
			name:         "defaults when empty",
			profileName:  "test",
			templateType: "basic",
			gitName:      "",
			gitEmail:     "",
			wantContains: []string{
				"[user]",
			},
			wantName:  "Your Name",
			wantEmail: "your.email@example.com",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := RenderGitconfig(tt.profileName, tt.templateType, tt.gitName, tt.gitEmail)
			if err != nil {
				t.Errorf("RenderGitconfig() error = %v", err)
				return
			}

			for _, want := range tt.wantContains {
				if !strings.Contains(got, want) {
					t.Errorf("RenderGitconfig() missing expected content: %q", want)
				}
			}

			// Verify name and email
			if !strings.Contains(got, "name = "+tt.wantName) {
				t.Errorf("RenderGitconfig() missing expected name: %q", tt.wantName)
			}
			if !strings.Contains(got, "email = "+tt.wantEmail) {
				t.Errorf("RenderGitconfig() missing expected email: %q", tt.wantEmail)
			}
		})
	}
}
