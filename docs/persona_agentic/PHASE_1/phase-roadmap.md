# Phase Roadmap

Three design maturity phases. Each phase is a self-contained architecture — not an environment promotion.

| Phase | Maturity | Theme |
|---|---|---|
| **PHASE_1** | Foundation | Core patterns working locally — containers, secrets, logging |
| **PHASE_2** | Hardened | Security hardening, operational maturity — container tokens, network zones, envelope encryption, incident response |
| **PHASE_3** | Full Spec | Production-ready — all security tooling, full PKI hierarchy, forensic capture, solo operator safety |

## Topic Progression

| Topic | PHASE_1 | PHASE_2 | PHASE_3 |
|---|---|---|---|
| **Brainbox Runtime** | Docker | Docker | Docker + kind/vcluster |
| **Brainbox Hardening** | Basic (seccomp default, drop dangerous caps, read-only rootfs, non-root) | Full mandatory baseline (custom seccomp, drop ALL caps, AppArmor, PID isolation) | Full mandatory baseline |
| **Image Policy** | cosign keyless signing (CI) + keyless/key-based verification (brainbox), dev images with debugging tools | Distroless required, vulnerability scanning | Distroless required, approved base image policy, static binaries |
| **Identity** | No identity system — implicit trust, containers identified by Docker labels | Orchestrator-issued container tokens (agent name, task ID, capabilities, expiry) | Full SPIRE, SVID type policy (x509/JWT), aggressive TTLs, HSM root CA, deny-list revocation, replay protection |
| **Secrets** | 1Password + direnv, file-based tmpfs delivery | Envelope encryption (KEK/DEK), OIDC federation for CI | Full envelope encryption, break-glass procedure |
| **Orchestrator** | Single process: task dispatch, agent registry, built-in policy, message routing | State persistence, degraded mode | Resilience (watchdog, safe mode, dead-man switch) |
| **Communication** | Star topology, request/reply + events, internal delegation (merged into Orchestration) | Separate page: external delegation, broadcast | Full delegation model, scope-based policy |
| **Network** | Docker bridge, basic egress allowlist (merged into Container Lifecycle) | Network zones (3-tier), default-deny between agents | Full zone isolation, SPIRE server isolation, Envoy bypass prevention |
| **Observability** | Structured JSON logs | Add distributed traces, data classification, redaction pipeline | Full redaction, hash-chained audit trail, WORM storage |
| **Shared State** | Vector DB + Artifact Store, direct access | Authenticated proxy, namespace isolation, signed writes | Full namespace isolation, quarantine, per-namespace encryption |
| **Security Tooling** | None — orchestrator built-in policy only | OPA + Kyverno | Full suite: Envoy, OPA, Cilium, Falco, Kyverno (all flaggable) |
| **Incident Response** | Container recycle is the response | IR runbooks, forensic capture before recycle | Full IR lifecycle, escalation matrix, known-good baseline |
| **Threat Model** | Container isolation is the primary control | Attack path analysis, risk quadrant | Full threat model with before/after risk assessment |
| **Operator Safety** | N/A — operator is at the keyboard | Basic monitoring | Dead-man switch, auto-safe-mode, backup contact |

## What's in Each Phase

### PHASE_1 (this folder)

```
agentic-architecture.md    — Overview (hub-spoke, 4 spokes)
arch-orchestration.md      — Task dispatch + message routing + communication
arch-brainbox.md           — Lifecycle phases + hardening + enforcement boundaries
arch-secrets-management.md  — 1Password + direnv + tmpfs delivery
arch-observability.md       — Structured JSON logs
arch-shared-state.md        — Vector DB + Artifact Store
```

### Added in PHASE_2

```
arch-identity-and-trust.md  — Container tokens, token lifecycle, image verification (NEW)
arch-security-guardrails.md — Network zones + full hardening (NEW)
arch-agent-communication.md — External delegation + broadcast (NEW)
arch-security-tooling.md    — OPA + Kyverno (NEW)
arch-threat-model.md        — Attack paths + risk quadrant (NEW)
arch-incident-response.md   — IR runbooks + forensic capture (NEW)
```

### Added in PHASE_3

```
SPIRE/SVID workload identity (replaces container tokens)
Full security tooling suite (Envoy, Cilium, Falco added)
Full PKI hierarchy (HSM root CA, intermediate CA)
SVID deny-list revocation + replay protection + mTLS
Break-glass procedure for secrets
Orchestrator resilience (watchdog, dead-man switch, safe mode)
Hash-chained audit trail + WORM storage
Shared state quarantine + per-namespace encryption
Full IR lifecycle + escalation matrix + known-good baseline
Solo operator safety (dead-man switch, backup contact)
TODO/security-review-findings.md — Detailed security audit findings
```
