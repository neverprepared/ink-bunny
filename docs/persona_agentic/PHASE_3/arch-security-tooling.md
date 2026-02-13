# Security Tooling

Runtime security has two tiers: a **mandatory hardening baseline** that is always on, and **optional tooling** that is flaggable per environment.

## Mandatory Baseline (always on)

These controls apply in every environment. They cannot be disabled via feature flags.

```mermaid
graph TD
    subgraph Mandatory["Mandatory (always on, every environment)"]
        direction LR
        Hardening[Container Hardening<br/>seccomp, caps, rootfs,<br/>non-root, AppArmor]
        SecretsDelivery[File-Based Secrets<br/>tmpfs, mode 0400<br/>no env vars]
        SPIRE_Sidecar[SPIRE Sidecar Isolation<br/>separate container<br/>shared socket only]
        OrchestratorPolicy[Orchestrator Policy<br/>built-in identity validation<br/>rate limiting, config validation]
    end
```

| Control | What It Enforces | Fallback If Absent |
|---|---|---|
| **Container hardening** | seccomp, drop all caps, read-only rootfs, non-root, no-new-privileges, AppArmor | None — this IS the foundation |
| **File-based secrets** | Secrets on tmpfs, not env vars — eliminates /proc/*/environ exposure | None — mandatory delivery mechanism |
| **SPIRE sidecar isolation** | Separate container, Unix socket only, no shared PID namespace | None — prevents SVID key theft |
| **Orchestrator built-in policy** | Identity validation, rate limiting, container config validation | None — orchestrator always runs |

See [[arch-brainbox#Mandatory Brainbox Hardening]] for the full hardening spec.

## Optional Tooling (flaggable)

Five additional tools, all independent. Environments choose which layers to enable based on risk profile.

```mermaid
graph TD
    subgraph Flags["Feature Flags"]
        direction LR
        F1[/Envoy\]
        F2[/OPA\]
        F3[/Cilium\]
        F4[/Falco\]
        F5[/Kyverno\]
    end

    subgraph Network["Network Path"]
        Envoy[Envoy + SPIRE<br/>mTLS, identity validation<br/>traffic inspection]
    end

    subgraph Policy["Policy Decisions"]
        OPA[Open Policy Agent<br/>authorize every action<br/>declarative rules]
    end

    subgraph Kernel["Kernel / Runtime"]
        Cilium[Cilium eBPF<br/>DNS filtering, egress enforcement<br/>identity-aware networking]
        Falco[Falco<br/>syscall monitoring<br/>escape detection]
    end

    subgraph Admission["Admission Control"]
        Kyverno[Kyverno<br/>validate infra configs<br/>enforce resource policies]
    end

    F1 -.->|on/off| Envoy
    F2 -.->|on/off| OPA
    F3 -.->|on/off| Cilium
    F4 -.->|on/off| Falco
    F5 -.->|on/off| Kyverno
```

## Where Each Tool Sits

```mermaid
graph TD
    User([User / Operator])
    Orch((Orchestrator))

    User --> Orch

    subgraph SecurityTooling["Security Tooling (all optional)"]

        Kyverno[Kyverno<br/>Admission]
        Envoy[Envoy<br/>Network Path]
        OPA[OPA<br/>Policy]
        Cilium[Cilium<br/>Kernel]
        Falco[Falco<br/>Runtime]

    end

    subgraph Sandbox["Container Sandbox"]
        Agent1[Agent A]
        Agent2[Agent B]
        Agent3[Agent N]
    end

    Orch -->|"provision"| Kyverno
    Kyverno -->|"validated config"| Sandbox
    Agent1 & Agent2 & Agent3 <-->|"traffic"| Envoy
    Envoy <-->|"validated requests"| Orch
    Orch -->|"should this be allowed?"| OPA
    Cilium -.->|"kernel-level enforcement"| Sandbox
    Falco -.->|"syscall monitoring"| Sandbox

    Observe[Observability]
    Falco & Cilium & Envoy & OPA --> Observe
```

## Tool Details

### Envoy + SPIRE — Network Path

Sits between agents and the orchestrator. Validates identity and inspects traffic.

```mermaid
graph LR
    Agent[Agent] -->|request + SVID| Envoy
    Envoy -->|"1. verify SVID<br/>via SPIRE"| SPIRE[SPIRE]
    Envoy -->|"2. inspect payload"| Envoy
    Envoy -->|"3. forward if valid"| Orch((Orchestrator))
    Envoy -.->|"invalid → reject"| Reject([Block])

    style Reject stroke:#f00,stroke-width:2px
```

| Function | Detail |
|---|---|
| **mTLS termination** | Enforces encrypted connections using SPIFFE x509 SVIDs |
| **Identity validation** | Verifies the agent's SVID is valid and matches the expected workload |
| **Traffic inspection** | Can inspect request payloads for schema violations or anomalies |
| **Rate limiting** | Per-agent request quotas at the proxy layer |
| **When disabled** | Agents connect directly to orchestrator — orchestrator handles validation itself |

#### Bypass Prevention

When Envoy is enabled, all traffic **must** flow through it. Direct connections to the orchestrator are blocked.

```mermaid
graph LR
    subgraph Container["Agent Container"]
        Agent[Agent Process]
        InitContainer["Init Container<br/>iptables redirect"]
    end

    subgraph Enforcement["Bypass Prevention"]
        IPTables["iptables REDIRECT<br/>all outbound → Envoy port"]
        NetPolicy["NetworkPolicy<br/>egress only to Envoy port"]
    end

    Envoy[Envoy Sidecar]
    Orch((Orchestrator))

    InitContainer -->|"on start"| IPTables
    Agent -->|"forced through"| Envoy
    Envoy -->|"validated"| Orch
    Agent -.->|"direct path blocked"| Blocked([Block])

    style Blocked stroke:#f00,stroke-width:2px
```

| Control | Detail |
|---|---|
| **iptables redirect** | Init container sets `iptables -t nat -A OUTPUT -p tcp --dport <orch-port> -j REDIRECT --to-port <envoy-port>` |
| **NetworkPolicy** | Egress allowed only to Envoy's listener port — direct orchestrator port denied |
| **CI validation** | Bypass prevention rules verified in CI before deployment |
| **Envoy health gate** | Container does not start accepting work until Envoy sidecar passes health check |

### OPA — Policy Decisions

Evaluates "should this be allowed?" at every enforcement point. Policies are declarative Rego files, not code.

```mermaid
graph LR
    Orch((Orchestrator)) -->|"query: can Agent A<br/>do action X?"| OPA[OPA]
    OPA -->|"evaluate policy"| Policies[(Rego<br/>Policies)]
    OPA -->|"allow / deny<br/>+ reason"| Orch

    Orch2((Orchestrator)) -->|"query: can Agent A<br/>talk to Agent B?"| OPA
    Orch3((Orchestrator)) -->|"query: can Agent A<br/>access Vault X?"| OPA
```

| Function | Detail |
|---|---|
| **Task authorization** | Can this agent run this task with these capabilities? |
| **Communication scope** | Can Agent A send messages to Agent B? |
| **Secret access** | Can this agent access this 1Password vault? |
| **Delegation approval** | Can Agent A request external delegation with these capabilities? |
| **When disabled** | Orchestrator's built-in policy engine handles all decisions (less granular) |

### Cilium — Kernel / Network

eBPF-based networking. Operates at the kernel level — no sidecar overhead, no proxy in the path.

```mermaid
graph TD
    subgraph Container["Agent Container"]
        Agent[Agent Process]
        DNS[DNS Query]
        Egress[Outbound Request]
    end

    subgraph CiliumLayer["Cilium (eBPF in kernel)"]
        DNSPolicy[DNS Policy<br/>allowlist resolvers<br/>log all queries]
        EgressPolicy[Egress Policy<br/>allowlisted destinations only]
        IdentityPolicy[Identity Policy<br/>label-based network rules]
    end

    DNS -->|intercepted| DNSPolicy
    DNSPolicy -->|allowed| Resolver([DNS Resolver])
    DNSPolicy -.->|"blocked /<br/>exfil detected"| Drop([Drop + Alert])
    Egress -->|intercepted| EgressPolicy
    EgressPolicy -->|allowed| Destination([External API])
    EgressPolicy -.->|blocked| Drop2([Drop + Alert])

    style Drop stroke:#f00,stroke-width:2px
    style Drop2 stroke:#f00,stroke-width:2px
```

| Function | Detail |
|---|---|
| **DNS filtering** | Intercepts all DNS queries, enforces allowlisted resolvers, detects tunneling patterns |
| **Egress enforcement** | Kernel-level allowlist — not bypassable by container processes (unlike iptables) |
| **Identity-aware networking** | Network policies based on SPIFFE identity labels, not just IP addresses |
| **When disabled** | Standard container networking — Docker/K8s network policies only |

### Falco — Runtime Monitoring

Watches syscalls inside containers. Detects anomalies and triggers automated responses.

```mermaid
graph LR
    subgraph Container["Agent Container"]
        Agent[Agent Process]
        Syscalls[Syscalls<br/>open, exec, connect, etc.]
        Agent --> Syscalls
    end

    Falco[Falco<br/>syscall stream]
    Syscalls -->|observed| Falco

    subgraph Detection["Detection Rules"]
        Escape[Container escape<br/>attempt]
        SecretRead[Unexpected secret<br/>file access]
        NetAnomaly[Anomalous network<br/>connection]
        ProcAnomaly[Unexpected process<br/>spawned]
    end

    Falco --> Detection

    subgraph Response["Automated Response"]
        Alert[Alert → Observability]
        Revoke[Revoke SVID<br/>via SPIRE]
        Recycle[Recycle Container<br/>via Orchestrator]
    end

    Detection -->|low severity| Alert
    Detection -->|high severity| Revoke & Recycle
```

| Function | Detail |
|---|---|
| **Escape detection** | Watches for mount namespace changes, privilege escalation syscalls, /proc manipulation |
| **Secret access monitoring** | Detects unexpected reads of /proc/*/environ or sensitive file paths |
| **Process monitoring** | Flags unexpected child processes (e.g. agent spawning a shell) |
| **Automated response** | Falco alert → webhook → orchestrator revokes SVID + recycles container |
| **When disabled** | No runtime monitoring — rely on container isolation and lifecycle timeouts only |

#### Circuit Breaker

Falco's automated response can be weaponized — an attacker triggers rules intentionally to force-recycle legitimate containers (DoS). The circuit breaker prevents this.

```mermaid
graph TD
    FalcoAlert[Falco Alert]
    Counter["Per-Container<br/>Recycle Counter"]
    Check{"N recycles in<br/>time window?"}
    Recycle["Recycle Container<br/>+ Revoke SVID"]
    Halt["HALT: Stop Automated<br/>Response, Alert Operator"]

    FalcoAlert --> Counter --> Check
    Check -->|"under threshold"| Recycle
    Check -->|"threshold exceeded"| Halt

    style Halt stroke:#f90,stroke-width:2px
```

| Parameter | Value | Rationale |
|---|---|---|
| **Recycle threshold** | 3 recycles per container identity within 10 minutes | Prevents infinite recycle loops from weaponized alerts |
| **Scope** | Per-container identity (SVID) | One agent triggering alerts doesn't affect others |
| **On threshold breach** | Halt automated recycle, alert operator, keep container isolated (SVID revoked but not restarted) | Human judgment for sustained anomalies |
| **Falco's role** | Detection, not prevention | Prevention is seccomp, AppArmor, capabilities — Falco detects what slips through |

### Kyverno — Admission Control

Validates infrastructure configurations before they are applied. Prevents bad state from ever existing.

```mermaid
graph LR
    Orch((Orchestrator)) -->|"create container<br/>config"| Kyverno
    Kyverno -->|"validate against<br/>policies"| Policies[(Policy<br/>Rules)]
    Kyverno -->|"valid → admit"| Runtime[Container Runtime]
    Kyverno -.->|"invalid → reject"| Reject([Block + Log])

    style Reject stroke:#f00,stroke-width:2px
```

| Function | Detail |
|---|---|
| **Resource limits required** | Reject any container config missing CPU/memory/disk limits |
| **No host mounts** | Block any config that attempts to mount host filesystem |
| **Approved images only** | Reject configs referencing images not in the approved registry |
| **No privileged containers** | Block privileged mode, host networking, host PID namespace |
| **When disabled** | Orchestrator's built-in config validation only (less strict) |

---

## Environment Profiles

The mandatory baseline applies everywhere. Optional tools are flagged per environment.

```mermaid
graph LR
    subgraph All["All Environments (mandatory)"]
        direction LR
        M1[Container Hardening ●]
        M2[File-Based Secrets ●]
        M3[SPIRE Sidecar Isolation ●]
        M4[Orchestrator Policy ●]
    end
```

```mermaid
graph LR
    subgraph Local["Local Dev (optional)"]
        L1[Envoy ○]
        L2[OPA ○]
        L3[Cilium ○]
        L4[Falco ○]
        L5[Kyverno ○]
    end

    subgraph CI["CI / Automation (optional)"]
        C1[Envoy ●]
        C2[OPA ●]
        C3[Cilium ○]
        C4[Falco ○]
        C5[Kyverno ●]
    end

    subgraph Prod["Production / K8s (optional)"]
        P1[Envoy ●]
        P2[OPA ●]
        P3[Cilium ●]
        P4[Falco ●]
        P5[Kyverno ●]
    end
```

| Layer | Local Dev | CI / Automation | Production / K8s |
|---|---|---|---|
| **Container hardening** | **On** | **On** | **On** |
| **File-based secrets** | **On** | **On** | **On** |
| **SPIRE sidecar isolation** | **On** | **On** | **On** |
| **Orchestrator policy** | **On** | **On** | **On** |
| Envoy | Off | On | On |
| OPA | Off | On | On |
| Cilium | Off | Off | On |
| Kyverno | Off | On | On |
| Falco | Off | Off | On |

### Graceful Degradation

When an **optional** tool is disabled or crashes, the mandatory baseline still holds.

| Tool Disabled | What Still Protects You |
|---|---|
| **Envoy off** | Orchestrator validates identity and rate-limits. Container hardening prevents exploitation. |
| **OPA off** | Orchestrator's built-in policy engine handles authorization. Container caps limit blast radius. |
| **Cilium off** | Standard Docker/K8s network policies. Container has no CAP_NET_RAW, no shell tools for exfil. |
| **Falco off** | Container hardening (seccomp, capabilities, AppArmor) PREVENTS what Falco would detect. Lifecycle TTLs bound exposure. |
| **Kyverno off** | Orchestrator validates configs. Hardening is applied by the provisioner, not Kyverno. |

### Health Monitoring

Every optional tool must be health-checked. Undetected tool failure is a security gap.

| Requirement | Detail |
|---|---|
| **Health check** | Each tool exposes a health endpoint or is monitored via process supervision |
| **Failure alerting** | Tool crash or unreachability triggers immediate alert to operator |
| **Flag audit trail** | All feature flag changes are version-controlled and logged to audit trail |
| **Production immutability** | Production flags cannot be toggled without emergency procedure + audit entry |
| **Fail-closed option** | Configurable per tool: if Falco or Cilium crashes in production, halt new agent provisioning |

---

## Threat Coverage

Maps each tool to the threats it addresses from the [[arch-threat-model|Threat Model]].

| Threat | Envoy | OPA | Cilium | Falco | Kyverno |
|---|---|---|---|---|---|
| **Compromised LLM Agent** | Identity check | Action authorization | Egress enforcement | Anomaly detection | — |
| **Supply Chain Poisoning** | — | — | — | — | Image policy |
| **Secret Exfiltration** | — | Access scoping | Egress enforcement | Secret access monitoring | — |
| **Container Escape** | — | — | Kernel enforcement | Escape detection | No privileged containers |
| **External API Probe** | mTLS rejection | — | — | — | — |
| **Traffic Interception** | mTLS encryption | — | — | — | — |
| **DNS Exfiltration** | — | — | DNS filtering | — | — |
| **Orchestrator DoS** | Rate limiting | — | — | — | — |
| **Insider Acct Takeover** | — | Policy enforcement | — | — | — |
| **Log Injection** | — | — | — | Process monitoring | — |
