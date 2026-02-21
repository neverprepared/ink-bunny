# Brainbox Orchestration Architecture

This document describes the current orchestration flow from host to container, including query execution, event streaming, and monitoring.

## System Overview

```mermaid
graph TB
    subgraph "Host Machine"
        Orchestrator[Claude Code<br/>Orchestrator]
        API[Brainbox API<br/>FastAPI :9999]
        Docker[Docker Engine]
        Dashboard[Web Dashboard<br/>Browser]
    end

    subgraph "Docker Container"
        Tmux[tmux session 'main']
        Claude[Claude Code CLI]
        FS[/home/developer/workspace<br/>Volume Mount]
    end

    Orchestrator -->|HTTP POST<br/>/api/sessions/*/query| API
    API -->|Docker API calls| Docker
    Docker -->|exec into container| Tmux
    Tmux -->|keystrokes via IPC| Claude

    API -.->|SSE events| Dashboard
    Docker -.->|health checks| API

    FS <-.->|bidirectional<br/>file sync| HostFS[Host Source Code]

    Claude -->|reads/writes| FS

    style Orchestrator fill:#e1f5ff
    style API fill:#fff4e1
    style Docker fill:#f0f0f0
    style Claude fill:#e1ffe1
    style Dashboard fill:#ffe1f5
```

## Query Execution Flow

```mermaid
sequenceDiagram
    participant O as Orchestrator<br/>(Host Claude)
    participant A as Brainbox API<br/>(FastAPI)
    participant D as Docker Engine
    participant T as tmux (main)
    participant C as Claude Code<br/>(Container)

    Note over O: User: "optimize the code"
    O->>+A: POST /api/sessions/opt-review/query<br/>{"prompt": "Implement opt #1", "timeout": 180}

    A->>A: Rate limit check (5/min)
    A->>A: Audit log: session.query

    A->>+D: containers.get("developer-opt-review")
    D-->>-A: container object

    A->>+D: container.exec_run(["tmux", "send-keys", ...])
    D->>+T: tmux send-keys -t main "prompt" Enter
    T->>C: inject keystrokes
    D-->>-A: exec started

    Note over C: Permission auto-approved<br/>(--dangerously-skip-permissions)

    C->>C: Parse prompt
    C->>C: Execute tools<br/>(Read, Edit, Bash)

    loop Polling (every 0.5s, max 300s)
        A->>+D: exec_run("tmux capture-pane -pt main")
        D->>T: capture pane output
        T-->>D: current output
        D-->>-A: pane contents

        alt Output contains "● Done" + stable
            Note over A: Completion detected!
        else Still working
            A->>A: Wait 0.5s, poll again
        end
    end

    C->>C: Output: "● Done"
    C->>T: Return to prompt: "❯"

    A->>+D: capture-pane (final)
    D->>T: get full output
    T-->>D: complete transcript
    D-->>-A: output text

    A->>A: Clean ANSI codes
    A->>A: Extract metadata
    A->>A: Audit log: success

    A-->>-O: {"success": true,<br/>"output": "...",<br/>"duration_seconds": 90.41}

    Note over O: Process result<br/>Send next query...
```

## Container Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Creating: POST /api/create

    Creating --> Provisioning: Docker pull/build
    Provisioning --> Configuring: Inject secrets
    Configuring --> Starting: Start container
    Starting --> Monitoring: Health checks begin

    Monitoring --> Ready: tmux session active
    Ready --> Processing: Receive query
    Processing --> Ready: Query complete

    Ready --> Stopped: POST /api/stop
    Stopped --> [*]: Container exited

    Ready --> Recycled: POST /api/delete
    Recycled --> [*]: Container removed

    Processing --> Failed: Timeout/Error
    Failed --> Ready: Recoverable
    Failed --> Recycled: Unrecoverable

    note right of Monitoring
        Health check every 30s:
        - CPU %
        - Memory usage
        - Uptime
        - Container status
    end note

    note right of Processing
        Query execution:
        - Inject prompt via tmux
        - Poll for completion
        - Return result
    end note
```

## Event Streams (SSE)

```mermaid
graph LR
    subgraph "Brainbox API (FastAPI)"
        Events[Event Generator]
        Queue[SSE Queue<br/>maxsize=50]
    end

    subgraph "Event Sources"
        Docker[Docker Events]
        Health[Health Checks]
        Query[Query Lifecycle]
        Hub[Hub State Changes]
    end

    subgraph "Subscribers"
        Dashboard[Web Dashboard]
        Monitor[External Monitors]
    end

    Docker -->|container.started<br/>container.stopped| Events
    Health -->|container.health_check| Events
    Query -->|session.query<br/>session.exec| Events
    Hub -->|hub.initialized<br/>agent.loaded| Events

    Events --> Queue

    Queue -.->|SSE stream<br/>GET /api/events| Dashboard
    Queue -.->|SSE stream| Monitor

    style Queue fill:#ffe1e1
    style Events fill:#e1ffe1
```

## File System Synchronization

```mermaid
graph TB
    subgraph "Host"
        HostFS[/Users/.../code/ink-bunny]
        API[Brainbox API]
    end

    subgraph "Container"
        ContainerFS[/home/developer/workspace]
        Claude[Claude Code]
    end

    HostFS <-->|Docker Volume Mount<br/>Bidirectional Sync| ContainerFS

    Claude -->|Read files| ContainerFS
    Claude -->|Write/Edit files| ContainerFS

    ContainerFS -.->|Changes appear<br/>immediately| HostFS

    API -->|Git operations| HostFS

    Note1[Example: Optimizations written<br/>by container Claude appear<br/>on host for git commit]

    style HostFS fill:#e1f5ff
    style ContainerFS fill:#e1ffe1
```

## Current Limitations & Future Improvements

```mermaid
mindmap
    root((Current<br/>Orchestration))
        Synchronous Execution
            Blocking queries
            No parallelism
            Sequential only
        Polling-based Detection
            500ms polling interval
            CPU overhead
            Latency in detection
        No Task Queue
            Manual coordination
            No priority
            No dependencies
        Single Orchestrator
            No HA
            No load balancing
            Manual multi-tab

        Future: NATS Integration
            Async task submission
                Fire-and-forget
                Non-blocking
            Event-driven completion
                No polling
                Real-time
            Task queue
                JetStream persistence
                Queue groups
                Load balancing
            Multi-orchestrator
                HA support
                Shared state
                Distributed work
```

## NATS Migration Path

```mermaid
graph LR
    subgraph "Current (HTTP + SSE)"
        O1[Orchestrator]
        A1[API]
        C1[Container]

        O1 -->|POST query<br/>BLOCKING| A1
        A1 -->|docker exec<br/>POLLING| C1
        A1 -.->|SSE events| O1
    end

    subgraph "Future (NATS + SSE)"
        O2[Orchestrator]
        N[NATS<br/>Server]
        A2[API<br/>Bridge]
        C2[Container<br/>Agent]
        D2[Dashboard]

        O2 -->|pub tasks.*<br/>ASYNC| N
        N -->|sub tasks.*| C2
        C2 -->|pub results.*| N
        N -->|sub results.*| O2

        N -->|pub events.*| A2
        A2 -.->|SSE forward| D2
    end

    Current -.->|Phase 1| Future

    style Current fill:#ffe1e1
    style Future fill:#e1ffe1
```

## Query API Details

### Request Format

```json
{
  "prompt": "Implement optimization #1",
  "working_dir": "/home/developer/workspace/brainbox",
  "timeout": 180,
  "fork_session": false
}
```

### Response Format

```json
{
  "success": true,
  "conversation_id": "optimization-review-1771168506",
  "output": "...Claude's full output...",
  "error": null,
  "exit_code": 0,
  "duration_seconds": 90.41,
  "files_modified": []
}
```

### Completion Detection Logic

```mermaid
flowchart TD
    Start[Poll tmux output] --> Capture[Capture pane]
    Capture --> Check1{Contains<br/>'● Done'?}

    Check1 -->|No| Wait[Wait 0.5s]
    Wait --> Timeout{Exceeded<br/>timeout?}
    Timeout -->|Yes| Return[Return partial<br/>+ timeout error]
    Timeout -->|No| Capture

    Check1 -->|Yes| Check2{Output<br/>stable 2+<br/>iterations?}
    Check2 -->|No| Wait
    Check2 -->|Yes| Check3{Prompt<br/>'❯' visible?}
    Check3 -->|No| Wait
    Check3 -->|Yes| Complete[Extract output<br/>Clean ANSI<br/>Return result]

    Return --> End([End])
    Complete --> End
```

## Performance Characteristics

| Metric | Current Value | Notes |
|--------|--------------|-------|
| Query Latency | ~500ms base + execution time | Docker exec + tmux overhead |
| Polling Interval | 500ms | Configurable, impacts CPU usage |
| Max Timeout | 300s (5 min) | Configurable per query |
| Rate Limit | 5 queries/min per session | Prevents abuse |
| SSE Event Delay | ~100ms | Near real-time |
| Health Check Interval | 30s | Container metrics |
| Max SSE Queue Size | 50 events | Drops old events if full |

## Security Model

```mermaid
graph TB
    subgraph "Trust Boundary"
        API[Brainbox API]
        Docker[Docker Engine]
    end

    subgraph "Container Sandbox"
        Claude[Claude Code]
        FS[Workspace]
    end

    API -->|Authenticated| Docker
    Docker -->|Isolated| Claude

    API -->|Rate Limited| Query[Query Endpoint]
    API -->|Audit Logged| Ops[All Operations]

    Claude -->|Skip Permissions<br/>FLAG ENABLED| Tools[File/Bash Tools]

    FS -->|Volume Mount<br/>READ/WRITE| Host[Host Filesystem]

    Note1[Security Assumptions:<br/>1. Container isolation via Docker<br/>2. No network access from containers<br/>3. Workspace volume is trusted<br/>4. Permission bypass for automation]

    style Claude fill:#ffe1e1
    style Host fill:#ffe1e1
```

## Next Steps

### Immediate Improvements (No NATS)
- [ ] Add `async=true` flag to query API
- [ ] Return task_id immediately for async queries
- [ ] Add `/api/sessions/{name}/tasks/{task_id}` status endpoint
- [ ] Emit SSE events: `query.{task_id}.started/completed`

### Phase 1: NATS Integration
- [ ] Add NATS server (embedded or sidecar)
- [ ] Implement NATS bridge in API
- [ ] Add container agent for NATS subscriptions
- [ ] Forward NATS events → SSE for dashboard

### Phase 2: Task Queue
- [ ] JetStream for persistent task queue
- [ ] Task dependencies (blockedBy/blocks)
- [ ] Priority scheduling
- [ ] Result aggregation

### Phase 3: Multi-Container Coordination
- [ ] Queue groups for load balancing
- [ ] Dynamic container scaling
- [ ] Workflow DAG execution
- [ ] High availability orchestrator

---

**Last Updated**: 2026-02-15
**Current Version**: Single orchestrator, synchronous queries, SSE events
**Next Milestone**: Async query API + task tracking
