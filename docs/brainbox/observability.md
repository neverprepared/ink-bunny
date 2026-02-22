# Monitoring, Metrics & Infrastructure

Brainbox integrates several infrastructure services for observability, artifact storage, and inter-container messaging. This document covers the health monitoring loop, container metrics collection, LangFuse trace integration, MinIO artifact storage, secret resolution, NATS messaging, and SSE event broadcasting.

## Infrastructure Service Map

```mermaid
graph TB
    subgraph Brainbox["Brainbox API (:9999)"]
        API[FastAPI]
        SSE[SSE Broadcaster]
        Monitor[Health Monitor]
    end

    subgraph Services["Infrastructure Services"]
        LF[LangFuse<br/>:3000<br/>HTTP Basic Auth]
        QD[Qdrant<br/>:6333<br/>API Key optional]
        MN[MinIO<br/>:9090<br/>Access Key + Secret]
        NATS[NATS<br/>:4222<br/>No auth]
        Docker[Docker Engine<br/>unix socket]
    end

    subgraph Containers["Managed Sessions"]
        C1[developer-default<br/>:7681]
        C2[researcher-analysis<br/>:7682]
    end

    API -->|traces, observations| LF
    API -->|health check| QD
    API -->|upload, download| MN
    API -->|pub/sub commands| NATS
    API -->|SDK calls| Docker
    Monitor -->|health_check| Docker
    SSE -->|events| Docker
    NATS -->|commands| C1 & C2
    C1 & C2 -->|results| NATS

    classDef bbStyle fill:#f97316,stroke:#ea580c,color:#fff
    classDef svcStyle fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef ctrStyle fill:#22c55e,stroke:#16a34a,color:#fff

    class API,SSE,Monitor bbStyle
    class LF,QD,MN,NATS,Docker svcStyle
    class C1,C2 ctrStyle
```

| Service | Default Port | Protocol | Auth | Config Prefix |
|---------|-------------|----------|------|--------------|
| Brainbox API | 9999 | HTTP | None | `CL_API_PORT` |
| LangFuse | 3000 | HTTP | Basic (public_key:secret_key) | `CL_LANGFUSE__*` |
| Qdrant | 6333 | HTTP | API key (optional) | `CL_QDRANT__*` |
| MinIO | 9090 | HTTP (S3) | Access key + secret | `CL_ARTIFACT__*` |
| NATS | 4222 | NATS protocol | None | `CL_NATS__*` |
| Docker | unix socket | Docker API | — | — |

## Health Monitor Loop

The monitor (`monitor.py`) runs a background async loop that checks each tracked session at a configurable interval.

```mermaid
flowchart TB
    Start([start_monitoring]) --> Register[Add session<br/>to _tracked]
    Register --> Loop{_tracked<br/>not empty?}
    Loop -->|yes| ForEach[For each session]
    ForEach --> HealthCheck[backend.health_check]
    HealthCheck --> Healthy{healthy?}

    Healthy -->|yes| ResetFail[Reset health_failures]
    Healthy -->|no| IncrFail[Increment<br/>health_failures]
    IncrFail --> CheckFail{failures >= 3?}
    CheckFail -->|yes| Recycle[Mark RECYCLING]

    ResetFail --> CheckTTL{TTL expired?}
    CheckFail -->|no| CheckTTL
    CheckTTL -->|yes| Recycle
    CheckTTL -->|no| LogMetrics[Log CPU, memory]

    Recycle --> Remove[Remove from<br/>_tracked]
    LogMetrics --> Sleep[Sleep interval]
    Sleep --> Loop

    Loop -->|no| End([Loop exits])

    classDef okStyle fill:#22c55e,stroke:#16a34a,color:#fff
    classDef warnStyle fill:#f59e0b,stroke:#d97706,color:#fff
    classDef errStyle fill:#ef4444,stroke:#dc2626,color:#fff

    class ResetFail,LogMetrics okStyle
    class IncrFail,CheckFail warnStyle
    class Recycle,Remove errStyle
```

| Setting | Default | Description |
|---------|---------|-------------|
| `health_check_interval` | 30s | Polling interval |
| `health_check_timeout` | 5s | Per-check timeout |
| `health_check_retries` | 3 | Failures before recycling |
| `ttl` | 3600s | Session time-to-live |

**Backend-specific metrics logged:**

| Backend | Metrics |
|---------|---------|
| Docker | CPU %, memory usage/limit (human-readable) |
| UTM | VM state, SSH reachability, SSH port |

## Artifact Lifecycle

Artifacts are stored in MinIO (S3-compatible) and accessed via the `/api/artifacts` endpoints.

```mermaid
sequenceDiagram
    participant Client
    participant API as api.py
    participant Art as artifacts.py
    participant MinIO as MinIO (S3)

    Note over Art: On first call
    Art->>MinIO: HEAD bucket
    alt bucket missing
        Art->>MinIO: CREATE bucket
    end

    Client->>API: POST /api/artifacts/results/task-123.json
    API->>Art: upload_artifact(key, data, metadata)
    Art->>MinIO: PutObject(bucket, key, data)
    MinIO-->>Art: ETag
    Art-->>API: ArtifactResult{key, size, etag}
    API-->>Client: 201 {stored: true, key, size, etag}

    Client->>API: GET /api/artifacts/results/task-123.json
    API->>Art: download_artifact(key)
    Art->>MinIO: GetObject(bucket, key)
    MinIO-->>Art: body + metadata
    Art-->>API: (bytes, metadata)
    API-->>Client: 200 body (content-type from metadata)
```

**Artifact modes** (`CL_ARTIFACT__MODE`):

| Mode | Behavior on Error |
|------|-------------------|
| `off` | All artifact endpoints return 503 |
| `warn` | Log warning, return null/empty (soft fail) |
| `enforce` | Return 502 (hard fail) |

**Configuration:**

| Setting | Default | Description |
|---------|---------|-------------|
| `artifact.endpoint` | `http://localhost:9090` | MinIO endpoint |
| `artifact.bucket` | `artifacts` | S3 bucket name |
| `artifact.access_key` | — | MinIO access key |
| `artifact.secret_key` | — | MinIO secret key |
| `artifact.region` | `us-east-1` | S3 region |

## Secret Resolution

Secrets are resolved during the configure phase and injected into containers. Two strategies are tried in order.

```mermaid
flowchart TD
    Start([resolve_secrets]) --> CheckOP{1Password SA token<br/>available?}

    CheckOP -->|yes| OPResolve[resolve_from_op]
    CheckOP -->|no| FileResolve[resolve_from_files]

    OPResolve --> ListItems[op item list --vault VAULT]
    ListItems --> ForEach[For each item]
    ForEach --> GetFields[op item get --fields]
    GetFields --> DeriveEnv[Derive env var name<br/>item-title + field-label<br/>→ ITEM_TITLE_FIELD_LABEL]
    DeriveEnv --> FilterSkip{Skip notes,<br/>OTP fields}
    FilterSkip -->|skip| ForEach
    FilterSkip -->|keep| AddToDict[Add to secrets dict]
    AddToDict --> ForEach
    ForEach --> Done1([Return secrets])

    FileResolve --> ReadDir[Read secrets_dir<br/>~/.config/developer/.secrets/]
    ReadDir --> ForFile[For each file]
    ForFile --> ReadFile[filename → value]
    ReadFile --> ForFile
    ForFile --> Done2([Return secrets])

    classDef opStyle fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef fileStyle fill:#f97316,stroke:#ea580c,color:#fff

    class OPResolve,ListItems,ForEach,GetFields,DeriveEnv,AddToDict opStyle
    class FileResolve,ReadDir,ForFile,ReadFile fileStyle
```

**1Password strategy (preferred):**
- Uses `OP_SERVICE_ACCOUNT_TOKEN` env var or `op_sa_token_file`
- Scoped to vault (`CL_OP_VAULT` if set)
- Env var naming: `item-title` + `field-label` → `ITEM_TITLE_FIELD_LABEL` (hyphens → underscores, uppercase)
- Skips: `notesPlain` field IDs, `OTP` field types

**Plaintext files (fallback):**
- Reads all files in `~/.config/developer/.secrets/`
- Filename becomes the key, file content becomes the value

**Injection targets:**

| Mode | Location | Permissions |
|------|----------|------------|
| Hardened | `/run/secrets/{name}` (tmpfs) | 0400 (read-only) |
| Legacy | `~/.env` (file) | 0077 umask |

## SSE Event Pipeline

SSE events flow from Docker and Hub sources through a broadcast mechanism to connected clients.

```mermaid
graph TB
    subgraph Sources["Event Sources"]
        DE[Docker Engine<br/>container events]
        Hub[Hub Router<br/>task events]
        NATS_S[NATS<br/>container messages]
    end

    subgraph Broadcast["SSE Broadcast"]
        Filter[Filter<br/>brainbox.managed]
        Serialize[JSON serialize]
        BC[_broadcast_sse]
    end

    subgraph Clients["SSE Clients"]
        Q1[Queue 1<br/>Dashboard]
        Q2[Queue 2<br/>MCP client]
        Q3[Queue N<br/>...]
    end

    DE -->|"create,start,stop,die,destroy"| Filter --> BC
    Hub -->|"task.started, task.completed, ..."| Serialize --> BC
    NATS_S -->|"progress, result, error"| Serialize --> BC

    BC --> Q1 & Q2 & Q3
    Q1 --> EP[GET /api/events]
    Q2 --> EP
    Q3 --> EP

    classDef srcStyle fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef bcStyle fill:#f97316,stroke:#ea580c,color:#fff
    classDef clientStyle fill:#22c55e,stroke:#16a34a,color:#fff

    class DE,Hub,NATS_S srcStyle
    class Filter,Serialize,BC bcStyle
    class Q1,Q2,Q3 clientStyle
```

**Implementation details:**
- `_sse_queues: set[asyncio.Queue]` — each connected client gets a bounded queue (maxsize=50)
- `_broadcast_sse(data)` — puts data into all queues (drops on `QueueFull`)
- Docker events run in a background thread via `run_in_executor`, reconnecting after a 1s delay on stream death
- Hub events are forwarded via `on_event()` callback registered during lifespan
- NATS events (questions, progress, results, errors, cancellations) are forwarded from subscription handlers

## LangFuse Integration

The LangFuse client (`langfuse_client.py`) queries traces and observations via the LangFuse public API using HTTP Basic Auth.

| Function | API Call | Returns |
|----------|---------|---------|
| `health_check()` | `GET /api/public/health` | `bool` |
| `list_traces(session_id, limit)` | `GET /api/public/traces?sessionId=...` | `list[TraceResult]` |
| `get_trace(trace_id)` | `GET /api/public/traces/{id}` + `GET /api/public/observations` | `(TraceResult, list[ObservationResult])` |
| `get_session_traces_summary(session_id)` | `GET traces` + `GET observations` (batch) | `SessionSummary` |

**SessionSummary** aggregates: `total_traces`, `total_observations`, `error_count`, `tool_counts` (tool name → count).

**Caching:** Container metrics endpoint caches trace counts per session with a 60s TTL to reduce LangFuse API load.

## NATS Integration

**Status:** `nats_client.py` is imported by `api.py` but the implementation file is not yet present in the repository. The NATS integration code in `api.py` (handlers, subscriptions) is complete, but the `BrainboxNATSClient` class itself needs to be implemented.

When NATS is enabled (`CL_NATS__ENABLED=true`), brainbox subscribes to container event channels and can publish commands.

**Subscriptions (set up during lifespan):**

| Subject Pattern | Handler | Purpose |
|----------------|---------|---------|
| `brainbox.*.questions` | `_handle_agent_question` | Agent asks a question |
| `brainbox.*.progress` | `_handle_progress_update` | Task progress updates |
| `brainbox.*.results` | `_handle_result` | Task completion results |
| `brainbox.*.errors` | `_handle_error` | Task errors |
| `brainbox.*.cancelled` | `_handle_cancelled` | Task cancellations |

All NATS events update the async task store (`_tasks`) and broadcast to SSE clients.

**Publishing:** `_nats_client.publish_command(session_name, command)` sends commands to containers, used by the query endpoint for async task dispatch.

## Structured Logging

All modules use `structlog` configured for JSON output to stdout.

**Log format:**
```json
{
  "timestamp": "2026-02-21T10:30:45Z",
  "level": "info",
  "event": "container.started",
  "session_name": "my-project",
  "container_name": "developer-my-project",
  "metadata": {"port": 7681, "backend": "docker"}
}
```

**Key events:**

| Event | Level | Module |
|-------|-------|--------|
| `api.started` | info | api.py |
| `audit.operation` | info | api.py |
| `container.cosign_verified` | info | lifecycle.py |
| `container.configured` | info | lifecycle.py |
| `container.started` | info | lifecycle.py |
| `container.monitoring` | info | lifecycle.py |
| `container.recycled` | info | lifecycle.py |
| `hub.initialized` | info | hub.py |
| `hub.state_restored` | info | hub.py |
| `registry.agent_loaded` | info | registry.py |
| `registry.token_issued` | info | registry.py |
| `router.task_started` | info | router.py |
| `router.task_completed` | info | router.py |
| `messages.routed` | info | messages.py |
| `messages.rejected` | warning | messages.py |
| `nats.connected` | info | api.py |
| `monitor.health_check` | info/warning | monitor.py |
