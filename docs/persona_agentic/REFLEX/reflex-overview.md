# Reflex — Claude Code Plugin

Reflex is an opinionated Claude Code plugin that provides sub-agents, skills, workflows, and infrastructure for application development, infrastructure, and data engineering workflows.

**Repository**: [mindmorass/reflex](https://github.com/mindmorass/reflex)
**Version**: 1.7.2
**License**: MIT

## Four Pillars

| Pillar | What It Provides | Scale |
|---|---|---|
| **Agents** | Autonomous sub-processes that Claude dispatches via the Task tool | 2 agents (workflow-orchestrator, rag-proxy) |
| **Skills** | Domain-specific knowledge and patterns loaded into Claude's context | 43 skills |
| **Commands** | User-invocable operations (`/reflex:init`, `/reflex:guardrail`, etc.) | 22 commands |
| **Workflows** | Multi-step templates orchestrating agents across planning, execution, and deployment | 4 templates, 13 reusable steps |

## Key Infrastructure

| Component | Implementation | Purpose |
|---|---|---|
| **Qdrant** | Docker Compose (REST 6333, gRPC 6334) | Vector DB for semantic search, RAG, persistent memory |
| **LangFuse** | Docker Compose (6 services: web, worker, postgres, clickhouse, redis, minio) | LLM observability — tool tracing, metrics, analytics |
| **Guardrails** | Python pattern engine (`guardrail.py`) via PreToolUse hook | Blocks destructive operations (file deletion, git force push, database drops, cloud termination) |
| **MCP Servers** | 11+ pre-configured servers in `mcp-catalog.json` | Qdrant, Atlassian, Git, GitHub, Azure, Azure DevOps, SQL Server, Playwright, Microsoft Docs |

## How Reflex Relates to PHASE_1

Reflex and [[PHASE_1/agentic-architecture|PHASE_1]] operate at **different abstraction levels**.

PHASE_1 describes a **container-native agent platform**: a custom orchestrator provisions Docker containers, issues identity tokens, enforces policy, and manages container lifecycles. Agents are isolated processes running inside hardened containers.

Reflex is a **Claude Code plugin** where **Claude itself is the orchestrator**. Agents are sub-processes within Claude's runtime, dispatched via Claude Code's `Task` tool. The star topology, task dispatch, and message routing all exist — but they're implemented by Claude Code's infrastructure rather than custom code.

This means:

- **Orchestration** is largely covered — Claude's Task tool implements the star topology, task routing, and message bus
- **Observability** exceeds PHASE_1 — LangFuse provides full tracing where PHASE_1 specifies only structured JSON logs
- **Vector DB** is well covered — Qdrant with ingestion pipeline, RAG proxy, and collection isolation
- **Container lifecycle** is the major gap — Reflex has no container provisioning, hardening, or lifecycle management
- **Secrets management** takes a different approach — `.env` files rather than 1Password/direnv/tmpfs

See [[REFLEX/reflex-phase1-coverage|Coverage Matrix]] for the full mapping, [[REFLEX/reflex-gap-analysis|Gap Analysis]] for what's missing, and [[REFLEX/reflex-strengths|Strengths]] for where Reflex exceeds PHASE_1.
