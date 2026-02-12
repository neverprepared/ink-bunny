# CLAUDE.md - Shell Profile Manager Development Guide

**Project**: Shell Profile Manager (`shell-profiler` CLI)
**Language**: Go 1.21+
**Type**: CLI Tool for workspace environment management
**Repository**: github.com/neverprepared/shell-profile-manager

## Project Overview

The Shell Profile Manager is a CLI tool that helps developers manage workspace-specific environment variables, git configurations, and dotfiles using direnv. It enables seamless context switching between personal, work, and client projects.

### Core Features
- Create and manage workspace profiles
- Automatic environment variable loading via direnv
- Profile-specific git configurations
- Dotfile management per workspace
- Interactive CLI with colored output

## Development Workflow

This project follows a multi-agent development approach with optional SpecKit integration for complex features.

### Standard Workflow (Simple Changes)
Use for: Bug fixes, minor features, documentation updates
1. Research → Requirements → Development → Testing → Review

### SpecKit Workflow (Complex Features)
Use for: New commands, architectural changes, major refactoring
1. Research → Specify → Clarify → Plan → Tasks → Implement → Test → Review

## Technology Stack

### Core Dependencies
- **CLI Framework**: Custom implementation using Go stdlib
- **Interactive Prompts**: github.com/AlecAivazis/survey/v2
- **Colors/UI**: Custom ANSI color implementation
- **External Tools**: direnv (required dependency)

### Development Tools
- **Testing**: Go standard testing package
- **Linting**: golangci-lint (recommended)
- **Formatting**: go fmt, goimports
- **Build**: Standard go build, Makefile included

## Project Structure

```
shell-profile-manager/
├── cmd/
│   └── shell-profiler/
│       └── main.go              # CLI entry point
├── internal/
│   ├── cli/
│   │   ├── app.go              # Main CLI application
│   │   └── colors.go           # Color constants
│   ├── commands/
│   │   ├── create.go           # Create new profiles
│   │   ├── delete.go           # Delete profiles
│   │   ├── dotfiles.go         # Manage dotfiles
│   │   ├── git.go              # Git integration
│   │   ├── init.go             # Initialize configuration
│   │   ├── list.go             # List profiles
│   │   ├── select.go           # Select active profile
│   │   └── update.go           # Update profiles
│   ├── config/
│   │   └── config.go           # Configuration management
│   ├── profile/
│   │   └── manager.go          # Profile business logic
│   └── ui/
│       ├── colors.go           # UI color utilities
│       └── prompts.go          # Interactive prompts
├── docs/                        # Documentation
├── .speckit/                    # SpecKit templates (optional)
├── specs/                       # Feature specifications (if using SpecKit)
├── go.mod                       # Go module definition
├── Makefile                     # Build automation
└── CLAUDE.md                    # This file
```

## Agent Workflow

### 1. Research Agent
**Role**: Search for existing solutions and best practices

**Tasks**:
- Search Go CLI best practices and patterns
- Research direnv integration techniques
- Find similar tools and their approaches
- Check for relevant Go libraries
- Suggest SpecKit workflow if feature is complex

**Output**: Recommendations with links to documentation

### 2. Requirements Gathering
**User provides**:
- Feature description or bug report
- Expected behavior
- Use cases and examples
- Performance/compatibility requirements
- Decision on SpecKit workflow (if applicable)

### 3. SME Agent - Development

#### Go-Specific Best Practices

**Code Style**:
- Follow standard Go idioms and conventions
- Use meaningful variable names (avoid single letters except standard i, j, k in loops)
- Keep functions focused and small
- Use early returns for error handling
- Document exported functions and types

**Error Handling**:
```go
// Good: Explicit error handling
if err := doSomething(); err != nil {
    return fmt.Errorf("failed to do something: %w", err)
}

// Avoid: Ignoring errors
_ = doSomething() // Only if truly safe to ignore
```

**Project Patterns**:
- Commands are in `internal/commands/` - one file per command
- Business logic in `internal/profile/manager.go`
- UI/UX helpers in `internal/ui/`
- Configuration in `internal/config/`
- Main CLI orchestration in `internal/cli/app.go`

**Adding a New Command**:
1. Create new file in `internal/commands/`: `feature.go`
2. Implement command function following existing pattern
3. Register command in `internal/cli/app.go`
4. Add help text and usage examples
5. Update documentation in `docs/`

**Testing Requirements**:
- Unit tests for business logic in `internal/profile/`
- Integration tests for commands (if applicable)
- Table-driven tests for multiple scenarios
- Test file naming: `*_test.go`

**Build & Run**:
```bash
# Development build
make build

# Run locally
./shell-profiler [command]

# Run tests
go test ./...

# Lint
golangci-lint run
```

### 4. QA Agent - Testing

**Test Coverage Areas**:
- Command execution (happy path)
- Error conditions (invalid input, missing files)
- Profile creation and deletion
- Dotfile operations
- Configuration loading
- Git integration
- Interactive prompts (mock stdin)

**Testing Approach**:
```go
func TestCreateProfile(t *testing.T) {
    tests := []struct {
        name        string
        profileName string
        wantErr     bool
    }{
        {"valid profile", "test-profile", false},
        {"empty name", "", true},
        {"invalid characters", "test/profile", true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := createProfile(tt.profileName)
            if (err != nil) != tt.wantErr {
                t.Errorf("createProfile() error = %v, wantErr %v", err, tt.wantErr)
            }
        })
    }
}
```

**Manual Testing**:
- Test on both macOS and Linux (if applicable)
- Verify direnv integration
- Test with real git operations
- Check colored output in different terminals
- Validate interactive prompts

**Quality Gates**:
- [ ] All tests pass: `go test ./...`
- [ ] No race conditions: `go test -race ./...`
- [ ] Code formatted: `go fmt ./...`
- [ ] Linter clean: `golangci-lint run`
- [ ] Build succeeds: `make build`
- [ ] Manual smoke tests pass
- [ ] Documentation updated

### 5. Final Review & Delivery

**Deliverables**:
- Working code with tests
- Updated documentation in `docs/`
- Updated README.md if user-facing changes
- CHANGELOG.md entry
- Git commits with clear messages

**Release Checklist**:
- [ ] Version bumped (if applicable)
- [ ] CHANGELOG.md updated
- [ ] All documentation reflects changes
- [ ] Tests pass on CI (if configured)
- [ ] Binary builds successfully

## SpecKit Integration (Optional)

### When to Use SpecKit

**Use SpecKit for**:
- New major commands (e.g., `shell-profiler sync`, `shell-profiler export`)
- Architectural changes (e.g., adding plugin system)
- Complex integrations (e.g., cloud sync, team sharing)
- Features with multiple implementation approaches

**Skip SpecKit for**:
- Bug fixes
- Minor UI improvements
- Documentation updates
- Simple command additions
- Refactoring without behavior changes

### SpecKit Setup

```bash
# Install SpecKit CLI
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# Initialize in project (already done if .speckit/ exists)
specify init . --ai claude
```

### SpecKit Directory Structure

```
.speckit/
├── constitution.md              # Project principles and standards
├── commands/
│   ├── specify.md              # Create specifications
│   ├── clarify.md              # Clarification workflow
│   ├── plan.md                 # Technical planning
│   ├── tasks.md                # Task breakdown
│   └── implement.md            # Implementation guide
└── templates/
    └── (SpecKit templates)

specs/
└── [feature-name]/
    ├── spec.md                 # Functional specification
    ├── plan.md                 # Technical plan
    ├── tasks.md                # Task list
    ├── research.md             # Technology research
    ├── data-model.md           # Data structures (if applicable)
    └── quickstart.md           # Validation scenarios
```

### SpecKit Workflow Example

**For new command: `shell-profiler backup`**

1. **Constitution** (if first time): Define code quality, testing standards
2. **Specify**: Create `specs/backup-command/spec.md`
   - What: Backup profiles to archive
   - Why: Disaster recovery, migration
   - User stories and acceptance criteria
3. **Clarify**: Address questions about compression, encryption, storage
4. **Plan**: Create `plan.md` with architecture, data model, API surface
5. **Tasks**: Break into actionable items in `tasks.md`
6. **Implement**: Build according to plan
7. **Test**: Validate against acceptance criteria in spec

## Code Quality Standards

### Go-Specific Rules

**Naming**:
- Packages: lowercase, single word (e.g., `profile`, not `profileManager`)
- Exported: PascalCase (e.g., `CreateProfile`)
- Unexported: camelCase (e.g., `validateName`)
- Interfaces: noun or verb+er (e.g., `Manager`, `Runner`)

**Documentation**:
- Document all exported functions, types, constants
- Use complete sentences
- Include examples for complex functions

**Error Messages**:
- Start lowercase (will be wrapped)
- Be specific and actionable
- Include context using `fmt.Errorf` with `%w`

**Concurrency**:
- Use mutexes for shared state
- Pass context.Context for cancellation
- Document goroutine lifecycle
- Test with `-race` flag

### Security Considerations

**This Project Specific**:
- Never log file contents (may contain secrets)
- Validate profile names (prevent path traversal)
- Don't execute arbitrary shell commands
- Warn users about `.envrc` security
- Use file permissions: 0755 for dirs, 0644 for files

**General Go Security**:
- Validate all user input
- Sanitize file paths
- Use crypto/rand for random data (not math/rand)
- Keep dependencies updated

## Dependencies Management

**Adding Dependencies**:
```bash
go get github.com/example/package@latest
go mod tidy
```

**Updating Dependencies**:
```bash
go get -u ./...
go mod tidy
```

**Dependency Guidelines**:
- Prefer stdlib when possible
- Choose well-maintained libraries
- Pin major versions
- Review security advisories: `go list -m -u all`

## Build & Release

**Build Binary**:
```bash
make build
# or
go build -o shell-profiler ./cmd/shell-profiler
```

**Cross-Platform Builds**:
```bash
# macOS
GOOS=darwin GOARCH=amd64 go build -o shell-profiler-darwin-amd64 ./cmd/shell-profiler

# Linux
GOOS=linux GOARCH=amd64 go build -o shell-profiler-linux-amd64 ./cmd/shell-profiler
```

**Release Process**:
1. Update version in code
2. Update CHANGELOG.md
3. Create git tag: `git tag v1.2.3`
4. Build binaries for all platforms
5. Create GitHub release with binaries

## Troubleshooting

**Build Issues**:
- Run `go mod tidy` to fix dependency issues
- Clear cache: `go clean -modcache`
- Update Go version if using new features

**Test Failures**:
- Run with verbose: `go test -v ./...`
- Run specific test: `go test -run TestName ./...`
- Check for race conditions: `go test -race ./...`

**Import Cycles**:
- Move shared code to new package
- Use interfaces to break dependencies
- Restructure packages if needed

## Quick Reference

### Common Commands

```bash
# Development
make build                 # Build binary
go test ./...             # Run tests
go test -race ./...       # Test with race detector
golangci-lint run         # Lint code
go mod tidy               # Clean dependencies

# Running
./shell-profiler create work     # Create profile
./shell-profiler list            # List profiles
./shell-profiler select          # Interactive select

# SpecKit (if using)
specify check             # Verify setup
/speckit.specify          # Create spec
/speckit.plan            # Create plan
/speckit.implement       # Implement
```

### File Locations

- **Binary**: `./shell-profiler`
- **Config**: `~/.config/shell-profiler/config.yaml`
- **Profiles**: `~/.config/shell-profiler/profiles/` (or user-configured)
- **Logs**: stdout/stderr (no persistent logs)

## Contributing Guidelines

**Before Starting**:
1. Check existing issues and PRs
2. Discuss major changes first
3. Read this CLAUDE.md completely

**Development Process**:
1. Create feature branch
2. Make changes following standards
3. Add tests
4. Update documentation
5. Run all quality checks
6. Submit PR with clear description

**Commit Messages**:
```
type(scope): brief description

Longer explanation if needed

Fixes #123
```

Types: feat, fix, docs, test, refactor, chore

## Git Policy

**No AI Co-Authoring**: NEVER include `Co-Authored-By` headers, `Generated with Claude Code` footers, or any other AI attribution in commit messages. Commits should contain only the commit message itself.

**Force Push**: Any `git push --force` or `git push --force-with-lease` MUST be confirmed with the user before execution. Always ask for explicit approval. Never force push without user input.

## Resources

**Go Documentation**:
- [Effective Go](https://go.dev/doc/effective_go)
- [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)
- [Standard Library](https://pkg.go.dev/std)

**Project Specific**:
- [direnv Documentation](https://direnv.net/)
- [survey Library](https://github.com/AlecAivazis/survey)

**SpecKit**:
- [SpecKit Repository](https://github.com/github/spec-kit)
- [SpecKit Documentation](https://github.com/github/spec-kit/blob/main/README.md)

---

## Notes

- This project uses internal packages (not importable externally)
- direnv is a required external dependency
- Profile data is stored locally, no cloud sync
- Cross-platform support: macOS and Linux (Windows may work with WSL)
- Colored output uses ANSI codes (may not work on all terminals)

**Remember**: Specification-first for complex features, code-first for simple changes. When in doubt, ask the user whether to use SpecKit workflow.
