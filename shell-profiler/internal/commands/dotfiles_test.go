package commands

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFormatFileSize(t *testing.T) {
	tests := []struct {
		size int64
		want string
	}{
		{0, "0 B"},
		{512, "512 B"},
		{1024, "1.0 KB"},
		{1536, "1.5 KB"},
		{1048576, "1.0 MB"},
		{1073741824, "1.0 GB"},
	}

	for _, tt := range tests {
		got := formatFileSize(tt.size)
		if got != tt.want {
			t.Errorf("formatFileSize(%d) = %q, want %q", tt.size, got, tt.want)
		}
	}
}

func TestFindDotfiles_KnownFiles(t *testing.T) {
	tmpDir := t.TempDir()

	// Create known dotfiles
	knownFiles := []string{".envrc", ".gitconfig", ".env"}
	for _, f := range knownFiles {
		if err := os.WriteFile(filepath.Join(tmpDir, f), []byte("test"), 0644); err != nil {
			t.Fatal(err)
		}
	}

	dotfiles := findDotfiles(tmpDir)

	// Build a map of found paths
	found := make(map[string]bool)
	for _, df := range dotfiles {
		rel, _ := filepath.Rel(tmpDir, df.Path)
		found[rel] = true
	}

	for _, f := range knownFiles {
		if !found[f] {
			t.Errorf("findDotfiles should find %q", f)
		}
	}

	// Known files should have descriptions
	for _, df := range dotfiles {
		rel, _ := filepath.Rel(tmpDir, df.Path)
		for _, kf := range knownFiles {
			if rel == kf && df.Description == "" {
				t.Errorf("known file %q should have a description", kf)
			}
		}
	}
}

func TestFindDotfiles_UnknownHiddenFiles(t *testing.T) {
	tmpDir := t.TempDir()

	// Create an unknown hidden file
	if err := os.WriteFile(filepath.Join(tmpDir, ".hidden-custom"), []byte("test"), 0644); err != nil {
		t.Fatal(err)
	}

	dotfiles := findDotfiles(tmpDir)

	found := false
	for _, df := range dotfiles {
		if filepath.Base(df.Path) == ".hidden-custom" {
			found = true
			if df.Description != "" {
				t.Error("unknown hidden file should have empty description")
			}
		}
	}
	if !found {
		t.Error("findDotfiles should find unknown hidden files")
	}
}

func TestFindDotfiles_SkipsGitDir(t *testing.T) {
	tmpDir := t.TempDir()

	// Create .git directory
	if err := os.MkdirAll(filepath.Join(tmpDir, ".git"), 0755); err != nil {
		t.Fatal(err)
	}

	dotfiles := findDotfiles(tmpDir)

	for _, df := range dotfiles {
		if filepath.Base(df.Path) == ".git" {
			t.Error("findDotfiles should skip .git directory")
		}
	}
}

func TestFindDotfiles_EmptyDir(t *testing.T) {
	tmpDir := t.TempDir()

	dotfiles := findDotfiles(tmpDir)

	if len(dotfiles) != 0 {
		t.Errorf("findDotfiles on empty dir should return 0 items, got %d", len(dotfiles))
	}
}
