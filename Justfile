# Root Justfile — polyglot monorepo task runner

default:
    @just --list --unsorted

# === Brainbox (Python) ===

bb-api:
    cd brainbox && uv run python -m brainbox api

bb-build:
    cd brainbox && uv sync
    cd brainbox/dashboard && npm install && npx vite build

bb-test:
    cd brainbox && uv run python -m pytest

bb-lint:
    cd brainbox && uv run ruff check src/

bb-mcp:
    cd brainbox && uv run python -m brainbox mcp

bb-dashboard:
    cd brainbox && npm run dashboard

bb-daemon-start:
    cd brainbox && uv run python -m brainbox api --daemon

bb-daemon-stop:
    cd brainbox && uv run python -m brainbox stop

bb-daemon-status:
    cd brainbox && uv run python -m brainbox status

bb-daemon-restart:
    cd brainbox && uv run python -m brainbox restart

bb-daemon-logs:
    tail -f ~/.config/developer/logs/brainbox.log

bb-docker-build:
    cd brainbox && ./scripts/build.sh

bb-docker-start *ARGS:
    cd brainbox && ./scripts/run.sh {{ ARGS }}

bb-minio:
    cd docker/minio && docker compose up -d

# === Shell Profiler (Go) ===

sp-build:
    cd shell-profiler && go build -o bin/shell-profiler ./cmd/shell-profiler

sp-test:
    cd shell-profiler && go test ./...

sp-lint:
    cd shell-profiler && golangci-lint run

# === Reflex (Plugin) ===

reflex-dev:
    claude --plugin-dir reflex

reflex-qdrant:
    cd docker/qdrant && docker compose up -d

reflex-langfuse:
    cd docker/langfuse && docker compose up -d

# === Cross-cutting ===

test-all: bb-test sp-test

lint-all: bb-lint sp-lint
