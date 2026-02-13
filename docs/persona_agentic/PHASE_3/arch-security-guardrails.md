# Security Guardrails

The core security boundary. Everything inside runs in containers — agents get **full filesystem autonomy within their container** but have zero access to the host.

```mermaid
graph TB
    Orch[Orchestration Layer]

    subgraph Guardrails["Security Guardrails"]

        subgraph AccessControl["Access Control"]
            AuthZ[Authorization]
            SecretsMgmt[Secrets Management]
            NetworkPolicy[Network Policies]
        end

        subgraph Sandbox["Container Sandbox"]
            ContainerMgmt[Container Management<br/>Docker / vcluster / kind]
            Lifecycle[Container Lifecycle]
            AgentRuntime[Agent Runtimes<br/>Full FS Access]

            ContainerMgmt --> Lifecycle --> AgentRuntime
        end

        subgraph Boundaries["Enforcement Boundaries"]
            ResourceLimits[Resource Limits<br/>CPU / Memory / Disk]
            EgressRules[Egress Rules<br/>Allowed Destinations]
            MountPolicy[Mount Policy<br/>No Host FS]
        end

        AccessControl --> Sandbox
        Boundaries -.->|enforced on| Sandbox
    end

    Comm[Agent Communication Layer]
    Observe[Observability Layer]

    Orch --> AccessControl
    AgentRuntime <--> Comm
    AgentRuntime --> Observe
```

## Access Control

| Control | Purpose |
|---|---|
| **Authorization** | Which agents can be spawned, what capabilities they receive |
| **Secrets Management** | Injected at runtime via 1Password + direnv — see [[arch-secrets-management]] |
| **Network Policies** | Restrict egress to approved destinations only |

## Network Zones

Platform components are segmented into three zones with default-deny between them.

```mermaid
graph TD
    subgraph AgentZone["Agent Sandbox Zone"]
        Agent1[Agent A]
        Agent2[Agent B]
        AgentN[Agent N]
    end

    subgraph ControlZone["Control Plane Zone"]
        Orch((Orchestrator))
        SPIRE[SPIRE Server]
        OPA[OPA]
    end

    subgraph DataZone["Data Plane Zone"]
        VectorDB[(Vector DB)]
        ArtifactStore[(Artifact Store)]
        Observability[Observability Stack]
    end

    Agent1 & Agent2 & AgentN -->|"allowed: orchestrator only"| Orch
    Orch --> SPIRE & OPA
    Orch --> VectorDB & ArtifactStore & Observability

    Agent1 -.->|"blocked"| Agent2
    Agent1 -.->|"blocked"| SPIRE
    Agent1 -.->|"blocked"| VectorDB

    style Agent1 fill:#fff
    style Agent2 fill:#fff
    style AgentN fill:#fff
```

| Zone | Contains | Inbound From | Outbound To |
|---|---|---|---|
| **Agent Sandbox** | All agent containers | Orchestrator (task dispatch, message routing) | Orchestrator only (+ allowlisted external APIs via egress rules) |
| **Control Plane** | Orchestrator, SPIRE Server, OPA | Agent zone (requests), Data zone (responses) | Data zone (store/query), Agent zone (dispatch) |
| **Data Plane** | Vector DB, Artifact Store, Observability | Control plane only (via shared state proxy) | Control plane (query responses) |

### Agent-to-Agent Isolation

Default-deny between all agent containers. Agents cannot communicate directly — all messages route through the orchestrator.

| Rule | Detail |
|---|---|
| **Default-deny NetworkPolicy** | All agent containers start with deny-all ingress and egress |
| **Egress allowlist** | Only orchestrator/Envoy port and explicitly approved external destinations |
| **No CAP_NET_RAW** | Dropped in mandatory hardening — prevents ARP spoofing on shared bridge networks |
| **No CAP_NET_ADMIN** | Dropped in mandatory hardening — prevents network configuration manipulation |
| **East-west monitoring** | Any inter-agent traffic that bypasses policy triggers immediate alert (Cilium or equivalent) |

### SPIRE Server Isolation

The SPIRE server is the identity root — it must be reachable only by the orchestrator and SPIRE agent sidecars.

| Rule | Detail |
|---|---|
| **Ingress** | Only from orchestrator (registration API) and SPIRE agent sidecars (attestation + SVID renewal) |
| **Egress** | Only to HSM/KMS (CA signing) and upstream SPIRE servers (if federated) |
| **Agent containers** | Cannot reach SPIRE server directly — interact only via local SPIRE agent sidecar over Unix socket |

## Enforcement Boundaries

| Boundary | Purpose |
|---|---|
| **Resource Limits** | CPU, memory, ephemeral storage caps per agent container |
| **Egress Rules** | Allowlisted outbound destinations only |
| **Mount Policy** | No host filesystem mounts, no Docker socket, no container runtime sockets |
| **Brainbox Hardening** | Mandatory in all environments — see [[arch-brainbox#Mandatory Brainbox Hardening]] |
| **Network Zones** | Three-zone segmentation with default-deny between zones |

### Brainbox Hardening (always on)

These controls are the security floor. They apply in every environment regardless of which [[arch-security-tooling|optional tools]] are enabled.

| Control | Mandatory Setting |
|---|---|
| seccomp | Custom restrictive profile |
| Capabilities | Drop ALL |
| Root filesystem | Read-only |
| User | Non-root (UID 65534) |
| Privilege escalation | Blocked |
| AppArmor | Custom deny profile |
| Secrets | File-based on tmpfs, not env vars |
| SPIRE sidecar | Separate container, shared Unix socket only |

## Container Management

| Tool | Use Case |
|---|---|
| **Docker** | Single-agent containers, lightweight tasks |
| **vcluster** | Virtual Kubernetes clusters for multi-agent workloads |
| **kind** | Local K8s clusters for development and testing |

See [[arch-brainbox]] for the full container lifecycle detail.
