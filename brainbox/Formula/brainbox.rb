class Brainbox < Formula
  desc "Docker-based sandboxed Claude Code session manager"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.8.0/brainbox-0.8.0.tar.gz"
  sha256 "4428dce03c502aff1f16118867560d52fcede8241298abad6de860995d62d0eb"
  license "MIT"
  version "0.8.0"

  depends_on "docker"

  def install
    # Create wrapper script inline
    (bin/"brainbox").write <<~EOS
      #!/bin/bash
      # brainbox Docker wrapper
      # Installed by Homebrew to run brainbox via Docker

      set -e

      BRAINBOX_IMAGE="${BRAINBOX_IMAGE:-brainbox:latest}"
      BRAINBOX_VERSION="#{version}"

      # Try ghcr.io if local image doesn't exist
      if ! docker image inspect "$BRAINBOX_IMAGE" &> /dev/null; then
          BRAINBOX_IMAGE="ghcr.io/neverprepared/brainbox:latest"
      fi

      # Color output
      RED='\\033[0;31m'
      GREEN='\\033[0;32m'
      YELLOW='\\033[1;33m'
      NC='\\033[0m'

      error() {
          echo -e "${RED}Error:${NC} $1" >&2
          exit 1
      }

      info() {
          echo -e "${GREEN}==>${NC} $1"
      }

      warn() {
          echo -e "${YELLOW}Warning:${NC} $1" >&2
      }

      # Check if Docker is installed
      if ! command -v docker &> /dev/null; then
          error "Docker is not installed. Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
      fi

      # Check if Docker daemon is running
      if ! docker info &> /dev/null; then
          error "Docker is not running. Please start Docker Desktop and try again."
      fi

      # Pull or build image if not available locally
      if ! docker image inspect "$BRAINBOX_IMAGE" &> /dev/null; then
          if [[ "$BRAINBOX_IMAGE" == ghcr.io/* ]]; then
              info "Pulling brainbox Docker image (this only happens once)..."
              if ! docker pull "$BRAINBOX_IMAGE" 2>/dev/null; then
                  warn "Could not pull from ghcr.io. You may need to build locally:"
                  echo "  git clone https://github.com/neverprepared/ink-bunny.git"
                  echo "  cd ink-bunny"
                  echo "  just bb-docker-build"
                  error "Docker image not available"
              fi
          else
              error "Docker image '$BRAINBOX_IMAGE' not found. Build it with: just bb-docker-build"
          fi
      fi

      # Run brainbox in Docker
      exec docker run --rm -it \\
          -v /var/run/docker.sock:/var/run/docker.sock \\
          -v "$HOME/.config/brainbox:/home/developer/.config" \\
          -v "$PWD:/workspace" \\
          "$BRAINBOX_IMAGE" \\
          brainbox "$@"
    EOS

    chmod 0755, bin/"brainbox"
  end

  def caveats
    <<~EOS
      brainbox requires Docker to run. Please ensure Docker Desktop is running:
        open -a Docker

      The first time you run brainbox, it will download the Docker image.

      Usage:
        brainbox --help
        brainbox provision myproject
        brainbox api

      Configuration is stored in ~/.config/brainbox
    EOS
  end

  test do
    # Test that Docker requirement is enforced
    system "#{bin}/brainbox", "--help" if system "docker", "info"
  end
end
