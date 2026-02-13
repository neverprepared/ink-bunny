# Security Guardrails

**New in PHASE_2.** Breaks out from PHASE_1's [[arch-brainbox|Brainbox Lifecycle]] page into its own page, adding three-zone network segmentation, default-deny policies, and OPA-backed authorization.

The core security boundary. Everything inside runs in containers — agents get **full filesystem autonomy within their container** but have zero access to the host.

```mermaid
graph TB
    Orch[Orchestration Layer]

    subgraph Guardrails["Security Guardrails"]

        subgraph AccessControl["Access Control"]
            AuthZ[Authorization<br/>OPA + built-in]
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
            Hardening[Container Hardening<br/>Mandatory Baseline]
            NetworkZones[Network Zones<br/>3-Tier Segmentation]
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
| **Authorization** | OPA evaluates policy decisions, orchestrator built-in rules as fallback — see [[arch-security-tooling#OPA]] |
| **Secrets Management** | Envelope encryption, file-based delivery — see [[arch-secrets-management]] |
| **Network Policies** | Restrict egress to approved destinations, enforce zone boundaries |

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
```

| Zone | Contains | Inbound From | Outbound To |
|---|---|---|---|
| **Agent Sandbox** | All agent containers | Orchestrator (task dispatch, message routing) | Orchestrator only (+ allowlisted external APIs) |
| **Control Plane** | Orchestrator, SPIRE Server, OPA | Agent zone (requests), Data zone (responses) | Data zone (store/query), Agent zone (dispatch) |
| **Data Plane** | Vector DB, Artifact Store, Observability | Control plane only (via shared state proxy) | Control plane (query responses) |

### Agent-to-Agent Isolation

| Rule | Detail |
|---|---|
| **Default-deny NetworkPolicy** | All agent containers start with deny-all ingress and egress |
| **Egress allowlist** | Only orchestrator port and explicitly approved external destinations |
| **No CAP_NET_RAW** | Dropped in mandatory hardening — prevents ARP spoofing on shared bridge networks |
| **No CAP_NET_ADMIN** | Dropped in mandatory hardening — prevents network configuration manipulation |

## Enforcement Boundaries

| Boundary | Purpose |
|---|---|
| **Resource Limits** | CPU, memory, ephemeral storage caps per agent container |
| **Egress Rules** | Allowlisted outbound destinations only |
| **Mount Policy** | No host filesystem mounts, no Docker socket, no container runtime sockets |
| **Brainbox Hardening** | Full mandatory baseline — see [[arch-brainbox#Mandatory Brainbox Hardening]] |
| **Network Zones** | Three-zone segmentation with default-deny between zones |

### Mandatory Brainbox Hardening

| Control | Setting |
|---|---|
| seccomp | Custom restrictive profile |
| Capabilities | Drop ALL |
| Root filesystem | Read-only |
| User | Non-root (UID 65534) |
| Privilege escalation | Blocked |
| AppArmor | Custom deny profile |
| Secrets | File-based on tmpfs, not env vars |
| SPIRE sidecar | Separate container, shared Unix socket only |
| PID namespace | Not shared between containers |

## Container Management

| Tool | Use Case |
|---|---|
| **Docker** | Single-agent containers, lightweight tasks |
| **vcluster** | Virtual Kubernetes clusters for multi-agent workloads |
| **kind** | Local K8s clusters for development and testing |

See [[arch-brainbox]] for the full container lifecycle detail.
