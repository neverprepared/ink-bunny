# Orchestration Layer

The orchestration hub handles **task dispatch**, **agent identity**, and **message routing**. There is no separate message broker or identity provider. Runs as a single process.

## Hub Overview

```mermaid
graph TD
    User([User / Operator])

    subgraph Orchestration["Orchestration Hub"]
        TaskRouter[Task Router]
        AgentRegistry[Agent Registry<br/>+ Token Issuer]
        PolicyEngine[Policy Engine<br/>built-in rules]
        MessageRouter[Message Router]

        TaskRouter -->|lookup| AgentRegistry
        TaskRouter -->|evaluate| PolicyEngine
        MessageRouter -->|evaluate| PolicyEngine
    end

    Observe[Observability]

    User -->|submit task| TaskRouter
    AgentRegistry -->|provision container| Container[Container Lifecycle]
    MessageRouter --> Observe
```

## Components

| Component | Responsibility |
|---|---|
| **Task Router** | Receives work requests from users, resolves which agent handles them |
| **Agent Registry** | Catalog of available agents, their capabilities, and container images. Issues container tokens on provisioning. |
| **Policy Engine** | Built-in rules for task authorization and message routing |
| **Message Router** | Routes all inter-agent communication — request/reply and events |

## Container Tokens

The orchestrator is the identity provider. When it spawns a container, it issues a unique token that the agent uses for all communication.

```mermaid
sequenceDiagram
    participant User as User
    participant Orch as Orchestrator
    participant Container as Agent Container

    User->>Orch: submit task
    Orch->>Orch: generate container token (agent name, task ID, capabilities, expiry)
    Orch->>Container: provision container, inject token via /run/secrets/agent-token
    Container->>Orch: all requests carry container token
    Orch->>Orch: validate token against registry
    Orch-->>Container: accept / reject
```

| Field | Purpose |
|---|---|
| **Token ID** | Unique identifier for this container instance |
| **Agent name** | Which agent image this container is running |
| **Task ID** | Which specific task this container was spawned for |
| **Capabilities** | What this agent is allowed to do |
| **Expiry** | Matches container TTL — token dies with the container |

The orchestrator validates every request by checking the token against its own registry. No external identity infrastructure needed.

> SPIFFE/SPIRE replaces this in PHASE_2 for workload attestation and mTLS.

## Star Topology

All inter-agent communication flows through the orchestrator. No direct agent-to-agent connections.

```mermaid
graph TD
    Orch((Orchestrator<br/>Message Router))

    Agent1[Agent A] <-->|"token-authenticated"| Orch
    Agent2[Agent B] <-->|"token-authenticated"| Orch
    Agent3[Agent N] <-->|"token-authenticated"| Orch

    Agent1 -.->|"no direct path"| Agent2
```

Every message passes through the orchestrator, which validates the token, checks policy, logs the exchange, and routes to the recipient.

## Message Patterns

| Pattern | Description | Example |
|---|---|---|
| **Request / Reply** | Agent sends request, orchestrator routes it, recipient replies | Agent A requests data from Agent B |
| **Event** | Agent emits an event, orchestrator routes to subscribers | Agent A completed a task, notify interested agents |

## Internal Delegation

Delegation is **internal only** — an agent can fork sub-processes within its own container. The orchestrator has no visibility.

```mermaid
graph TD
    subgraph Container["Agent A Container"]
        Parent[Parent Process]
        Child1[Sub-Process 1]
        Child2[Sub-Process 2]

        Parent -->|fork| Child1
        Parent -->|fork| Child2
    end

    Orch((Orchestrator))
    Container <-->|"single token"| Orch
```

| Property | Detail |
|---|---|
| **Scope** | Same container, same token, same resource limits |
| **Orchestrator visibility** | None — internal sub-processes are opaque |
| **Secret access** | Shared — sub-processes inherit the parent's `/run/secrets/` mount |

> External delegation (orchestrator provisions a new container for a sub-task) is introduced in PHASE_2.

## Communication Guardrails

Enforced at the orchestrator on every message.

| Guardrail | How |
|---|---|
| **Token required** | Every message must carry a valid container token — unauthenticated messages rejected |
| **Policy check** | Built-in rules evaluate whether this agent can send to that target |
| **Schema validation** | Message payload must conform to the expected schema |
| **Logging** | Every routed message is logged to [[arch-observability|Observability]] |
