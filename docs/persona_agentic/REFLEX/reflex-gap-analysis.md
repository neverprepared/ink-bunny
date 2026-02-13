# Reflex Gap Analysis — PHASE_1

Gaps that would need to be addressed to bring Reflex up to full [[PHASE_1/agentic-architecture|PHASE_1]] compliance. Each gap references the specific PHASE_1 requirement.

## Gap Summary

| Gap | Severity | PHASE_1 Source |
|---|---|---|
| Brainbox Lifecycle Management | Critical | [[PHASE_1/arch-brainbox]] |
| Agent Identity System | High | [[PHASE_1/arch-orchestration]] |
| Image Verification | High | [[PHASE_1/arch-brainbox]] |
| Secrets Delivery Model | Medium | [[PHASE_1/arch-secrets-management]] |
| Brainbox Hardening Enforcement | High | [[PHASE_1/arch-brainbox]] |
| Artifact Store | Medium | [[PHASE_1/arch-shared-state]] |
| Agent-to-Agent Policy | Medium | [[PHASE_1/arch-orchestration]] |

---

## 1. Brainbox Lifecycle Management

**What's missing**: The entire container lifecycle — provision, configure, start, monitor, recycle. Reflex has no mechanism to create Docker containers for agents, track their health, enforce timeouts, or clean up state after completion.

**Why it matters**: PHASE_1's security model depends on container isolation. Without containers, agents share Claude's process space with no resource boundaries, no filesystem isolation, and no teardown guarantees. This is the foundational gap — most other gaps (hardening, identity, secrets delivery) depend on containers existing.

**PHASE_1 requirement**: [[PHASE_1/arch-brainbox]] defines a 5-phase lifecycle (Provision → Configure → Start → Monitor → Recycle) with restart policies, orphan reaping, and ephemeral state guarantees.

**Current Reflex state**: Agents are Claude Code sub-processes. Claude's runtime provides basic execution timeouts but no container-level lifecycle management. The `docker-patterns` and `kubernetes-patterns` skills provide guidance for writing Dockerfiles and manifests, but nothing provisions or manages agent containers.

---

## 2. Agent Identity System

**What's missing**: Container tokens — unique identifiers issued per agent instance that carry agent name, task ID, capabilities, and expiry. No mechanism for agents to authenticate requests or for the orchestrator to validate agent identity.

**Why it matters**: Without identity tokens, there is no way to attribute actions to specific agent instances, enforce capability-based access control, or audit which agent performed which operation. PHASE_1's observability and policy systems both depend on container tokens.

**PHASE_1 requirement**: [[PHASE_1/arch-orchestration]] specifies that the orchestrator generates a container token on provisioning, injects it via `/run/secrets/agent-token`, and validates it on every request. Token fields: Token ID, Agent name, Task ID, Capabilities, Expiry.

**Current Reflex state**: Trust is implicit. If Claude dispatches a task via the Task tool, the sub-agent is trusted. LangFuse traces identify operations by tool name and session, not by agent identity.

---

## 3. Image Verification

**What's missing**: cosign signature verification for agent images before provisioning. No image signing, no signature checking, no rejection of unsigned images.

**Why it matters**: Without image verification, there is no supply chain integrity guarantee. PHASE_1 requires that only signed images can be provisioned — this prevents tampered or unauthorized agent code from running.

**PHASE_1 requirement**: [[PHASE_1/arch-brainbox]] requires cosign verification at the Provision phase. Unsigned or invalid images are rejected. Later phases add vulnerability scanning and distroless base image requirements.

**Current Reflex state**: No container images exist to verify. Agent definitions are markdown files loaded by Claude Code. The plugin itself is installed from a GitHub repository with no signature verification.

---

## 4. Secrets Delivery Model

**What's missing**: The 1Password + direnv + tmpfs delivery chain. Secrets currently live in `.env` files on disk and are loaded as environment variables, which exposes them in `/proc/*/environ`.

**Why it matters**: PHASE_1's secrets model eliminates three attack vectors: secrets in git (only `op://` URIs are committed), secrets in images (runtime delivery via tmpfs), and secrets in `/proc` (file-based, not env vars). Reflex's `.env` approach leaves secrets on disk and in process environment.

**PHASE_1 requirement**: [[PHASE_1/arch-secrets-management]] specifies 1Password as the single source of truth, `.envrc` with `op://` URIs, `direnv` + `op` CLI resolution, and delivery as files on tmpfs at `/run/secrets/<name>` with mode 0400.

**Current Reflex state**: The `/reflex:init` command (`plugins/reflex/commands/init.md`) manages credentials for 7 services via `.env` files. This is functional but has weaker security properties than the PHASE_1 model.

---

## 5. Brainbox Hardening Enforcement

**What's missing**: Enforced security controls — seccomp profiles, capability dropping, read-only root filesystem, non-root user, privilege escalation prevention. Reflex has skills that *describe* these patterns but nothing that *applies* them.

**Why it matters**: Hardening reduces the blast radius of a compromised agent. Without enforcement, an agent process could access the host filesystem, escalate privileges, or make unrestricted network connections.

**PHASE_1 requirement**: [[PHASE_1/arch-brainbox]] specifies: seccomp default profile, drop NET_RAW/SYS_ADMIN/MKNOD/SYS_CHROOT/NET_ADMIN, read-only rootfs, non-root user (65534), no-new-privileges, tmpfs-only writable mounts.

**Current Reflex state**: The `docker-patterns` skill documents multi-stage builds and security best practices. The `kubernetes-patterns` skill covers pod security contexts. These are informational — a human writing a Dockerfile could follow them, but Reflex does not enforce them when running agents.

---

## 6. Artifact Store

**What's missing**: A dedicated, addressable store for durable agent outputs (generated files, reports, build artifacts).

**Why it matters**: PHASE_1 requires that anything outliving a container goes to Shared State. Without an artifact store, agent outputs either stay in Claude's context (lost on session end) or are written to local filesystem (unstructured, unattributed).

**PHASE_1 requirement**: [[PHASE_1/arch-shared-state]] specifies an Artifact Store alongside the Vector DB — local directory or S3-compatible store, with token-attributed writes.

**Current Reflex state**: Qdrant handles semantic data (embeddings, documents). LangFuse's MinIO instance is S3-compatible but dedicated to observability data. No general-purpose artifact store exists for agent outputs.

---

## 7. Agent-to-Agent Authorization Policy

**What's missing**: Policy rules that govern which agents can communicate with which other agents, and what operations they can request.

**Why it matters**: PHASE_1's policy engine evaluates every inter-agent message against built-in rules. Without this, any sub-agent could theoretically request any operation from any other sub-agent (mediated only by Claude's own judgment).

**PHASE_1 requirement**: [[PHASE_1/arch-orchestration]] specifies a Policy Engine with built-in rules for task authorization and message routing. Communication guardrails require token validation, policy check, schema validation, and logging on every message.

**Current Reflex state**: The guardrail system (`plugins/reflex/scripts/guardrail.py`) blocks destructive *tool use* — it evaluates Bash commands, file writes, and edits against dangerous patterns. This is tool-level safety, not agent-to-agent authorization. There is no mechanism to say "agent A may not dispatch tasks to agent B" or "agent A may only read from Qdrant, not write."
