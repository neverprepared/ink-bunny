# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a monorepo for an agentic development platform with five packages:

- **brainbox/** — FastAPI backend, Svelte dashboard, and Python package for managing sandboxed Claude Code sessions
- **docker/** — Dockerfiles and compose configs: `docker/brainbox/` (container image + setup), `docker/qdrant/`, `docker/langfuse/`, `docker/minio/`, `docker/docker-compose.yml` (unified)
- **reflex/** — Claude Code plugin providing skills, agents, slash commands, workflow orchestration, RAG integration, and MCP server management
- **shell-profiler/** — Go CLI for managing workspace-specific environment profiles via direnv
- **docs/** — Three-phase architectural documentation (Foundation → Hardened → Production-ready) describing the broader agentic platform vision

## Architecture

**brainbox** provides the API and dashboard, **docker/** provides the container images and compose configs. **reflex** is the plugin that runs inside brainbox (or any Claude Code instance). **shell-profiler** manages per-workspace environment configuration. **docs** describes the aspirational architecture — reflex partially implements Phase 1 concepts (orchestration via Task tool, observability via LangFuse, vector DB via Qdrant), while container isolation, SPIRE identity, and security hardening from Phases 2–3 are not yet implemented.

### Reflex Plugin Architecture

Four pillars, all defined as markdown files:

| Pillar | Location | Format |
|--------|----------|--------|
| Skills (42) | `reflex/plugins/reflex/skills/<name>/SKILL.md` | Pattern/knowledge definitions |
| Commands (19) | `reflex/plugins/reflex/commands/<name>.md` | Slash commands (`/reflex:*`) |
| Agents (2) | `reflex/plugins/reflex/agents/<name>.md` | rag-proxy, workflow-orchestrator |
| Workflows (5) | `reflex/plugins/reflex/workflow-templates/templates/` | jira-driven, github-driven, standalone, custom, transcript-summary |

Key config files:
- `reflex/plugins/reflex/.claude-plugin/plugin.json` — plugin manifest
- `reflex/plugins/reflex/mcp-catalog.json` — MCP server registry (17 servers)
- `reflex/plugins/reflex/hooks/hooks.json` — hook configurations (guardrails, LangFuse, notifications)

Scripts in `reflex/plugins/reflex/scripts/` implement hooks and tooling: `guardrail.py` (destructive op blocking), `ingest.py` (Qdrant ingestion), `summarize.py` (transcript summarizer), `mcp-generate.sh` (MCP registration).

### Brainbox Architecture

Docker container (Ubuntu 24.04, Dockerfile at `docker/brainbox/Dockerfile`) with non-root `developer` user, pre-installed Claude Code, and Playwright MCP. Container setup files (`.bashrc`, `settings.json`, `ttyd-wrapper.sh`, `CLAUDE.md`) live in `docker/brainbox/setup/`. Sessions are named and isolated with persistent data in `~/.config/developer/sessions/`. Secrets are injected as `/home/developer/.env` at container startup.

### Dashboard Architecture

Svelte 5 SPA (runes, no stores library) with a sidebar-driven control panel layout:

```
Sidebar (220px / 60px collapsed)  |  Main Content (active panel)
```

- **Routing**: Hash-based (`#containers`, `#dashboard`), synced via `stores.svelte.js`
- **Sidebar collapse**: Persisted in `localStorage`
- **Panel registry**: `panels.js` — add entries to extend navigation

| Panel | Component | Purpose |
|-------|-----------|---------|
| Containers | `ContainersPanel.svelte` | Session cards, terminal iframes, create/stop/delete, SSE updates |
| Dashboard | `DashboardPanel.svelte` | StatsGrid + MetricsTable (polls `/api/metrics/containers` every 5s) + HubActivity (SSE-refreshed) |
| Observability | `ObservabilityPanel.svelte` | LangFuse + Qdrant health, session traces, trace detail |

Key files:
- `dashboard/src/lib/stores.svelte.js` — `currentPanel` + `sidebarCollapsed` reactive state
- `dashboard/src/lib/panels.js` — panel registry with inline SVG icons
- `dashboard/src/lib/AppShell.svelte` — CSS Grid shell (sidebar + content)
- `dashboard/src/lib/Sidebar.svelte` — collapsible nav with active highlighting

Backend API:
- `GET /api/sessions` — container list with ports, volumes, status
- `GET /api/metrics/containers` — per-container CPU %, memory, uptime (reuses `monitor.py` helpers)
- `GET /api/hub/state` — tasks, agents, tokens, messages
- `GET /api/events` — SSE stream for Docker + hub events
- Hub state cleanup: terminal tasks (completed/failed/cancelled) and stale messages are dropped on startup

### Shell Profiler Architecture

Go CLI (`cmd/shell-profiler/main.go`) using `internal/` packages for commands, config, profile management, and UI. Depends on direnv for environment variable loading.

## Commands

Uses [Just](https://github.com/casey/just) as the polyglot task runner. Run `just` to see all available recipes.

### Brainbox (Python)

```bash
just bb-api              # Start FastAPI backend
just bb-build            # Install deps + build Svelte dashboard
just bb-test             # Run pytest
just bb-lint             # Run ruff
just bb-mcp              # Start MCP server
just bb-dashboard        # Start API + dashboard (localhost:9999)
just bb-docker-build     # Build Docker image
just bb-docker-start     # Start default session
just bb-docker-start -s myproject -v /path:/home/developer/workspace/myproject
just bb-daemon-start     # Start API as daemon
just bb-daemon-stop      # Stop daemon
just bb-daemon-status    # Check daemon status
just bb-daemon-restart   # Restart daemon
just bb-daemon-logs      # Tail daemon logs
just bb-minio            # Start MinIO via docker compose
```

### Shell Profiler (Go)

```bash
just sp-build            # Build Go binary to shell-profiler/bin/
just sp-test             # Run Go tests
just sp-lint             # Run golangci-lint
```

### Reflex (Plugin)

```bash
just reflex-dev          # Launch Claude Code with local plugin
just reflex-qdrant       # Start Qdrant (port 6333)
just reflex-langfuse     # Start LangFuse (port 3000)
```

### Cross-cutting

```bash
just test-all            # Run all test suites
just lint-all            # Run all linters
```

### docs

No build commands. Architecture documents are organized by phase:
- `docs/persona_agentic/PHASE_1/` — Foundation (container isolation, basic orchestration, 1Password secrets, vector DB)
- `docs/persona_agentic/PHASE_2/` — Hardened (SPIRE identity, OPA/Kyverno, threat model, IR runbooks)
- `docs/persona_agentic/PHASE_3/` — Production (full PKI with HSM, Envoy/Cilium/Falco, orchestrator resilience)
- `docs/persona_agentic/REFLEX/` — Analysis of reflex coverage vs. Phase 1 architecture

## Distribution

| Package | Channels | Tag format |
|---------|----------|------------|
| shell-profiler | Homebrew (`neverprepared/ink-bunny`) | `shell-profiler/vX.Y.Z` |
| brainbox | Homebrew (`neverprepared/ink-bunny`) | `brainbox/vX.Y.Z` |
| reflex | Plugin marketplace + Homebrew (`neverprepared/ink-bunny`) | `reflex/vX.Y.Z` |

All formulas are distributed via a single consolidated tap: `brew install neverprepared/ink-bunny/<package>`. Formulas live in `<package>/Formula/` in the monorepo and are synced to `neverprepared/homebrew-ink-bunny` on release.

## Conventions

### CLAUDE_CONFIG_DIR

Never hardcode `~/.claude` or `$HOME/.claude`. Always use `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`. Users may have custom config directories.

### Git Commits

```
<summary line>

<optional body>
```

No AI attribution — no "Generated with Claude Code" footers, no Co-Authored-By lines. Always `git pull --rebase` before pushing. Do not auto-resolve rebase conflicts — inform the user.

### Versioning

| Package | Strategy | Config |
|---------|----------|--------|
| shell-profiler | Manual tag push | — |
| brainbox | Manual tag push | — |
| reflex | release-please (conventional commits) | `reflex/release-please-config.json` |

### CI/CD

Path-filtered CI runs on PR/push to main. Release workflows trigger on scoped tags (`<package>/v*`). Each release workflow builds artifacts, uploads to GitHub release, updates the formula, and syncs to the corresponding Homebrew tap repo.

### Workflow Patterns

- Enter plan mode for non-trivial tasks (3+ steps or architectural decisions)
- Use subagents for research/exploration to keep main context clean; use `model: "haiku"` for quick subtasks
- After corrections from the user, update `tasks/lessons.md` with the pattern
- Never mark a task complete without proving it works
- After every WebSearch, store valuable results in Qdrant with metadata (source, category, confidence, freshness)
