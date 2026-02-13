# Reflex Coverage Matrix — PHASE_1

How Reflex maps to each architectural topic in [[PHASE_1/agentic-architecture|PHASE_1]]. Coverage levels: **Covered**, **Partial**, **Gap**, **Different Approach**.

## Summary

| PHASE_1 Topic                    | Coverage           | Reflex Implementation                                                       |
| -------------------------------- | ------------------ | --------------------------------------------------------------------------- |
| Orchestration — Task Dispatch    | Partial            | Workflow orchestrator + semantic router via Claude Code's Task tool         |
| Orchestration — Agent Registry   | Partial            | Static catalog (2 agents + 43 skills in markdown). No dynamic registration. |
| Orchestration — Container Tokens | Gap                | No agent identity system                                                    |
| Orchestration — Message Routing  | Partial            | Claude Code IS the message bus (Task tool = star topology)                  |
| Orchestration — Policy Engine    | Partial            | Guardrails block destructive ops. No agent-to-agent authorization.          |
| Brainbox Lifecycle               | Gap                | No container provisioning, monitoring, or recycling                         |
| Brainbox Hardening               | Gap                | Docker patterns skill has guidance, no enforcement                          |
| Image Verification (cosign)      | Gap                | No image signing or verification                                            |
| Secrets Management               | Different Approach | `.env` files + `/reflex:init` credential setup                              |
| Observability                    | Covered            | LangFuse: full tool tracing, metrics, analytics                             |
| Shared State — Vector DB         | Covered            | Qdrant with ingestion pipeline, RAG proxy, collection isolation             |
| Shared State — Artifact Store    | Gap                | No dedicated artifact store                                                 |

---

## Orchestration

*PHASE_1 source: [[PHASE_1/arch-orchestration]]*

### Task Dispatch

**PHASE_1 specifies**: A Task Router receives work requests from users, resolves which agent handles them, and evaluates policy before dispatching.

**Reflex provides**: The `workflow-orchestrator` agent (`plugins/reflex/agents/workflow-orchestrator.md`) analyzes user input, manages tickets (Jira/GitHub), and dispatches work to specialized subagents. The `router-builder` skill (`plugins/reflex/skills/router-builder/`) provides intent routing patterns for agent task distribution. Claude Code's `Task` tool handles the actual dispatch mechanism.

**Coverage**: Partial — dispatch exists but is mediated by Claude's own Task tool rather than a dedicated Task Router process. The orchestrator agent adds workflow awareness on top of Claude's native dispatch.

### Agent Registry

**PHASE_1 specifies**: A catalog of available agents, their capabilities, and container images. Issues container tokens on provisioning.

**Reflex provides**: A static catalog of 2 agents and 43 skills defined in markdown files. The `/reflex:agents` and `/reflex:skills` commands enumerate them. Each skill has a `SKILL.md` describing its capabilities.

**Coverage**: Partial — the catalog exists but is static markdown, not a queryable registry. No dynamic registration, no capability negotiation, no container image mapping. Token issuance is not implemented.

### Container Tokens

**PHASE_1 specifies**: The orchestrator issues a unique token per container (agent name, task ID, capabilities, expiry). Every request carries the token. The orchestrator validates all requests against its registry.

**Reflex provides**: Nothing equivalent. Sub-agents are Claude Code sub-processes with no identity system. Trust is implicit — if Claude dispatches a task, the sub-agent is trusted.

**Coverage**: Gap

### Message Routing

**PHASE_1 specifies**: All inter-agent communication flows through the orchestrator (star topology). The Message Router handles request/reply and event patterns. No direct agent-to-agent connections.

**Reflex provides**: Claude Code's `Task` tool implements a star topology by design — all sub-agent communication passes through Claude. The `rag-proxy` agent (`plugins/reflex/agents/rag-proxy.md`) wraps other agents with Qdrant context, acting as a message enrichment layer.

**Coverage**: Partial — the star topology exists natively in Claude Code's architecture. However, there is no explicit Message Router component, no event subscription system, and no schema validation on inter-agent messages.

### Policy Engine

**PHASE_1 specifies**: Built-in rules for task authorization and message routing. Communication guardrails enforce token requirements, policy checks, schema validation, and logging on every message.

**Reflex provides**: The guardrail system (`plugins/reflex/scripts/guardrail.py`) blocks destructive operations via PreToolUse hooks. Patterns cover file deletion, git force push, database drops, cloud resource termination, container removal, and system modification. Severity levels: CRITICAL (block), HIGH/MEDIUM (confirm), LOW (warn).

**Coverage**: Partial — guardrails enforce safety constraints on tool use, but there is no agent-to-agent authorization policy, no message-level policy evaluation, and no schema validation for inter-agent communication.

---

## Brainbox Lifecycle

*PHASE_1 source: [[PHASE_1/arch-brainbox]]*

### Lifecycle Phases (Provision, Configure, Start, Monitor, Recycle)

**PHASE_1 specifies**: Every agent container follows a managed lifecycle: pull + verify image, inject secrets + apply hardening, launch agent, continuous health checks, teardown + scrub state. No container runs unbounded.

**Reflex provides**: No container lifecycle management. Agents are Claude Code sub-processes, not Docker containers. There is no provisioning, health monitoring, resource tracking, timeout enforcement, or state scrubbing.

**Coverage**: Gap — this is the largest divergence between Reflex and PHASE_1. Reflex operates at a fundamentally different abstraction level where Claude's runtime manages sub-process lifecycle.

### Image Verification

**PHASE_1 specifies**: All agent images must be verified with cosign before provisioning. Unsigned or invalid images are rejected.

**Reflex provides**: Nothing equivalent. There are no container images to verify.

**Coverage**: Gap

### Container Hardening

**PHASE_1 specifies**: seccomp default profile, drop dangerous capabilities (NET_RAW, SYS_ADMIN, etc.), read-only root filesystem, non-root user, no privilege escalation, tmpfs-only writable mounts.

**Reflex provides**: The `docker-patterns` skill (`plugins/reflex/skills/docker-patterns/SKILL.md`) documents container best practices including multi-stage builds and security hardening. The `kubernetes-patterns` skill (`plugins/reflex/skills/kubernetes-patterns/SKILL.md`) covers pod security contexts. These are **guidance only** — no enforcement mechanism exists.

**Coverage**: Gap — knowledge is available but not applied. Skills inform humans writing Dockerfiles; they don't enforce hardening on agent containers.

### Enforcement Boundaries

**PHASE_1 specifies**: Resource limits (CPU, memory, ephemeral storage), egress rules (allowlisted destinations only), mount policy (no host mounts, no Docker socket), timeouts (maximum TTL per container).

**Reflex provides**: Claude Code imposes its own execution timeouts on sub-agents. The guardrail system prevents some dangerous operations. No resource limits, egress rules, or mount policies exist.

**Coverage**: Gap

---

## Secrets Management

*PHASE_1 source: [[PHASE_1/arch-secrets-management]]*

**PHASE_1 specifies**: 1Password as single source of truth. `.envrc` references secrets by `op://` URI. `direnv` + `op` CLI resolves at shell entry. Secrets delivered as files on tmpfs (`/run/secrets/<name>`, mode 0400). Never in git, images, or `/proc/*/environ`.

**Reflex provides**: The `/reflex:init` command (`plugins/reflex/commands/init.md`) manages credentials for 7 services (LangFuse, Atlassian, Qdrant, Azure, Azure DevOps, GitHub, SQL Server). Credentials are stored in `.env` files and loaded as environment variables. The command provides interactive setup, validation, and status checking.

**Coverage**: Different Approach — Reflex manages credentials but through `.env` files and environment variables, not 1Password/direnv/tmpfs. The security properties differ:

| Property | PHASE_1 | Reflex |
|---|---|---|
| Secret store | 1Password vault | `.env` files on disk |
| Delivery | Files on tmpfs (mode 0400) | Environment variables |
| Git safety | `.envrc` contains only `op://` URIs | `.env` in `.gitignore` (convention) |
| `/proc` exposure | None (file-based) | Visible in `/proc/*/environ` |
| Rotation | Update 1Password, next start picks up | Edit `.env`, restart |

---

## Observability

*PHASE_1 source: [[PHASE_1/arch-observability]]*

**PHASE_1 specifies**: Structured JSON logs to stdout with consistent fields (timestamp, agent_name, task_id, container_token, level, message, metadata). Tracks task events, container events, message events, resource usage. Formal metrics, distributed traces, and redaction are deferred to PHASE_2.

**Reflex provides**: Full LangFuse integration (`docker/langfuse/docker-compose.yml`) — a 6-service observability stack (web UI, async worker, PostgreSQL, ClickHouse, Redis, MinIO). The `langfuse-hook.sh` script traces every tool use via PostToolUse hooks. The `langfuse-trace.py` script sends structured trace data to LangFuse. The `/reflex:langfuse` command controls the integration.

**Coverage**: Covered — and exceeds PHASE_1. See [[REFLEX/reflex-strengths|Strengths]] for details.

---

## Shared State

*PHASE_1 source: [[PHASE_1/arch-shared-state]]*

### Vector DB

**PHASE_1 specifies**: A local vector DB instance (Qdrant or ChromaDB) for semantic search, embeddings, conversation history, and knowledge base. All agents can access all data. Writes attributed by container token.

**Reflex provides**: Qdrant via Docker Compose (`docker/qdrant/docker-compose.yml`) with REST API (6333) and gRPC (6334). The `ingest.py` script (`plugins/reflex/scripts/ingest.py`) supports 11+ file formats (PDF, Markdown, HTML, EPUB, DOCX, Jupyter, code, Mermaid). The `rag-proxy` agent enriches tasks with stored knowledge. The `/reflex:qdrant` command controls the connection. The `/reflex:ingest` command triggers ingestion. Skills like `qdrant-patterns`, `rag-builder`, `knowledge-ingestion-patterns`, and `research-patterns` provide usage guidance.

**Coverage**: Covered — Qdrant is operational with ingestion, RAG proxy, and collection management. Write attribution uses session context rather than container tokens, but the functional requirement is met.

### Artifact Store

**PHASE_1 specifies**: A durable, addressable store for generated files, reports, and build artifacts. Local directory or S3-compatible store.

**Reflex provides**: No dedicated artifact store. LangFuse's MinIO instance provides S3-compatible storage but is used for observability data, not agent artifacts.

**Coverage**: Gap
