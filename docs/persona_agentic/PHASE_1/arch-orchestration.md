# Orchestration Layer

The orchestration hub handles **task dispatch** and **message routing**. There is no separate message broker. Runs as a single process.

## Hub Overview

```mermaid
graph TD
    User([User / Operator])

    subgraph Orchestration["Orchestration Hub"]
        TaskRouter[Task Router]
        AgentRegistry[Agent Registry]
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
| **Agent Registry** | Catalog of available agents, their capabilities, and container images |
| **Policy Engine** | Built-in rules for task authorization and message routing |
| **Message Router** | Routes all inter-agent communication — request/reply and events |

## Star Topology

All inter-agent communication flows through the orchestrator. No direct agent-to-agent connections.

```mermaid
graph TD
    Orch((Orchestrator<br/>Message Router))

    Agent1[Agent A] <-->|"Docker-managed"| Orch
    Agent2[Agent B] <-->|"Docker-managed"| Orch
    Agent3[Agent N] <-->|"Docker-managed"| Orch

    Agent1 -.->|"no direct path"| Agent2
```

Every message passes through the orchestrator, which checks policy, logs the exchange, and routes to the recipient. Identity is implicit — containers are identified by Docker labels, not authenticated tokens.

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
    Container <-->|"single container"| Orch
```

| Property | Detail |
|---|---|
| **Scope** | Same container, same resource limits |
| **Orchestrator visibility** | None — internal sub-processes are opaque |
| **Secret access** | Shared — sub-processes inherit the parent's `/run/secrets/` mount |

> External delegation (orchestrator provisions a new container for a sub-task) is introduced in PHASE_2.

## Communication Guardrails

Enforced at the orchestrator on every message.

| Guardrail | How |
|---|---|
| **Container identity** | Messages are attributed by Docker container labels — no authenticated tokens in Phase 1 |
| **Policy check** | Built-in rules evaluate whether this agent can send to that target |
| **Schema validation** | Message payload must conform to the expected schema |
| **Logging** | Every routed message is logged to [[arch-observability|Observability]] |
