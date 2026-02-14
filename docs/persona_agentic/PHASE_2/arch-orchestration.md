# Orchestration Layer

The orchestration hub serves two roles: **task dispatch** (routing work to agents) and **communication bus** (routing all agent-to-agent messages). There is no separate message broker.

## Hub Overview

```mermaid
graph TD
    User([User / Operator])

    subgraph Orchestration["Orchestration Hub"]
        TaskRouter[Task Router]
        AgentRegistry[Agent Registry]
        PolicyEngine[Policy Engine]
        MessageRouter[Message Router]

        TaskRouter -->|lookup| AgentRegistry
        TaskRouter -->|evaluate| PolicyEngine
        MessageRouter -->|evaluate| PolicyEngine
    end

    Guard[Security Guardrails]
    Observe[Observability]

    User -->|submit task| TaskRouter
    PolicyEngine -->|approve / deny| Guard
    AgentRegistry -->|resolve agent image| Guard
    MessageRouter --> Observe
```

## Components

| Component | Responsibility |
|---|---|
| **Task Router** | Receives work requests from users, resolves which agent handles them |
| **Agent Registry** | Catalog of available agents, their capabilities, and container images |
| **Policy Engine** | Evaluates authorization for both task dispatch and agent-to-agent messages. Delegates to [[arch-security-tooling#OPA|OPA]] when enabled. |
| **Message Router** | Routes all inter-agent communication — request/reply, events, broadcasts |

## Task Dispatch Flow

1. User submits a task
2. Task Router queries the Agent Registry for a capable agent
3. Policy Engine evaluates authorization (can this agent run? with what capabilities?)
4. On approval, the task is dispatched into the [[arch-security-guardrails|Security Guardrails]] layer

## Message Routing Flow

1. Agent sends a message (result, event, delegation request) to the orchestrator
2. Message Router validates the payload schema
3. Policy Engine checks scope (can this agent send this message to that target?)
4. Agent identity token (SVID) is verified
5. Message is logged to [[arch-observability|Observability]] and routed to the recipient

See [[arch-agent-communication]] for the full communication model, delegation patterns, and guardrails.

## State Persistence

The orchestrator persists critical state to survive restarts.

```mermaid
graph LR
    Orch((Orchestrator))
    Store[(Durable Store<br/>SQLite / embedded KV)]

    Orch -->|"persist"| Store
    Store -->|"recover on restart"| Orch

    subgraph Persisted["What's Persisted"]
        Registry["Agent Registry<br/>(images, capabilities)"]
        InFlight["In-Flight Tasks<br/>(state, assignment, timeout)"]
        PolicyConfig["Policy Configuration"]
    end

    Store --- Persisted
```

| Data | Persisted | Recovery |
|---|---|---|
| **Agent registry** | Yes | Rebuilt from config + registry on restart |
| **In-flight tasks** | Yes | Resumed or safely timed out on restart |
| **Policy config** | Yes | Loaded from version-controlled source on restart |
| **Message queue** | No | In-flight messages lost — agents retry via standard timeout |

## Degraded Mode

When the orchestrator detects internal failures, it enters a degraded read-only mode rather than crashing.

| Mode | Behavior |
|---|---|
| **Normal** | Full task dispatch, message routing, policy evaluation |
| **Degraded (read-only)** | No new task dispatch, no new container provisioning. Existing containers continue running. Message routing and health checks continue. Alerts operator. |
| **Offline** | Orchestrator unreachable. Existing containers continue until TTL. No new work. |

## Agent Daemon

Each container runs a lightweight agent daemon that connects it to the orchestrator's task and message infrastructure. Without the daemon, containers are interactive-only — an operator must manually drive work through the terminal. The daemon enables programmatic task execution.

```mermaid
graph TD
    subgraph Container["Agent Container"]
        Daemon[Agent Daemon<br/>poll / execute / report]
        Claude[Claude Code CLI<br/>--model flag]
        Daemon -->|"invoke"| Claude
    end

    Orch((Orchestrator<br/>Hub API))
    Daemon <-->|"poll tasks / post results"| Orch
```

### Daemon Responsibilities

| Responsibility | Detail |
|---|---|
| **Task polling** | Poll `/api/hub/messages` for assigned work using the container's token |
| **Task execution** | Invoke Claude Code CLI with the task prompt, capture output |
| **Result reporting** | Post results back to the hub via `/api/hub/messages` with `task.completed` event |
| **Health signaling** | Emit heartbeat events so the orchestrator knows the daemon is alive |
| **Graceful shutdown** | On SIGTERM, finish current task, report partial results, exit cleanly |

### LLM Provider Routing

The daemon inherits the container's LLM configuration. The orchestrator decides which LLM backend a container uses at provision time, not at task time.

```mermaid
graph LR
    Orch((Orchestrator))

    subgraph Private["Private LLM Containers"]
        A1[Agent A<br/>ollama / qwen3]
        A2[Agent B<br/>ollama / qwen3]
    end

    subgraph Public["Public LLM Containers"]
        A3[Agent C<br/>claude / opus]
    end

    Orch -->|"sensitive task"| A1
    Orch -->|"sensitive task"| A2
    Orch -->|"complex reasoning"| A3

    Ollama[(Ollama<br/>host / GPU box)]
    Anthropic[(Anthropic API)]

    A1 & A2 -->|"local network"| Ollama
    A3 -->|"internet"| Anthropic
```

| Routing Scenario | Provider | Rationale |
|---|---|---|
| **Sensitive code / proprietary data** | Ollama (private) | Data stays on the local network |
| **Complex reasoning / large context** | Claude (public) | Stronger model capabilities |
| **Mixed workload** | Both | Orchestrator routes by task sensitivity label |
| **Cost optimization** | Ollama (private) | No per-token API costs for bulk work |

### Practical Use Cases

| Use Case | How It Works |
|---|---|
| **Isolation boundaries** | Different containers get different secrets, network policies, and roles — a researcher container can't write to production, a performer can |
| **Persistent long-running work** | An agent works on a codebase for hours with full state (git history, installed deps) — subagents are ephemeral, containers persist |
| **Mixed LLM backends** | Sensitive repo in a private Ollama container, complex analysis on Claude API — orchestrator routes by sensitivity |
| **Role-specific tooling** | Developer has full git, performer has cloud CLIs, researcher has Qdrant — each container is purpose-built |

## Basic Monitoring

| Check | Action on Failure |
|---|---|
| **Orchestrator health endpoint** | If unreachable, alert operator |
| **Task throughput** | If zero tasks dispatched for configurable window, alert operator |
| **Container orphan scan** | If containers exist with no matching orchestrator task record, alert + recycle |
