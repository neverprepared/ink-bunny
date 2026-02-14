# Threat Model

Four threat actors mapped to attack paths through the architecture. Risk assessed on a likelihood × impact quadrant.

## Threat Actors

| Actor | Description | Motivation |
|---|---|---|
| **T1: Compromised LLM Agent** | An agent whose LLM is manipulated via prompt injection, poisoned context, or adversarial input | Exfiltrate data, escalate privileges, corrupt shared state |
| **T2: Malicious Insider** | An authorized operator whose credentials are stolen or who acts maliciously | Access secrets, modify policies, manipulate agent behavior |
| **T3: Supply Chain** | Compromised dependency, base image, or build pipeline | Inject backdoors, establish persistence, access secrets |
| **T4: External Attacker** | No internal access — probing from outside the platform boundary | Gain initial access, move laterally, exfiltrate data |

## Attack Paths

### T1: Compromised Agent — Inside the Sandbox

```mermaid
graph TD
    LLM["Compromised LLM Agent<br/>(inside container)"]

    LLM --> ReadSecrets["Read /run/secrets/*"]
    LLM --> SpawnShell["Spawn shell process"]
    LLM --> WriteArtifacts["Write poisoned artifacts<br/>to shared state"]
    LLM --> Exfil["Exfiltrate via<br/>allowed egress"]
    LLM --> Escalate["Attempt container<br/>escape"]

    ReadSecrets --> SecretControl["Mitigated: scoped secrets,<br/>file mode 0400,<br/>envelope encryption"]
    SpawnShell --> ShellControl["Mitigated: distroless images,<br/>no shells available"]
    WriteArtifacts --> ArtifactControl["Mitigated: signed writes,<br/>namespace isolation"]
    Exfil --> ExfilControl["Mitigated: egress allowlist,<br/>network zones"]
    Escalate --> EscapeControl["Mitigated: seccomp, drop ALL caps,<br/>AppArmor, non-root, read-only rootfs"]

    style SecretControl fill:#cfc
    style ShellControl fill:#cfc
    style ArtifactControl fill:#cfc
    style ExfilControl fill:#cfc
    style EscapeControl fill:#cfc
```

### T2: Malicious Insider — Valid Credentials

```mermaid
graph TD
    Insider["Malicious Insider<br/>(valid credentials)"]

    Insider --> StealSecrets["Access 1Password<br/>vaults"]
    Insider --> ModifyPolicy["Modify OPA /<br/>Kyverno policies"]
    Insider --> InjectAgent["Deploy malicious<br/>agent image"]
    Insider --> TamperLogs["Tamper with<br/>observability data"]

    StealSecrets --> SecretControl2["Mitigated: envelope encryption,<br/>needs both 1Password + KMS"]
    ModifyPolicy --> PolicyControl["Mitigated: version-controlled<br/>policies, change logging"]
    InjectAgent --> ImageControl["Mitigated: cosign verification,<br/>vulnerability scanning"]
    TamperLogs --> LogControl["Partial: structured logs,<br/>token attribution"]

    style SecretControl2 fill:#cfc
    style PolicyControl fill:#cfc
    style ImageControl fill:#cfc
    style LogControl fill:#ffc
```

### T3: Supply Chain — Build Pipeline

```mermaid
graph TD
    Supply["Supply Chain<br/>Compromise"]

    Supply --> PoisonImage["Poisoned base<br/>image"]
    Supply --> PoisonDep["Compromised<br/>dependency"]
    Supply --> BuildTamper["Build pipeline<br/>manipulation"]
    Supply --> RegistryCompromise["Container registry<br/>compromise"]

    PoisonImage --> ImageControl2["Mitigated: distroless base,<br/>cosign, vuln scanning"]
    PoisonDep --> DepControl["Partial: vuln scanning<br/>catches known CVEs"]
    BuildTamper --> BuildControl["Partial: cosign signing<br/>verifies output integrity"]
    RegistryCompromise --> RegControl["Mitigated: cosign rejects<br/>unsigned/tampered images"]

    style ImageControl2 fill:#cfc
    style DepControl fill:#ffc
    style BuildControl fill:#ffc
    style RegControl fill:#cfc
```

### T4: External Attacker — No Initial Access

```mermaid
graph TD
    External["External Attacker<br/>(no internal access)"]

    External --> ProbeOrch["Probe orchestrator<br/>API"]
    External --> MITM["Traffic<br/>interception"]
    External --> DNSExfil["DNS-based<br/>exfiltration"]
    External --> DenialOfService["Denial of<br/>service"]

    ProbeOrch --> OrchControl["Mitigated: token validation,<br/>local auth only (CLI)"]
    MITM --> MITMControl["Partial: token on every request,<br/>mTLS deferred to PHASE_3"]
    DNSExfil --> DNSControl["Partial: egress allowlist,<br/>no Cilium DNS filtering yet"]
    DenialOfService --> DoSControl["Partial: rate limiting,<br/>resource limits per container"]

    style OrchControl fill:#cfc
    style MITMControl fill:#ffc
    style DNSControl fill:#ffc
    style DoSControl fill:#ffc
```

## Risk Quadrant

```mermaid
quadrantChart
    title Risk Assessment (Phase 2)
    x-axis Low Likelihood --> High Likelihood
    y-axis Low Impact --> High Impact
    quadrant-1 Mitigate Next
    quadrant-2 Monitor
    quadrant-3 Accept
    quadrant-4 Address Soon

    Container Escape: [0.15, 0.90]
    Secret Exfiltration: [0.25, 0.80]
    Supply Chain Poisoning: [0.30, 0.75]
    Compromised Agent Actions: [0.55, 0.55]
    Orchestrator DoS: [0.40, 0.60]
    DNS Exfiltration: [0.35, 0.45]
    Insider Policy Tampering: [0.20, 0.65]
    Log Tampering: [0.30, 0.40]
    External API Probe: [0.45, 0.30]
    Traffic Interception: [0.10, 0.50]
```

## Addressed in This Phase

| Threat | Key Mitigations |
|---|---|
| **Container Escape** | Full mandatory hardening: custom seccomp, drop ALL caps, AppArmor, non-root, read-only rootfs |
| **Secret Exfiltration** | Envelope encryption, file-based delivery, scoped vaults, egress allowlist |
| **Supply Chain** | cosign verification, vulnerability scanning, distroless images |
| **Agent Impersonation** | Container token on every request, orchestrator validation, capability scoping |
| **Cross-Agent Data Leak** | Namespace isolation, signed writes, authenticated proxy |
| **Insider Secrets Access** | Envelope encryption (needs both 1Password + KMS) |

## Outstanding Gaps

| Gap | Why It Persists | Addressed In |
|---|---|---|
| No cryptographic identity | Container tokens are bearer tokens, not cryptographic attestation | PHASE_3 (SPIRE/SVID) |
| No kernel-level network enforcement | Egress allowlist at container level, not eBPF | PHASE_3 (Cilium) |
| No runtime syscall monitoring | Prevention via seccomp/AppArmor, but no detection | PHASE_3 (Falco) |
| No tamper-proof audit trail | Structured logs with attribution, but no hash chain or WORM | PHASE_3 |
| No DNS filtering | Egress allowlist blocks IPs, not DNS tunneling | PHASE_3 (Cilium) |
| Compromised agent actions within scope | Agent can still misuse its legitimate capabilities | Accepted residual risk |
