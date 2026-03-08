# shell-profiler - Go Implementation

This is the Go implementation of the workspace profile manager CLI.

## Building

```bash
# Build the binary
make build

# Or directly with go
go build -o shell-profiler ./cmd/shell-profiler

# Install to workspace root
make install
```

## Development

```bash
# Run directly without building
go run ./cmd/shell-profiler

# Run tests
make test
```

## Architecture

The Go implementation is structured as follows:

- `cmd/shell-profiler/` - Main entry point
- `internal/cli/` - CLI command routing (`app.go`) and color constants
- `internal/commands/` - Command implementations (create, delete, dotfiles, git, init, list, select, update)
- `internal/config/` - Configuration management (`~/.profile-manager`)
- `internal/profile/` - Profile business logic (info, direnv status)
- `internal/templates/` - Go templates for generating profile files (envrc.tpl, env.tpl, gitconfig.tpl)
- `internal/ui/` - Interactive prompts and color utilities

## Implementation Status

All commands are fully implemented in Go:

- ✅ `init` - Initialize configuration (`~/.profile-manager`)
- ✅ `create` (`new`, `add`) - Create a new workspace profile
- ✅ `update` (`upgrade`) - Update an existing profile
- ✅ `list` (`ls`) - List all profiles
- ✅ `select` (`use`) - Select and switch to a profile
- ✅ `delete` (`remove`, `rm`) - Delete a profile
- ✅ `info` (`current`, `show`) - Show current profile details
- ✅ `status` - Show direnv status
- ✅ `dotfiles` - Manage dotfiles (subcommands: `list`, `edit`)
- ✅ `sync` - Git sync operations (subcommands: `init`, `pull`, `push`, `sync`, `remote`, `status`)
- ⚠️ `restore` - Not yet implemented
