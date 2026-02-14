package commands

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDeleteProfile_MissingProfile(t *testing.T) {
	tmpDir := t.TempDir()

	err := DeleteProfile(tmpDir, DeleteOptions{
		ProfileName: "nonexistent",
		Force:       true,
	})
	if err == nil {
		t.Fatal("expected error for missing profile")
	}
	if !strings.Contains(err.Error(), "does not exist") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestDeleteProfile_ForceDeleteRemoves(t *testing.T) {
	tmpDir := t.TempDir()

	// Create a profile with some files
	profileDir := filepath.Join(tmpDir, "todelete")
	if err := os.MkdirAll(filepath.Join(profileDir, ".ssh"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(profileDir, ".envrc"), []byte("test"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(profileDir, ".gitconfig"), []byte("test"), 0644); err != nil {
		t.Fatal(err)
	}

	err := DeleteProfile(tmpDir, DeleteOptions{
		ProfileName: "todelete",
		Force:       true,
	})
	if err != nil {
		t.Fatalf("force delete should succeed: %v", err)
	}

	if _, err := os.Stat(profileDir); !os.IsNotExist(err) {
		t.Error("profile directory should be removed after force delete")
	}
}

func TestDeleteProfile_DryRunDoesNotDelete(t *testing.T) {
	tmpDir := t.TempDir()

	profileDir := filepath.Join(tmpDir, "drytest")
	if err := os.MkdirAll(profileDir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(profileDir, ".envrc"), []byte("test"), 0644); err != nil {
		t.Fatal(err)
	}

	err := DeleteProfile(tmpDir, DeleteOptions{
		ProfileName: "drytest",
		Force:       true,
		DryRun:      true,
	})
	if err != nil {
		t.Fatalf("dry run should succeed: %v", err)
	}

	if _, err := os.Stat(profileDir); err != nil {
		t.Error("dry run should not delete the profile directory")
	}
}

func TestDeleteProfile_EmptyNameWithForceNonexistentDir(t *testing.T) {
	// When profilesDir doesn't exist, empty name + Force should fail
	err := DeleteProfile("/nonexistent/profiles/dir", DeleteOptions{
		ProfileName: "ghost",
		Force:       true,
	})
	if err == nil {
		t.Fatal("expected error for nonexistent profile")
	}
	if !strings.Contains(err.Error(), "does not exist") {
		t.Errorf("unexpected error: %v", err)
	}
}
