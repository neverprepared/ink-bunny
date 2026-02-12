# Root Justfile — polyglot monorepo task runner

default:
    @just --list --unsorted

# === Container Lifecycle (Python) ===

cl-api:
    cd container-lifecycle && uv run python -m container_lifecycle api

cl-build:
    cd container-lifecycle && uv sync
    cd container-lifecycle/dashboard && npm install && npx vite build

cl-test:
    cd container-lifecycle && uv run pytest

cl-lint:
    cd container-lifecycle && uv run ruff check src/

cl-mcp:
    cd container-lifecycle && uv run python -m container_lifecycle mcp

cl-dashboard:
    cd container-lifecycle && npm run dashboard

cl-docker-build:
    cd container-lifecycle && ./scripts/build.sh

cl-docker-start *ARGS:
    cd container-lifecycle && ./scripts/run.sh {{ ARGS }}

# === Shell Profiler (Go) ===

sp-build:
    cd shell-profiler && go build -o bin/shell-profiler ./cmd/shell-profiler

sp-test:
    cd shell-profiler && go test ./...

sp-lint:
    cd shell-profiler && golangci-lint run

# === Reflex (Plugin) ===

reflex-dev:
    claude --plugin-dir reflex-claude-marketplace

reflex-qdrant:
    cd reflex-claude-marketplace/docker/qdrant && docker compose up -d

reflex-langfuse:
    cd reflex-claude-marketplace/docker/langfuse && docker compose up -d

# === Cross-cutting ===

test-all: cl-test sp-test

lint-all: cl-lint sp-lint
