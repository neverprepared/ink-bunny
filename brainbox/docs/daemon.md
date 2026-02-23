# Daemon Mode

Run the brainbox API server as a background daemon with full lifecycle management.

## Quick Start

```bash
# Start daemon on default port (9999)
brainbox api --daemon

# Check status
brainbox status

# Stop daemon
brainbox stop

# Restart daemon
brainbox restart
```

## Commands

### Start Daemon

Start the API server as a background daemon:

```bash
brainbox api --daemon [OPTIONS]
```

**Options:**
- `--host HOST` - Host to bind to (default: `127.0.0.1`)
- `--port PORT` - Port to bind to (default: `9999`)
- `--reload` - Enable auto-reload on code changes (development only)

**Examples:**

```bash
# Start on default port with default host
brainbox api --daemon

# Start on custom port
brainbox api --daemon --port 8888

# Start on all interfaces
brainbox api --daemon --host 0.0.0.0 --port 9999

# Start with auto-reload for development
brainbox api --daemon --reload --port 9999
```

**Output:**

```
Daemon started successfully
  PID: 12345
  URL: http://127.0.0.1:9999
  Logs: ~/.config/developer/logs/brainbox.log
```

### Stop Daemon

Stop the running daemon:

```bash
brainbox stop [OPTIONS]
```

**Options:**
- `--timeout SECONDS` - Maximum time to wait for graceful shutdown (default: `10`)

**Examples:**

```bash
# Stop with default timeout
brainbox stop

# Stop with custom timeout
brainbox stop --timeout 30
```

The daemon will first receive a SIGTERM signal for graceful shutdown. If the process doesn't exit within the timeout, it will be force-killed with SIGKILL.

**Output:**

```
Daemon stopped gracefully (PID 12345)
```

### Check Status

Check if the daemon is running:

```bash
brainbox status [OPTIONS]
```

**Options:**
- `--json` - Output status in JSON format

**Examples:**

```bash
# Human-readable status
brainbox status

# JSON status
brainbox status --json
```

**Output (running):**

```
✓ Daemon running
  PID: 12345
  URL: http://127.0.0.1:9999
  Uptime: 2h 15m
  Logs: ~/.config/developer/logs/brainbox.log
```

**Output (not running):**

```
✗ Daemon not running
  Logs: ~/.config/developer/logs/brainbox.log
```

**JSON Output:**

```json
{
  "running": true,
  "pid": 12345,
  "url": "http://127.0.0.1:9999",
  "host": "127.0.0.1",
  "port": 9999,
  "started_at": "2026-02-18T10:00:00+00:00",
  "uptime_seconds": 8100,
  "log_file": "/Users/username/.config/developer/logs/brainbox.log"
}
```

### Restart Daemon

Restart the daemon (stop then start):

```bash
brainbox restart [OPTIONS]
```

**Options:**
- `--host HOST` - Host to bind to (default: `127.0.0.1`)
- `--port PORT` - Port to bind to (default: `9999`)
- `--reload` - Enable auto-reload on code changes

**Examples:**

```bash
# Restart with default settings
brainbox restart

# Restart on different port
brainbox restart --port 8888
```

**Output:**

```
Daemon stopped gracefully (PID 12345)
Daemon started successfully
  PID: 12346
  URL: http://127.0.0.1:9999
  Logs: ~/.config/developer/logs/brainbox.log
```

## File Locations

### PID File

Location: `~/.config/developer/brainbox.pid` (or `$XDG_CONFIG_HOME/developer/brainbox.pid`)

Format:
```
<pid>
<port>
<host>
<started_at_iso_timestamp>
```

Example:
```
12345
9999
127.0.0.1
2026-02-18T10:00:00+00:00
```

### Log File

Location: `~/.config/developer/logs/brainbox.log` (or `$XDG_CONFIG_HOME/developer/logs/brainbox.log`)

The log file contains combined stdout and stderr from the API server. New daemon starts append to the existing log file with a separator.

**View logs:**

```bash
# View entire log
cat ~/.config/developer/logs/brainbox.log

# Tail logs in real-time
tail -f ~/.config/developer/logs/brainbox.log

# View last 50 lines
tail -n 50 ~/.config/developer/logs/brainbox.log
```

## Error Handling

### Already Running

If you try to start the daemon when it's already running:

```bash
$ brainbox api --daemon
{"ok": false, "error": "Daemon already running (PID 12345) at http://127.0.0.1:9999"}
```

**Solution:** Stop the existing daemon first, or use `brainbox restart` to restart it.

### Not Running

If you try to stop the daemon when it's not running:

```bash
$ brainbox stop
{"ok": false, "error": "Daemon not running"}
```

**Solution:** Check the status with `brainbox status` before stopping.

### Stale PID File

If the PID file exists but the process is dead (e.g., after a system crash), the daemon manager will automatically detect and clean up the stale PID file.

```bash
$ brainbox status
✗ Daemon not running

$ brainbox api --daemon
Daemon started successfully
  PID: 12346
  ...
```

### Permission Errors

If you encounter permission errors with the PID or log files:

```bash
$ brainbox api --daemon
{"ok": false, "error": "Failed to write PID file: [Errno 13] Permission denied: ..."}
```

**Solution:** Ensure you have write permissions for `~/.config/developer/` or set `$XDG_CONFIG_HOME` to a directory you own.

## Integration with System Service Managers

### systemd (Linux)

Create a systemd user service at `~/.config/systemd/user/brainbox.service`:

```ini
[Unit]
Description=Brainbox API Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m brainbox api --host 127.0.0.1 --port 9999
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

**Manage the service:**

```bash
# Enable and start
systemctl --user enable brainbox
systemctl --user start brainbox

# Check status
systemctl --user status brainbox

# Stop
systemctl --user stop brainbox

# View logs
journalctl --user -u brainbox -f
```

**Note:** When using systemd, you don't need the `--daemon` flag. systemd manages the process in the background.

### launchd (macOS)

Create a LaunchAgent at `~/Library/LaunchAgents/com.brainbox.api.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.brainbox.api</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>-m</string>
        <string>brainbox</string>
        <string>api</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>9999</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/brainbox.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/brainbox.err</string>
</dict>
</plist>
```

**Manage the service:**

```bash
# Load and start
launchctl load ~/Library/LaunchAgents/com.brainbox.api.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.brainbox.api.plist

# View logs
tail -f /tmp/brainbox.log
```

**Note:** When using launchd, you don't need the `--daemon` flag. launchd manages the process in the background.

## Troubleshooting

### Daemon won't start

1. **Check if already running:**
   ```bash
   brainbox status
   ```

2. **Check logs for errors:**
   ```bash
   tail -n 50 ~/.config/developer/logs/brainbox.log
   ```

3. **Check port availability:**
   ```bash
   # macOS/Linux
   lsof -i :9999

   # If port is in use, use a different port
   brainbox api --daemon --port 9998
   ```

### Daemon won't stop

1. **Try with longer timeout:**
   ```bash
   brainbox stop --timeout 30
   ```

2. **Force kill manually:**
   ```bash
   # Get PID from status
   brainbox status --json | jq '.pid'

   # Force kill
   kill -9 <PID>

   # Clean up PID file
   rm ~/.config/developer/brainbox.pid
   ```

### Lost track of daemon

If you're not sure if the daemon is running:

```bash
# Check status
brainbox status

# Look for process
ps aux | grep "brainbox api"

# Check if port is in use
lsof -i :9999
```

### Logs too large

If the log file grows too large:

```bash
# Truncate log file
> ~/.config/developer/logs/brainbox.log

# Or rotate logs manually
mv ~/.config/developer/logs/brainbox.log ~/.config/developer/logs/brainbox.log.old
```

## Development vs Production

### Development

For development, use auto-reload to automatically restart on code changes:

```bash
brainbox api --daemon --reload --port 9999
```

**Warning:** `--reload` watches for file changes and restarts the server automatically. This adds overhead and should NOT be used in production.

### Production

For production, run without `--reload`:

```bash
brainbox api --daemon --host 0.0.0.0 --port 9999
```

**Best practices for production:**

1. Use a system service manager (systemd/launchd) instead of manual daemon management
2. Set up proper log rotation
3. Configure monitoring and health checks
4. Use a reverse proxy (nginx, caddy) in front of the API
5. Enable TLS/SSL termination at the reverse proxy
6. Set resource limits (memory, CPU)
7. Configure automatic restarts on failure

## See Also

- [brainbox README](../README.md)
- [Install Guide](../INSTALL.md)
