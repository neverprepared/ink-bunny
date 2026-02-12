# Shared State

Durable persistence layer for cross-agent data. The only sanctioned path for data that outlives a single container. All access is authenticated, scoped, and audited.

## Architecture

```mermaid
graph TD
    Agent1[Agent A]
    Agent2[Agent B]
    Agent3[Agent N]

    Proxy[Shared State Proxy<br/>SVID validation<br/>namespace enforcement<br/>write signing]

    subgraph Persistence["Shared State"]
        VectorDB[(Vector DB<br/>Semantic Retrieval)]
        ArtifactStore[(Artifact Store<br/>Durable Outputs)]
    end

    Agent1 & Agent2 & Agent3 -->|"request + SVID"| Proxy
    Proxy -->|"validated + scoped"| VectorDB & ArtifactStore
    Proxy -.->|"unauthorized → reject"| Reject([Block])

    Observe[Observability]
    Proxy --> Observe

    style Reject stroke:#f00,stroke-width:2px
```

Agents never access stores directly. All reads and writes go through an authenticated proxy that enforces namespace isolation and validates SVIDs.

## Stores

| Store | Purpose | Examples |
|---|---|---|
| **Vector DB** | Semantic search and retrieval across agent workloads | Embeddings, conversation history, knowledge base |
| **Artifact Store** | Durable, addressable outputs from agent tasks | Generated files, reports, build artifacts, datasets |

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

    AgentA[Agent A<br/>SVID] -->|own namespace| NSA
    AgentB[Agent B<br/>SVID] -->|own namespace| NSB
    AgentA & AgentB -.->|"OPA policy grant"| Shared
    AgentA -.->|"blocked by default"| NSB
```

| Rule | Detail |
|---|---|
| **Default: own namespace only** | Agents can read/write only data in their own namespace |
| **Cross-namespace reads** | Require explicit OPA policy grant based on SVID identity |
| **Shared namespace** | Opt-in space for cross-agent data — requires policy approval |
| **Vector DB tenant isolation** | Collections scoped per namespace — queries cannot cross boundaries without policy |
| **Artifact Store path isolation** | Artifacts stored under `/<namespace>/<task-id>/` — proxy enforces path boundaries |

### Write Integrity

Every write includes a cryptographic signature for tamper detection.

| Control | Detail |
|---|---|
| **Signed writes** | Each write includes a signature over the content hash using the agent's SVID |
| **Attribution** | Every stored object carries: originating SVID, task ID, timestamp, content hash |
| **Verified reads** | Consuming agents verify the signature before processing — unsigned or invalid artifacts are rejected |

## Rules

- Container filesystems are **ephemeral** — anything that must survive a recycle goes here
- Agents access stores only through the authenticated proxy, never via direct filesystem mounts
- All writes are signed and attributed to the originating SVID
- All reads verify signatures before processing
- Cross-namespace access requires explicit OPA policy
- Data retention and classification governed by [[arch-observability#Data Classification]]

## What's Deferred

| Feature | Phase |
|---|---|
| Quarantine (flag compromised SVID data as untrusted) | PHASE_3 |
| Per-namespace encryption at rest | PHASE_3 |
| Integrity background scans | PHASE_3 |
| Downstream notification on quarantine | PHASE_3 |
