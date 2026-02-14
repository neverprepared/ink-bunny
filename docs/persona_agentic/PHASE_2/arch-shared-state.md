# Shared State

Durable persistence layer for cross-agent data. The only sanctioned path for data that outlives a single container. All access is authenticated, scoped, and audited.

## Architecture

```mermaid
graph TD
    Agent1[Agent A]
    Agent2[Agent B]
    Agent3[Agent N]

    Proxy[Shared State Proxy<br/>token validation<br/>namespace enforcement<br/>write signing]

    subgraph Persistence["Shared State"]
        VectorDB[(Vector DB<br/>Semantic Retrieval)]
        MinIO[(MinIO<br/>S3-Compatible<br/>Artifact Store)]
    end

    Agent1 & Agent2 & Agent3 -->|"request + token"| Proxy
    Proxy -->|"validated + scoped"| VectorDB & MinIO
    Proxy -.->|"unauthorized → reject"| Reject([Block])

    Observe[Observability]
    Proxy --> Observe

    style Reject stroke:#f00,stroke-width:2px
```

Agents never access stores directly. All reads and writes go through an authenticated proxy that enforces namespace isolation and validates container tokens.

## Stores

| Store | Purpose | Examples |
|---|---|---|
| **Vector DB** | Semantic search and retrieval across agent workloads | Embeddings, conversation history, knowledge base |
| **MinIO (S3-Compatible)** | Durable, addressable outputs from agent tasks | Generated files, reports, build artifacts, datasets |

### MinIO Artifact Store

MinIO provides the concrete S3-compatible artifact store. Self-hosted, already running in the home lab.

| Property | Detail |
|---|---|
| **Access protocol** | S3 API via boto3/minio-py through the shared state proxy |
| **Bucket structure** | `artifacts/<agent-name>/<task-id>/<filename>` |
| **Access control** | MinIO bucket policies scoped per-agent (enforced via proxy) |
| **Retention** | Configurable per-bucket lifecycle rules |
| **Agent upload flow** | Daemon uploads via S3 API after task execution → posts `task.completed` with S3 URI to hub |

## Access Control

### Namespace Isolation

Each agent (or task) operates in a scoped namespace. Cross-namespace access requires explicit policy.

```mermaid
graph LR
    subgraph Namespaces["Namespace Isolation"]
        NSA["Namespace: Agent A<br/>Agent A can read/write"]
        NSB["Namespace: Agent B<br/>Agent B can read/write"]
        Shared["Namespace: shared<br/>explicitly granted agents only"]
    end

    AgentA[Agent A<br/>Token] -->|own namespace| NSA
    AgentB[Agent B<br/>Token] -->|own namespace| NSB
    AgentA & AgentB -.->|"OPA policy grant"| Shared
    AgentA -.->|"blocked by default"| NSB
```

| Rule | Detail |
|---|---|
| **Default: own namespace only** | Agents can read/write only data in their own namespace |
| **Cross-namespace reads** | Require explicit OPA policy grant based on container token identity |
| **Shared namespace** | Opt-in space for cross-agent data — requires policy approval |
| **Vector DB tenant isolation** | Collections scoped per namespace — queries cannot cross boundaries without policy |
| **MinIO path isolation** | Artifacts stored under `artifacts/<namespace>/<task-id>/` — proxy enforces S3 prefix boundaries |

### Write Integrity

Every write is attributed to the originating container token for auditability.

| Control | Detail |
|---|---|
| **Attributed writes** | Each write includes the agent's container token ID for traceability |
| **Attribution** | Every stored object carries: originating token ID, agent name, task ID, timestamp, content hash |
| **Verified reads** | Proxy verifies the token is valid before serving data — expired or revoked tokens are rejected |

## Pipeline Integration

MinIO native bucket notifications deliver artifacts to downstream pipelines without custom webhook code.

### Webhook Push via Bucket Notifications

```mermaid
graph LR
    Agent[Agent Daemon] -->|"upload artifact"| MinIO[(MinIO)]
    MinIO -->|"s3:ObjectCreated:*"| Notify[Bucket Notification]
    Notify -->|"POST webhook"| N8N[n8n]
    Notify -->|"POST webhook"| Jenkins[Jenkins]
```

| Property | Detail |
|---|---|
| **Trigger** | MinIO fires on `s3:ObjectCreated:*` events |
| **Delivery** | POST to configured webhook endpoints (n8n, Jenkins, or any HTTP target) |
| **Payload** | Bucket, key, size, content-type — standard S3 notification format |
| **Multiple targets** | n8n AND Jenkins (or others) can receive the same notification simultaneously |
| **No custom code** | MinIO handles delivery and retry natively — no webhook infrastructure to build |

### Delivery Guarantees

| Guarantee | Detail |
|---|---|
| **Retry** | MinIO retries failed webhook deliveries (configurable retry count and interval) |
| **Idempotency** | Downstream consumers must be idempotent — MinIO may retry on timeout |
| **Queue on failure** | If all targets are down, notifications queue in MinIO until recovery |

## Rules

- Container filesystems are **ephemeral** — anything that must survive a recycle goes here
- Agents access stores only through the authenticated proxy, never via direct filesystem mounts
- All writes are attributed to the originating container token
- All reads require a valid container token
- Cross-namespace access requires explicit OPA policy
- Data retention and classification governed by [[arch-observability#Data Classification]]

## What's Deferred

| Feature | Phase |
|---|---|
| Quarantine (flag compromised agent data as untrusted) | PHASE_3 |
| Per-namespace encryption at rest | PHASE_3 |
| Integrity background scans | PHASE_3 |
| Downstream notification on quarantine | PHASE_3 |
