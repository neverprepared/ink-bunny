# Profile CLI - Go Implementation

This is the Go implementation of the workspace profile manager. It provides the same functionality as `profile.sh` but as a compiled binary.

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
make run

# Or
go run ./cmd/shell-profiler

# Run tests
make test
```

## Architecture

The Go implementation is structured as follows:

- `cmd/shell-profiler/` - Main entry point
- `internal/cli/` - CLI command handling and routing
- `internal/profile/` - Profile management logic (info, status)
- `internal/scripts/` - Script execution wrapper (delegates to shell scripts)

Currently, most commands delegate to the existing shell scripts. Over time, these can be migrated to pure Go implementations.

## Current Implementation Status

- ✅ `info` - Fully implemented in Go
- ✅ `status` - Fully implemented in Go
- ✅ `help` - Fully implemented in Go
- 🔄 `create` - Delegates to `scripts/create-profile.sh`
- 🔄 `update` - Delegates to `scripts/update-profile.sh`
- 🔄 `list` - Delegates to `scripts/list-profiles.sh`
- 🔄 `delete` - Delegates to `scripts/delete-profile.sh`
- 🔄 `restore` - Delegates to `scripts/restore-profile.sh`

## Future Enhancements

- Migrate all commands to pure Go implementations
- Add better error handling and user feedback
- Add configuration file support
- Add unit tests
- Add integration tests
