# Incident Response

Procedures for detecting, containing, investigating, and recovering from security incidents. Every automated response includes a forensic capture step before destructive action.

## Response Lifecycle

```mermaid
graph LR
    Detect[Detect<br/>alert triggered]
    Capture[Capture<br/>forensic snapshot]
    Contain[Contain<br/>isolate + revoke]
    Investigate[Investigate<br/>analyze evidence]
    Recover[Recover<br/>restore + verify]
    PostMortem[Post-Mortem<br/>update defenses]

    Detect --> Capture --> Contain --> Investigate --> Recover --> PostMortem
```

| Phase | What Happens | Who |
|---|---|---|
| **Detect** | Alert from Falco, Cilium, OPA, Envoy, or observability anomaly | Automated |
| **Capture** | Forensic snapshot of container state before any destructive action | Automated |
| **Contain** | Revoke SVID, quarantine shared state, isolate network | Automated (with circuit breaker) |
| **Investigate** | Analyze captured evidence, trace attack path, assess blast radius | Operator |
| **Recover** | Rotate affected secrets, verify known-good state, resume operations | Operator |
| **Post-Mortem** | Update policies, rules, and documentation based on findings | Operator |

## Forensic Capture

Every automated response (container recycle, SVID revocation) must capture forensic evidence **before** destroying the container.

```mermaid
sequenceDiagram
    participant Alert as Alert Source
    participant Orch as Orchestrator
    participant Container as Agent Container
    participant Evidence as Evidence Store<br/>(WORM)

    Alert->>Orch: security alert (container ID, severity)
    Orch->>Container: pause container (SIGSTOP)
    Orch->>Container: capture snapshot
    Note over Container: process list, open files,<br/>network connections,<br/>filesystem diff, memory dump (if critical)
    Orch->>Evidence: store snapshot (signed, timestamped)
    Orch->>Container: proceed with containment (revoke SVID, recycle)
```

| Captured Data | How | Retention |
|---|---|---|
| **Process list** | `ps aux` equivalent from `/proc` | 90 days |
| **Open file descriptors** | `/proc/<pid>/fd` snapshot | 90 days |
| **Network connections** | `/proc/<pid>/net/tcp` + Cilium flow log | 90 days |
| **Filesystem diff** | Overlay diff layer (changes from image baseline) | 90 days |
| **Container logs** | Full stdout/stderr captured before recycle | 90 days |
| **tmpfs contents** | `/workspace`, `/tmp` snapshot (NOT `/run/secrets`) | 90 days, encrypted |
| **Memory dump** | Full process memory (critical severity only) | 30 days, encrypted, restricted access |

Forensic snapshots are stored in a WORM (write-once-read-many) evidence store, signed by the orchestrator's identity, and never modified after creation.

## Runbooks by Threat Actor

### T1: Compromised LLM Agent

```mermaid
graph TD
    Trigger["Falco: unexpected syscall,<br/>process spawn, or<br/>secret file access"]
    Capture1["Capture forensic snapshot"]
    Revoke["Revoke SVID<br/>(deny-list + delete registration)"]
    Quarantine["Quarantine agent's<br/>shared state data"]
    Notify["Notify downstream agents<br/>that consumed this agent's data"]
    Investigate1["Investigate: what did<br/>the agent access?<br/>What data did it write?"]
    Rotate["Rotate secrets the<br/>agent had access to"]
    Verify["Verify shared state<br/>integrity (signature check)"]

    Trigger --> Capture1 --> Revoke --> Quarantine --> Notify --> Investigate1 --> Rotate --> Verify
```

| Step | Detail |
|---|---|
| **Contain** | Revoke SVID, quarantine shared state, recycle container (after capture) |
| **Blast radius** | Limited: agent had own-namespace secrets, own-namespace shared state, allowlisted egress only |
| **Investigate** | Check artifact signatures, trace Cilium flow logs for exfiltration, review observability traces |
| **Recover** | Rotate affected secrets, re-verify quarantined data, resume with fresh container |

### T2: Malicious Insider

```mermaid
graph TD
    Trigger2["Anomalous operator<br/>behavior detected<br/>(OPA / audit trail)"]
    Capture2["Preserve full<br/>audit trail"]
    Freeze["Freeze: disable<br/>operator API token"]
    Scope["Scope: which vaults,<br/>policies, and agents<br/>were accessed?"]
    RotateAll["Rotate all secrets<br/>in accessed vaults"]
    ReviewPolicy["Review all policy<br/>changes for backdoors"]
    RestoreBaseline["Restore policies<br/>from known-good baseline"]

    Trigger2 --> Capture2 --> Freeze --> Scope --> RotateAll --> ReviewPolicy --> RestoreBaseline
```

| Step | Detail |
|---|---|
| **Contain** | Revoke operator credentials immediately — backup contact has emergency shutdown only |
| **Blast radius** | Potentially full — operator has broad access. Envelope encryption limits secret exposure (needs both 1Password + KMS). |
| **Investigate** | Audit trail hash chain verification, review all policy changes, check for SPIRE registration entry manipulation |
| **Recover** | Rotate all secrets, restore policies from version control, re-attest all running containers |

### T3: Supply Chain Compromise

```mermaid
graph TD
    Trigger3["Image scan: unexpected<br/>layer change, failed<br/>signature, or new CVE"]
    Block["Block: reject image<br/>at Provision gate"]
    Identify["Identify: which<br/>containers are running<br/>the compromised image?"]
    CaptureAll["Capture forensic<br/>snapshots for all<br/>affected containers"]
    RecycleAll["Recycle all affected<br/>containers"]
    Quarantine3["Quarantine shared<br/>state from affected<br/>containers"]
    PatchRebuild["Patch and rebuild<br/>from trusted base"]

    Trigger3 --> Block --> Identify --> CaptureAll --> RecycleAll --> Quarantine3 --> PatchRebuild
```

| Step | Detail |
|---|---|
| **Contain** | Block compromised image, recycle all running instances, quarantine their shared state |
| **Blast radius** | All containers running the affected image — could be multiple agents |
| **Investigate** | Diff image layers against known-good, check for embedded backdoors, trace supply chain |
| **Recover** | Rebuild from trusted base, re-sign with cosign, redeploy, verify shared state integrity |

### T4: External Attacker

```mermaid
graph TD
    Trigger4["Envoy: mTLS rejection,<br/>Cilium: blocked egress,<br/>or anomalous inbound"]
    LogCapture["Capture connection<br/>details and flow logs"]
    BlockSource["Block source IP/range<br/>at network edge"]
    Assess["Assess: did any<br/>traffic reach agents?"]
    AuditCheck["Verify audit trail<br/>integrity (hash chain)"]
    Harden["Harden: tighten<br/>egress rules, review<br/>exposed endpoints"]

    Trigger4 --> LogCapture --> BlockSource --> Assess --> AuditCheck --> Harden
```

| Step | Detail |
|---|---|
| **Contain** | Block at network edge, verify no compromise inside perimeter |
| **Blast radius** | Typically zero if mTLS and network policies held — external attacker has no valid SVID |
| **Investigate** | Review Envoy access logs, Cilium flow logs, check for any successful connections |
| **Recover** | Update network policies, rotate any exposed endpoints, verify no persistence |

## Known-Good Baseline

A verified reference state used to confirm recovery is complete.

| Component | Baseline Definition | Verification |
|---|---|---|
| **Agent images** | Signed image digests in approved registry | `cosign verify` against pinned key |
| **OPA policies** | Version-controlled Rego files at tagged commit | Git hash comparison |
| **Kyverno policies** | Version-controlled YAML at tagged commit | Git hash comparison |
| **SPIRE configuration** | Version-controlled registration entries | Diff against running state |
| **1Password vaults** | Expected secret count and last-rotated timestamps | Automated inventory check |
| **Orchestrator config** | Version-controlled configuration at tagged commit | Git hash comparison |
| **Shared state integrity** | All artifacts pass SVID signature verification | Background integrity scan |

## Escalation

| Severity | Automated Response | Operator Action Required |
|---|---|---|
| **Low** | Log to observability | Review during next session |
| **Medium** | Log + alert operator | Investigate within 4 hours |
| **High** | Capture + contain + alert | Investigate immediately |
| **Critical** | Capture + contain + safe mode + alert backup contact | Investigate immediately, consider full shutdown |
