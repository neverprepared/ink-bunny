# Brainbox Installation Guide

Brainbox is a sandboxed Docker container orchestration tool for Claude Code sessions.

## Recommended: Docker Wrapper (Simple)

The Docker wrapper runs brainbox inside a container, avoiding dependency conflicts.

```bash
# Install via Homebrew
brew install neverprepared/ink-bunny/brainbox

# First run will pull the Docker image
brainbox --help

# Start using brainbox
brainbox provision myproject
brainbox api
```

**Requirements:**
- Docker Desktop must be installed and running
- macOS (arm64 or x86_64)

**Pros:**
- No Python dependency issues
- Fully isolated environment
- Same environment as production
- Easy updates

**Cons:**
- Requires Docker
- Slightly slower startup (container overhead)

---

## Alternative: Native Python Installation

For advanced users who want native Python execution:

```bash
# Install via Homebrew (may have dependency issues on some systems)
brew install neverprepared/ink-bunny/brainbox

# Or install from source
git clone https://github.com/neverprepared/ink-bunny.git
cd ink-bunny/brainbox
uv sync
uv run brainbox --help
```

**Requirements:**
- Python 3.11+
- Rust toolchain (for compiled dependencies)

**Known Issues:**
- Some dependencies (pydantic_core, uvloop) require compilation
- May fail on systems without Rust/build tools

---

## Development Installation

```bash
# Clone repository
git clone https://github.com/neverprepared/ink-bunny.git
cd ink-bunny/brainbox

# Install with uv (recommended)
uv sync

# Run directly
uv run brainbox --help

# Or build Docker image
just bb-docker-build
just bb-docker-start
```

---

## Docker Image Only

If you just want the Docker image without Homebrew:

```bash
# Pull from registry (when available)
docker pull ghcr.io/neverprepared/brainbox:latest

# Or build locally
git clone https://github.com/neverprepared/ink-bunny.git
cd ink-bunny
just bb-docker-build

# Run
docker run -it --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  brainbox:latest brainbox --help
```

---

## Troubleshooting

### Docker not running
```
Error: Docker is not running. Please start Docker Desktop and try again.
```
**Solution:** Open Docker Desktop or run `open -a Docker`

### Image not found
```
Error: Docker image 'brainbox:latest' not found
```
**Solution:** Build locally with `just bb-docker-build` or wait for public registry

### Permission denied
```
Error: permission denied while trying to connect to Docker daemon
```
**Solution:** Add user to docker group or use Docker Desktop

---

## Configuration

Brainbox stores configuration in `~/.config/developer/` (or `$XDG_CONFIG_HOME/developer/`):
- `sessions/` - Session state files
- `.secrets/` - Resolved secret files
- `logs/brainbox.log` - API server log
- `brainbox.pid` - Daemon PID file

Configuration is controlled via environment variables (see `brainbox/src/brainbox/config.py`).

---

## Uninstall

```bash
# Homebrew
brew uninstall brainbox

# Remove config
rm -rf ~/.config/developer

# Remove Docker images
docker rmi brainbox:latest
```
