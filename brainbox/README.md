# brainbox

Managed Docker lifecycle for sandboxed Claude Code sessions with a 5-phase pipeline (provision → configure → start → monitor → recycle), container hardening, and a web dashboard.

## Quick Start

### API Server

Run the API server in the foreground:

```bash
brainbox api --port 9999
```

Or as a background daemon:

```bash
# Start daemon
brainbox api --daemon --port 9999

# Check status
brainbox status

# Stop daemon
brainbox stop

# Restart daemon
brainbox restart
```

See [Daemon Mode Documentation](docs/daemon.md) for full details on background daemon management.

### Container Management

```bash
# Provision a new session
brainbox provision --session myproject

# Run full pipeline (provision + start + monitor)
brainbox run --session myproject --port 2222

# Recycle (stop and remove) a session
brainbox recycle --session myproject
```

### MCP Server

Run as an MCP server for Claude Code integration:

```bash
brainbox mcp
```

## Daemon Mode

The brainbox API server can run as a background daemon with full lifecycle management:

- **Start**: `brainbox api --daemon` - Launch API server in background
- **Stop**: `brainbox stop` - Gracefully stop the daemon
- **Status**: `brainbox status` - Check if daemon is running (supports `--json` flag)
- **Restart**: `brainbox restart` - Stop and start the daemon

**Features:**
- Process management with PID file tracking
- Graceful shutdown with SIGTERM → SIGKILL fallback
- Automatic stale PID file cleanup
- Centralized logging to `~/.config/developer/logs/brainbox.log`
- Human-readable and JSON status output
- Integration with systemd/launchd for production deployments

For complete documentation, examples, troubleshooting, and system service integration, see [docs/daemon.md](docs/daemon.md).

## Acknowledgements

Initial scaffolding (Dockerfile, dashboard, session scripts) derived from [claude-code-tips](https://github.com/ykdojo/claude-code-tips) by [@ykdojo](https://github.com/ykdojo).
