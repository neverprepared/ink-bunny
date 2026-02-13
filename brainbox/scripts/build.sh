#!/bin/bash
# Build the developer image and remove stale container

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PROJECT_DIR")"
CONTAINER_NAME="developer"

echo "Building image..."
docker build -t developer -f "$REPO_ROOT/docker/brainbox/Dockerfile" "$REPO_ROOT" || exit 1

# Remove old container so run.sh creates a fresh one from the new image
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Removing old container..."
    docker rm -f "$CONTAINER_NAME" > /dev/null
fi
