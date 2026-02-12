# Threat Model

Defines what we are defending against, what assumptions we make, and where the known risks live.

## Threat Actors Overview

```mermaid
graph TD
    subgraph Actors["Threat Actors"]
        direction LR
        T1([T1: Compromised<br/>Agent])
        T2([T2: Malicious<br/>Insider])
        T3([T3: Supply<br/>Chain])
        T4([T4: External<br/>Attacker])
    end

    Orch((Orchestration<br/>Hub))

    T1 -.->|inside sandbox| Orch
    T2 -->|legitimate access| Orch
    T3 -.->|poisoned image| Orch
    T4 -.->|network access| Orch

    Orch --> Guard[Security Guardrails]
    Orch --> Comm[Agent Communication]
    Orch --> Observe[Observability]
    Orch --> State[(Shared State)]
    Orch --> Secrets[Secrets Mgmt]
```

Each threat actor has a different entry point and attack path through the architecture. Detailed paths below.

## Assumptions

Things we assume to be true. If any of these break, the security model degrades.

| Assumption | If violated |
|---|---|
| **Container runtime is sound** | Container escape → full host compromise |
| **Host OS is hardened** | Process inspection leaks secrets from `/proc/*/environ` |
| **1Password is not compromised** | All secrets are exposed — single point of failure |
| **Network between components is trusted (or encrypted)** | Eavesdropping on secrets, messages, logs in transit |
| **Agent images come from a trusted registry** | Poisoned images execute arbitrary code inside the sandbox |
| **The orchestrator is not compromised** | Attacker controls all task routing, policy, and identity issuance |
| **op CLI binary is authentic** | Tampered CLI could exfiltrate secrets at resolution time |

## Threat Catalog

### T1: Compromised Agent

An agent container runs malicious code — either through a supply chain attack or a prompt injection that causes the agent to act adversarially.

**Entry point**: Inside the sandbox — the agent is already running.

```mermaid
graph LR
    Agent([Compromised<br/>Agent])

    subgraph Sandbox["Container Sandbox"]
        EnvVars[Env Vars<br/>contains secrets]
        FS[Container FS<br/>full access]
    end

    Agent --> EnvVars
    Agent --> FS

    Orch((Orchestrator))
    State[(Shared State)]
    Host[Host Kernel]

    Agent -->|"1. exfiltrate secrets<br/>via allowed egress"| Orch
    Agent -->|"2. poison data<br/>forge attribution"| State
    Agent -->|"3. impersonate<br/>another agent"| Orch
    Agent -->|"4. flood messages<br/>DoS"| Orch
    Agent -.->|"5. container escape<br/>(kernel exploit)"| Host

    style Host stroke:#f00,stroke-width:2px
    style EnvVars stroke:#f90,stroke-width:2px
```

| # | Attack Path | Impact | Mitigation |
|---|---|---|---|
| 1 | Read env vars → exfiltrate over allowed egress | Credential theft | Scoped secrets per agent, short-lived tokens, egress DPI |
| 2 | Write poisoned data to shared state | Downstream agents consume bad data | Artifact signing, attribution verification |
| 3 | Forge identity on orchestrator | Actions attributed to wrong agent | Cryptographic agent identity (see Identity & Trust) |
| 4 | Flood the orchestrator | DoS on agent communication | Rate limiting, per-agent quotas |
| 5 | Exploit kernel to escape container | Full host compromise | Seccomp, AppArmor/SELinux, minimal capabilities, patched kernels |

---

### T2: Malicious Insider

An authorized user with legitimate access acts with bad intent.

**Entry point**: The orchestration layer — they have valid credentials.

```mermaid
graph LR
    Insider([Malicious<br/>Insider])

    Orch[Orchestration API]
    Policy[Policy Engine]
    Observe[Observability]
    Secrets[1Password Vaults]

    Insider -->|"valid credentials"| Orch
    Insider -->|"1. submit exfil task"| Orch
    Insider -->|"2. weaken policies"| Policy
    Insider -->|"3. read logs for<br/>intelligence"| Observe
    Insider -->|"4. rotate secrets<br/>to lock others out"| Secrets

    Orch --> Sandbox[Agent Sandbox]
    Sandbox -->|"exfiltrated data"| Egress[Allowed Egress]

    style Policy stroke:#f90,stroke-width:2px
    style Secrets stroke:#f90,stroke-width:2px
```

| # | Attack Path | Impact | Mitigation |
|---|---|---|---|
| 1 | Submit task → agent exfiltrates data over allowed egress | Data loss | Policy engine review, dual-approval for sensitive tasks, audit trail |
| 2 | Modify policies → grant excessive agent capabilities | Privilege escalation | Policy changes require MFA + peer approval, change audit log |
| 3 | Query observability stack → infer operations, extract PII | Information leakage | RBAC on logs/traces/metrics, data masking |
| 4 | Rotate secrets in 1Password → deny access to others | Availability impact | Vault access controls, break-glass procedures, rotation alerts |

---

### T3: Supply Chain Compromise

A dependency, base image, or tool in the build pipeline is compromised.

**Entry point**: Before the sandbox — the attack is baked into artifacts the platform trusts.

```mermaid
graph LR
    Attacker([Supply Chain<br/>Attacker])

    subgraph BuildPipeline["Build Pipeline"]
        BaseImage[Base Image]
        OpCLI[op CLI Binary]
        Direnv[direnv Hooks]
        BusDeps[Orchestrator<br/>Dependencies]
    end

    subgraph Runtime["What Gets Compromised"]
        Agent[Agent Container<br/>runs malicious code]
        SecretResolution[Secret Resolution<br/>exfiltrates at resolve time]
        CommLayer[Orchestrator<br/>intercepts all messages]
    end

    Attacker -->|"poison"| BaseImage & OpCLI & Direnv & BusDeps

    BaseImage -->|"1. malicious image<br/>passes pull"| Agent
    OpCLI -->|"2. tampered binary<br/>steals secrets"| SecretResolution
    Direnv -->|"3. hook intercepts<br/>env vars"| SecretResolution
    BusDeps -->|"4. compromised lib<br/>reads all traffic"| CommLayer

    style BuildPipeline stroke:#f00,stroke-width:2px
```

| # | Attack Path | Impact | Mitigation |
|---|---|---|---|
| 1 | Poisoned base image → arbitrary code in sandbox | Full agent compromise | Image signing (cosign), vulnerability scanning, approved base image list |
| 2 | Tampered op CLI → exfiltrate secrets at resolution | All secrets for that runner exposed | Checksum verification, pinned versions, signed releases |
| 3 | Malicious `.envrc` hook → intercept env vars pre-container | Secrets stolen before reaching sandbox | `.envrc` review in PR, restricted direnv allowed list |
| 4 | Compromised orchestrator dependency → read/modify all messages | Full communication interception | Dependency pinning, SBOM generation, regular audits |

---

### T4: External Attacker

Network-level access to the platform, but no legitimate credentials.

**Entry point**: The network boundary — they can see traffic and probe exposed services.

```mermaid
graph LR
    Attacker([External<br/>Attacker])

    subgraph Network["Network Boundary"]
        Traffic[Component Traffic<br/>unencrypted?]
        API[Orchestration API<br/>exposed endpoint]
        DNS[Container DNS<br/>resolver]
    end

    subgraph Targets["Targets"]
        Secrets[Secrets in Transit]
        Orch[Orchestration<br/>Full Control]
        Data[Exfiltrated Data]
        Host[Host Kernel]
    end

    Attacker -->|"1. sniff traffic"| Traffic --> Secrets
    Attacker -->|"2. probe API"| API --> Orch
    Attacker -->|"3. DNS tunnel<br/>from container"| DNS --> Data
    Attacker -.->|"4. kernel exploit<br/>container escape"| Host

    style Traffic stroke:#f00,stroke-width:2px
    style API stroke:#f90,stroke-width:2px
```

| # | Attack Path | Impact | Mitigation |
|---|---|---|---|
| 1 | Sniff unencrypted traffic between components | Eavesdrop on secrets, messages, logs | mTLS between all platform components |
| 2 | Probe orchestration API → brute force or exploit | Full system control | Authentication required, rate limiting, network segmentation |
| 3 | DNS exfiltration from inside container | Data leak bypassing egress rules | DNS filtering/logging, restricted resolvers, egress DNS inspection |
| 4 | Exploit host kernel from network | Container escape, host compromise | Kernel patching cadence, minimal host surface, VM isolation for high-risk |

## Risk Matrix

Context: solo operator, mix of LLM-driven and static agents, multi-environment (local dev + cloud CI + self-hosted K8s).

### Pre-Mitigation (architecture only)

```mermaid
quadrantChart
    title Before Security Tooling
    x-axis Low Likelihood --> High Likelihood
    y-axis Low Impact --> High Impact
    quadrant-1 Mitigate Immediately
    quadrant-2 Plan Mitigation
    quadrant-3 Monitor
    quadrant-4 Accept or Defer
    Compromised LLM Agent: [0.75, 0.8]
    Supply Chain Poisoning: [0.5, 0.9]
    Secret Exfiltration: [0.65, 0.85]
    Container Escape: [0.3, 0.9]
    External API Probe: [0.55, 0.75]
    DNS Exfiltration: [0.45, 0.55]
    Traffic Interception: [0.5, 0.7]
    Orchestrator DoS: [0.45, 0.35]
    Insider Acct Takeover: [0.15, 0.7]
    Log Injection: [0.55, 0.3]
```

### Post-Mitigation (with [[arch-security-tooling|Security Tooling]])

```mermaid
quadrantChart
    title After Security Tooling
    x-axis Low Likelihood --> High Likelihood
    y-axis Low Impact --> High Impact
    quadrant-1 Mitigate Immediately
    quadrant-2 Plan Mitigation
    quadrant-3 Monitor
    quadrant-4 Accept or Defer
    Compromised LLM Agent: [0.7, 0.5]
    Supply Chain Poisoning: [0.3, 0.65]
    Secret Exfiltration: [0.4, 0.5]
    Container Escape: [0.15, 0.7]
    External API Probe: [0.25, 0.45]
    DNS Exfiltration: [0.2, 0.35]
    Traffic Interception: [0.1, 0.25]
    Orchestrator DoS: [0.3, 0.25]
    Insider Acct Takeover: [0.1, 0.5]
    Log Injection: [0.35, 0.2]
```

### Tuning Rationale

| Threat | Before | After | Tooling That Moved It |
|---|---|---|---|
| **Compromised LLM Agent** | 0.75 / 0.80 | 0.70 / 0.50 | Likelihood stays high (prompt injection still works). Impact halved — Cilium blocks exfiltration, Falco detects anomalies, OPA limits actions, Envoy validates identity. |
| **Supply Chain Poisoning** | 0.50 / 0.90 | 0.30 / 0.65 | Kyverno blocks unapproved images at admission. cosign rejects unsigned images. Falco catches anomalous behavior if one slips through. |
| **Secret Exfiltration** | 0.65 / 0.85 | 0.40 / 0.50 | Cilium kernel-level egress blocks unauthorized destinations. Falco detects /proc/*/environ reads. OPA scopes secret access. Multiple layers to punch through. |
| **Container Escape** | 0.30 / 0.90 | 0.15 / 0.70 | Kyverno prevents privileged containers at admission. Falco detects escape syscalls and auto-recycles. Dwell time near zero. |
| **External API Probe** | 0.55 / 0.75 | 0.25 / 0.45 | Envoy mTLS rejects unauthenticated connections at TLS handshake. Probes never reach the orchestrator. |
| **Traffic Interception** | 0.50 / 0.70 | 0.10 / 0.25 | Envoy + SPIRE mTLS encrypts all traffic. Effectively solved — residual only if mTLS misconfigured. |
| **DNS Exfiltration** | 0.45 / 0.55 | 0.20 / 0.35 | Cilium intercepts all DNS at kernel level, enforces resolver allowlists, detects tunneling patterns. |
| **Orchestrator DoS** | 0.45 / 0.35 | 0.30 / 0.25 | Envoy rate limiting at proxy layer before traffic hits orchestrator. |
| **Insider Acct Takeover** | 0.15 / 0.70 | 0.10 / 0.50 | OPA enforces granular policy. Stolen credentials are constrained by declarative rules. |
| **Log Injection** | 0.55 / 0.30 | 0.35 / 0.20 | Falco process monitoring + SVID attribution flags unsigned entries. |

### Quadrant Shift Summary

| Quadrant | Before | After |
|---|---|---|
| **Mitigate Immediately** | Compromised LLM Agent, Secret Exfiltration, Supply Chain | — empty — |
| **Plan Mitigation** | Container Escape, External API Probe, Traffic Interception | Compromised LLM Agent (only remaining high-area threat) |
| **Monitor** | DNS Exfiltration, Orchestrator DoS | Supply Chain, Secret Exfiltration, Container Escape, External API Probe, Insider Acct Takeover |
| **Accept or Defer** | Log Injection, Insider Acct Takeover | Traffic Interception, DNS Exfiltration, Orchestrator DoS, Log Injection |

## Addressed Gaps

| Gap | Addressed By | Page |
|---|---|---|
| ~~Encryption in transit (mTLS)~~ | Envoy + SPIRE x509 SVIDs | [[arch-security-tooling]], [[arch-identity-and-trust]] |
| ~~Container runtime hardening~~ | Falco syscall monitoring + Kyverno admission (no privileged containers) | [[arch-security-tooling]] |
| ~~Network segmentation~~ | Cilium identity-aware eBPF networking | [[arch-security-tooling]] |
| ~~Secret exfiltration prevention~~ | Cilium egress enforcement + Falco secret access monitoring | [[arch-security-tooling]] |
| ~~DNS exfiltration~~ | Cilium DNS filtering | [[arch-security-tooling]] |

## Outstanding Gaps (to be addressed)

| Gap | Related Page | Priority |
|---|---|---|
| Host hardening requirements | New page needed | High |
| Incident response procedures | New page needed | High |
| Shared state access control (RBAC) | [[arch-shared-state]] | Medium |
| Log integrity (signing, WORM) | [[arch-observability]] | Medium |
| Security control testing/validation | New page needed | Low |
