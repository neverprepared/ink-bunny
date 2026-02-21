# Brainbox Docker Image

Official Docker image for brainbox - sandboxed Claude Code session manager.

## Quick Start

```bash
# Pull the image
docker pull ghcr.io/neverprepared/brainbox:latest

# Run brainbox
docker run -it --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/.config/brainbox:/home/developer/.config \
  ghcr.io/neverprepared/brainbox:latest \
  brainbox --help
```

## Installation via Homebrew (Recommended)

```bash
brew install neverprepared/ink-bunny/brainbox
brainbox --help
```

The Homebrew formula automatically handles Docker image pulling and provides a clean `brainbox` command.

## Building Locally

```bash
# Clone repository
git clone https://github.com/neverprepared/ink-bunny.git
cd ink-bunny

# Build image
just bb-docker-build

# Run
docker run -it --rm brainbox:latest brainbox --help
```

## Image Details

- **Base**: Ubuntu 24.04
- **User**: `developer` (non-root)
- **Python**: Managed via uv
- **Pre-installed**:
  - Claude Code CLI
  - Playwright MCP server
  - Docker client (for nested containers)
  - Common development tools

## Platforms

- `linux/amd64` (x86_64)
- `linux/arm64` (Apple Silicon, ARM servers)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAINBOX_IMAGE` | `brainbox:latest` | Override Docker image to use |

## Volumes

| Volume | Purpose |
|--------|---------|
| `/var/run/docker.sock` | Docker socket for container orchestration |
| `~/.config/brainbox` | Persistent configuration and session data |
| `/workspace` | Current working directory mount |

## Versions

Images are tagged with:
- `latest` - Latest stable release
- `X.Y.Z` - Specific version (e.g., `0.6.0`)
- `X.Y` - Minor version (e.g., `0.6`)

## Security

- Runs as non-root user (`developer`)
- No privileged mode required
- Docker socket mounted for container management only
- Secrets stored in `~/.config/brainbox/secrets.env`

## Support

- **Issues**: https://github.com/neverprepared/ink-bunny/issues
- **Documentation**: https://github.com/neverprepared/ink-bunny/tree/main/brainbox
- **Releases**: https://github.com/neverprepared/ink-bunny/releases
