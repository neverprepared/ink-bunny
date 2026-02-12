# Agent Communication Layer

There is no separate message broker. The [[arch-orchestration|Orchestration Hub]] is the bus. All agent-to-agent communication routes through the orchestrator, which already owns identity, policy, and lifecycle management.

## Star Topology

```mermaid
graph TD
    subgraph Sandbox["Container Sandbox"]
        AgentA[Agent A]
        AgentB[Agent B]
        AgentN[Agent N]
    end

    Orch((Orchestration<br/>Hub))

    AgentA -->|result / event| Orch
    AgentB -->|result / event| Orch
    AgentN -->|result / event| Orch
    Orch -->|task / message| AgentA
    Orch -->|task / message| AgentB
    Orch -->|task / message| AgentN

    Observe[Observability]
    State[(Shared State)]

    Orch --> Observe
    Orch --> State
```

Agents never talk to each other directly. Every message passes through the orchestrator where it is validated, policy-checked, logged, and routed.

### Why star, not mesh

| Concern | Star (orchestrator is bus) | Mesh (dedicated broker) |
|---|---|---|
| **Infrastructure** | One component to deploy across all environments | Broker to deploy, secure, and maintain alongside orchestrator |
| **Security** | Single chokepoint — policy, identity, rate limiting in one place | Duplicate auth and policy enforcement on broker |
| **Observability** | Every message is already visible to the orchestrator | Broker needs its own instrumentation |
| **Failure mode** | Orchestrator down = all comms stop (acceptable for solo operator) | Broker can fail independently, partial outage scenarios |
| **Scale ceiling** | Bottleneck under high-frequency agent-to-agent streaming | Broker handles backpressure and persistence natively |

If a high-frequency streaming pattern emerges later, a broker can be introduced for that specific use case without rearchitecting the rest.

## Message Patterns

All patterns flow through the orchestrator.

```mermaid
graph LR
    subgraph Patterns["Communication Patterns"]
        direction TB
        RP["Request / Reply<br/>Agent → Orch → Agent → Orch → Agent"]
        Events["Events<br/>Agent → Orch → Subscribers"]
        Broadcast["Broadcast<br/>Agent → Orch → All Agents"]
    end
```

| Pattern | Flow | Use Case |
|---|---|---|
| **Request / Reply** | Agent A → Orch → Agent B → result → Orch → Agent A | "Agent B, process this data and return the result" |
| **Events** | Agent A → Orch → subscribed agents | Status updates, progress signals, completion notifications |
| **Broadcast** | Agent A → Orch → all active agents | "Dataset ready", "system shutting down" |

## Delegation Model

Two delegation paths based on scope. The [[arch-orchestration|Policy Engine]] enforces which path is required.

### Overview

```mermaid
graph TD
    AgentA[Agent A]

    subgraph Internal["Internal Delegation"]
        direction LR
        SubProc1[Sub-process 1]
        SubProc2[Sub-process 2]
    end

    Orch((Orchestration<br/>Hub))

    subgraph External["External Delegation"]
        direction LR
        SubAgentX[Sub-Agent X<br/>New Container]
        SubAgentY[Sub-Agent Y<br/>New Container]
    end

    AgentA -->|"lightweight<br/>same scope"| Internal
    AgentA -->|"heavyweight<br/>new scope needed"| Orch
    Orch -->|"provision + dispatch"| External
    External -->|"result"| Orch
    Orch -->|"result"| AgentA
```

### Internal Delegation (lightweight)

Agent handles sub-tasks within its own container. No orchestrator involvement.

```mermaid
graph LR
    Agent[Agent A<br/>LLM + tools] -->|fork / call| Sub1[Tool Call 1]
    Agent -->|fork / call| Sub2[Tool Call 2]
    Agent -->|fork / call| Sub3[Sub-process]
    Sub1 -->|result| Agent
    Sub2 -->|result| Agent
    Sub3 -->|result| Agent
```

| Property | Detail |
|---|---|
| **When to use** | Sub-tasks that need the same secrets, same capabilities, same identity |
| **Lifecycle** | Managed by the agent — orchestrator has no visibility |
| **Identity** | Inherits parent agent's token — no separate identity |
| **Examples** | LLM tool calls, data transformation steps, internal retries |
| **Risk** | No blast radius reduction — if the agent is compromised, all sub-tasks are too |

### External Delegation (heavyweight)

Agent requests the orchestrator to spawn a new container with its own identity.

```mermaid
sequenceDiagram
    participant A as Agent A
    participant O as Orchestrator
    participant P as Policy Engine
    participant S as Sub-Agent X

    A->>O: request sub-agent (task, required capabilities)
    O->>P: evaluate (can A delegate this? what scope?)
    P-->>O: approved (scoped identity + secrets)
    O->>S: provision container, inject identity + secrets
    S->>S: execute task
    S->>O: return result
    O->>A: forward result
    O->>S: recycle container
```

| Property | Detail |
|---|---|
| **When to use** | Sub-tasks that need different secrets, different capabilities, or different trust level |
| **Lifecycle** | Orchestrator provisions, monitors, and recycles the sub-agent container |
| **Identity** | Sub-agent gets its own scoped token — independent from parent |
| **Examples** | Calling an external API with different credentials, running untrusted code, accessing a different vault |
| **Risk** | Full blast radius reduction — sub-agent compromise doesn't compromise parent |

### Policy Decides the Path

```mermaid
graph TD
    Agent[Agent requests<br/>sub-task]
    Check{Policy Engine<br/>same scope?}
    Internal[Internal Delegation<br/>fork in container]
    External[External Delegation<br/>new container via orchestrator]

    Agent --> Check
    Check -->|"same secrets,<br/>same capabilities"| Internal
    Check -->|"new secrets,<br/>new capabilities,<br/>or untrusted workload"| External
```

| Trigger | Delegation Path |
|---|---|
| Sub-task needs the same secrets and capabilities as parent | Internal — stays in container |
| Sub-task needs access to a different 1Password vault | External — orchestrator provisions with scoped secrets |
| Sub-task runs untrusted or user-provided code | External — isolated container, minimal capabilities |
| Sub-task is an LLM tool call within the agent's existing scope | Internal — fast, no round-trip |
| Sub-task requires a different container image | External — orchestrator pulls and provisions |

## Communication Guardrails

All enforced at the orchestrator since it is the bus.

| Control | How |
|---|---|
| **Message Validation** | Orchestrator rejects malformed payloads before routing |
| **Rate Limiting** | Per-agent message quotas enforced at the orchestrator |
| **Scope Check** | Policy engine evaluates every cross-agent message — can A talk to B? |
| **Identity Verification** | Every message must carry a valid agent token issued by the orchestrator |
| **Audit** | Every message is logged with sender, receiver, timestamp, and payload hash |
