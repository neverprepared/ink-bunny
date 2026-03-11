class Brainbox < Formula
  desc "Docker-based sandboxed Claude Code session manager"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.13.1/brainbox-0.13.1.tar.gz"
  version "0.13.1"
  sha256 "5de5b1ea5a4dae44aa7af369c949558fbe4c647ad01721d52e93313e818f351f"
  license "MIT"

  depends_on "docker"

  def install
    # Write docker-compose.yml — embedded so the tarball doesn't need to contain it
    (share/"brainbox").mkpath
    (share/"brainbox/docker-compose.yml").write <<~YAML
      # Brainbox stack — UI + API + Qdrant
      # Usage: brainbox up
      #
      # DooD note: bind mount paths for session containers must be host paths.
      # XDG_CONFIG_HOME and CLAUDE_CONFIG_DIR are mounted at their actual host
      # paths so session container mounts resolve correctly via the Docker daemon.
      services:
        brainbox-ui:
          image: ghcr.io/neverprepared/brainbox-ui:latest
          ports:
            - "127.0.0.1:9998:80"
          depends_on:
            - brainbox-api
          networks:
            - brainbox-net
          restart: unless-stopped

        brainbox-api:
          image: ghcr.io/neverprepared/brainbox-api:latest
          ports:
            - "127.0.0.1:9999:9999"
          volumes:
            - "${XDG_CONFIG_HOME:-${HOME}/.config}:${XDG_CONFIG_HOME:-${HOME}/.config}"
            - "${CLAUDE_CONFIG_DIR:-${HOME}/.claude}:${CLAUDE_CONFIG_DIR:-${HOME}/.claude}:ro"
            - "${WORKSPACE_HOME:-${HOME}}/.aws:${WORKSPACE_HOME:-${HOME}}/.aws:ro"
            - "${WORKSPACE_HOME:-${HOME}}/.ssh:${WORKSPACE_HOME:-${HOME}}/.ssh:ro"
            - "${WORKSPACE_HOME:-${HOME}}/.gitconfig:${WORKSPACE_HOME:-${HOME}}/.gitconfig:ro"
            - "${WORKSPACE_HOME:-${HOME}}/.azure:${WORKSPACE_HOME:-${HOME}}/.azure:ro"
            - "${WORKSPACE_HOME:-${HOME}}/.kube:${WORKSPACE_HOME:-${HOME}}/.kube:ro"
            - "/var/run/docker.sock:/var/run/docker.sock"
          environment:
            - XDG_CONFIG_HOME=${XDG_CONFIG_HOME:-${HOME}/.config}
            - CLAUDE_CONFIG_DIR=${CLAUDE_CONFIG_DIR:-${HOME}/.claude}
            - WORKSPACE_HOME=${WORKSPACE_HOME:-${HOME}}
            - BRAINBOX_HOST_HOME=${HOME}
            - SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock
          networks:
            - brainbox-net
          restart: unless-stopped

        qdrant:
          image: qdrant/qdrant:latest
          ports:
            - "127.0.0.1:6333:6333"
          volumes:
            - "${QDRANT_DATA_DIR:-${XDG_CONFIG_HOME:-${HOME}/.config}/qdrant}:/qdrant/storage"
          networks:
            - brainbox-net
          restart: unless-stopped

      networks:
        brainbox-net:
          name: brainbox-net
    YAML

    # Create compose-aware wrapper script
    (bin/"brainbox").write <<~EOS
      #!/bin/bash
      # brainbox — Docker Compose wrapper
      set -e

      COMPOSE_FILE="#{share}/brainbox/docker-compose.yml"
      BRAINBOX_VERSION="#{version}"

      # Check if Docker is installed
      if ! command -v docker &> /dev/null; then
          echo "Error: Docker is not installed." >&2
          exit 1
      fi

      # Check if Docker daemon is running
      if ! docker info &> /dev/null 2>&1; then
          echo "Error: Docker is not running. Please start Docker Desktop." >&2
          exit 1
      fi

      case "$1" in
        up|start)
          exec docker compose -f "$COMPOSE_FILE" up -d
          ;;
        down|stop)
          exec docker compose -f "$COMPOSE_FILE" down
          ;;
        logs)
          exec docker compose -f "$COMPOSE_FILE" logs -f
          ;;
        status|ps)
          exec docker compose -f "$COMPOSE_FILE" ps
          ;;
        pull)
          exec docker compose -f "$COMPOSE_FILE" pull
          ;;
        version|--version|-v)
          echo "brainbox $BRAINBOX_VERSION"
          ;;
        *)
          echo "Usage: brainbox {up|start|down|stop|logs|status|pull|version}"
          echo ""
          echo "Commands:"
          echo "  up/start   Start brainbox stack (API + Qdrant)"
          echo "  down/stop  Stop brainbox stack"
          echo "  logs       Follow logs from all services"
          echo "  status     Show running containers"
          echo "  pull       Pull latest images"
          echo "  version    Show brainbox version"
          exit 1
          ;;
      esac
    EOS

    chmod 0755, bin/"brainbox"
  end

  def caveats
    <<~EOS
      brainbox requires Docker to run. Please ensure Docker Desktop is running:
        open -a Docker

      Start the brainbox stack:
        brainbox up

      Dashboard: http://localhost:9998
      API:       http://localhost:9999

      Configuration is stored in $XDG_CONFIG_HOME/developer (default: ~/.config/developer)
      Qdrant data stored in $XDG_CONFIG_HOME/qdrant (override with QDRANT_DATA_DIR)
    EOS
  end

  test do
    assert_match "brainbox #{version}", shell_output("#{bin}/brainbox version")
  end
end
