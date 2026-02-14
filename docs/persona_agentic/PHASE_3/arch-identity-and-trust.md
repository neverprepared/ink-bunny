# Identity & Trust

Establishes who or what is making a request at every boundary in the system. Without this layer, any component can impersonate any other.

Replaces the orchestrator-issued container tokens from PHASE_2 with cryptographic workload identity via SPIFFE/SPIRE. Agents now receive short-lived SVIDs instead of container tokens, enabling mTLS, workload attestation, and HSM-backed PKI.

## Trust Boundaries

Three boundaries where identity must be verified. Each crossing requires a different credential.

```mermaid
graph TD
    User([User / Operator])

    subgraph External["External → Platform"]
        CLI[CLI<br/>Local Machine]
        CI[CI / Automation<br/>API Token]
    end

    Orch((Orchestration<br/>Hub))

    subgraph Platform["Platform → Sandbox"]
        SPIRE[SPIRE Server<br/>Issues SVIDs]
    end

    subgraph Sandbox["Sandbox → Platform"]
        AgentA[Agent A<br/>SVID]
        AgentB[Agent B<br/>SVID]
        AgentN[Agent N<br/>SVID]
    end

    User --> CLI & CI
    CLI -->|"local auth"| Orch
    CI -->|"bearer token"| Orch
    Orch -->|"request SVID"| SPIRE
    SPIRE -->|"issue scoped SVID"| AgentA & AgentB & AgentN
    AgentA & AgentB & AgentN -->|"present SVID"| Orch
```

| Boundary | Who crosses | Credential | Verified by |
|---|---|---|---|
| **External → Platform** | User (CLI) | Local OS identity / session | Orchestrator |
| **External → Platform** | CI pipeline | API token (from 1Password) | Orchestrator |
| **Platform → Sandbox** | Orchestrator → Agent | SPIFFE SVID issued by SPIRE | Agent receives at start |
| **Sandbox → Platform** | Agent → Orchestrator | SPIFFE SVID | Orchestrator validates on every request |

---

## User Authentication

Two paths into the orchestrator depending on context.

```mermaid
graph LR
    subgraph Local["Local Dev"]
        Dev([Developer])
        CLI[CLI Tool]
        Dev -->|"run command"| CLI
        CLI -->|"local auth<br/>(OS session)"| Orch
    end

    Orch((Orchestrator))

    subgraph Automation["CI / Automation"]
        Pipeline([CI Pipeline])
        Token[API Token<br/>from 1Password]
        Pipeline -->|"resolve token"| Token
        Token -->|"bearer auth"| Orch
    end
```

| Context | Auth Method | Token Lifetime | Stored In |
|---|---|---|---|
| **Local CLI** | OS session identity — you're on the machine | Session duration | N/A |
| **CI / Automation** | Scoped API token, resolved via `op` at pipeline start | Short-lived (pipeline duration) | 1Password vault |

### API Token Lifecycle

```mermaid
sequenceDiagram
    participant CI as CI Pipeline
    participant OP as 1Password
    participant Orch as Orchestrator

    CI->>OP: resolve op://vault/orchestrator/api-token
    OP-->>CI: token (scoped, rotatable)
    CI->>Orch: POST /task (Authorization: Bearer <token>)
    Orch->>Orch: validate token, check scope
    Orch-->>CI: 200 task accepted
```

---

## Agent Identity (SPIFFE / SPIRE)

Each agent container receives a SPIFFE SVID (SPIFFE Verifiable Identity Document) at the Configure phase of its lifecycle. Agents never self-issue identity.

### SVID Issuance Flow

```mermaid
sequenceDiagram
    participant Orch as Orchestrator
    participant SPIRE as SPIRE Server
    participant Agent as Agent Container

    Orch->>SPIRE: register workload (agent name, task ID, capabilities)
    SPIRE-->>Orch: registration entry created
    Orch->>Agent: provision container with SPIRE agent sidecar
    Agent->>SPIRE: workload attestation (prove I am this container)
    SPIRE-->>Agent: issue SVID (x509 or JWT)
    Note over Agent: SVID encodes identity + expiry
    Agent->>Orch: all requests carry SVID
    Orch->>SPIRE: validate SVID on each request
```

### SVID Contents

The SVID encodes everything the orchestrator needs to make policy decisions.

```
spiffe://agentic-platform/agent/<agent-name>/task/<task-id>
```

| Field | Purpose |
|---|---|
| **Trust domain** | `agentic-platform` — scopes all identities to this system |
| **Agent name** | Which agent image this container is running |
| **Task ID** | Which specific task this container was spawned for |
| **Expiry** | Matches container TTL — identity dies with the container |
| **Capabilities** | Encoded in registration entry — what this agent is allowed to do |

### SVID Type Policy

Two SVID types exist. Each has different security properties — use the right one for the context.

```mermaid
graph LR
    subgraph x509["x509 SVIDs (default)"]
        mTLS["Agent ↔ Orchestrator<br/>mutual TLS"]
        StateProxy["Agent ↔ Shared State Proxy<br/>mutual TLS"]
        AgentComm["Agent ↔ Agent<br/>(via orchestrator mTLS)"]
    end

    subgraph JWT["JWT SVIDs (restricted)"]
        ExtAPI["External API calls<br/>where mTLS not supported"]
        Webhook["Webhook callbacks<br/>short-lived, audience-bound"]
    end

    subgraph Never["Never Acceptable"]
        Logs["JWT in logs"]
        LongLived["Long-lived JWT"]
        NoClaim["JWT without audience claim"]
    end

    style Never stroke:#f00,stroke-width:2px
```

| SVID Type | Use Case | Security Properties |
|---|---|---|
| **x509** | All agent-to-orchestrator communication, shared state access, inter-agent routing | Non-replayable (bound to TLS session), enables mTLS, cannot be exfiltrated from wire |
| **JWT** | External API calls where mTLS is not practical | Bearer token — **replayable if stolen**. Must have: audience claim, ≤ 60s TTL, never logged |

| Envoy Trust Rule | Detail |
|---|---|
| **SPIRE trust bundle only** | Envoy accepts only certificates from the SPIRE trust bundle — rejects system CAs |
| **Max chain depth: 2** | Root → Intermediate → SVID. No deeper chains accepted |
| **Certificate pinning** | Orchestrator and shared state proxy pin to SPIRE-issued certificates only |

### Why SPIFFE/SPIRE

| Concern | How SPIRE handles it |
|---|---|
| **No static secrets** | SVIDs are short-lived and auto-rotated — no long-lived credentials in containers |
| **Workload attestation** | SPIRE verifies the container is what it claims via node and workload attestors (Docker, K8s) |
| **Multi-environment** | SPIRE has attestors for Docker, Kubernetes, and bare metal — fits local dev, CI, and K8s |
| **mTLS built in** | x509 SVIDs enable mTLS between agent and orchestrator out of the box |
| **No agent cooperation needed** | The SPIRE agent sidecar handles attestation — the agent process just uses the SVID |

### Identity Lifecycle

```mermaid
graph LR
    Register[Register<br/>Orch registers workload<br/>with SPIRE]
    Attest[Attest<br/>Container proves identity<br/>to SPIRE agent]
    Issue[Issue<br/>SPIRE issues SVID<br/>to container]
    Use[Use<br/>Agent presents SVID<br/>on every request]
    Rotate[Rotate<br/>SPIRE auto-rotates<br/>before expiry]
    Expire[Expire<br/>Container recycle<br/>kills SVID]

    Register --> Attest --> Issue --> Use
    Use --> Rotate --> Use
    Use -->|"container recycled"| Expire
```

| Phase | What Happens |
|---|---|
| **Register** | Orchestrator creates a SPIRE registration entry with agent name, task ID, and allowed capabilities |
| **Attest** | SPIRE workload attestor verifies the container's identity (Docker PID, K8s pod, etc.) |
| **Issue** | SPIRE issues an SVID (x509 cert or JWT) to the verified container |
| **Use** | Agent includes the SVID in every request to the orchestrator and shared state |
| **Rotate** | SPIRE auto-rotates the SVID before expiry — no agent involvement needed |
| **Expire** | On container recycle, the registration entry is deleted and the SVID becomes invalid |

---

## SPIRE PKI & Root CA Lifecycle

The SPIRE root CA is the most sensitive cryptographic material in the system. Compromise of the root key breaks all identity guarantees.

### CA Hierarchy

```mermaid
graph TD
    subgraph HSM["Hardware Security Module"]
        RootCA["Root CA<br/>offline, HSM-bound<br/>10-year lifetime"]
    end

    subgraph SPIREServer["SPIRE Server"]
        IntermediateCA["Intermediate CA<br/>signs SVIDs<br/>24-hour lifetime"]
    end

    subgraph Agents["Agent Containers"]
        SVID1["SVID<br/>Agent A<br/>5-min TTL"]
        SVID2["SVID<br/>Agent B<br/>5-min TTL"]
        SVIDN["SVID<br/>Agent N<br/>5-min TTL"]
    end

    RootCA -->|"signs intermediate<br/>(offline ceremony)"| IntermediateCA
    IntermediateCA -->|"signs SVIDs<br/>(automated, high-frequency)"| SVID1 & SVID2 & SVIDN
```

| Layer | Key Storage | Lifetime | Rotation |
|---|---|---|---|
| **Root CA** | HSM / TPM — never exported, never online except during signing ceremony | 10 years | Manual ceremony with trust bundle overlap |
| **Intermediate CA** | SPIRE server memory — encrypted at rest on disk | 24 hours | Auto-rotated by SPIRE, signed by root CA |
| **SVID** | Agent sidecar memory — never written to disk | 5 minutes | Auto-rotated by SPIRE agent before expiry |

### Root CA Rotation

Root key rotation is a planned ceremony, not an automated process.

```mermaid
sequenceDiagram
    participant Operator as Operator
    participant HSM as HSM
    participant SPIRE as SPIRE Server
    participant Agents as Agent Fleet

    Note over Operator: Rotation ceremony begins
    Operator->>HSM: generate new root key pair
    HSM-->>Operator: new root CA certificate
    Operator->>SPIRE: add new root to trust bundle (keep old root)
    SPIRE->>Agents: distribute updated trust bundle
    Note over Agents: Agents trust both old and new root

    Note over Operator: Overlap period (7+ days)
    Operator->>HSM: sign new intermediate CA with new root
    SPIRE->>Agents: new SVIDs chain to new intermediate

    Note over Operator: After all SVIDs renewed
    Operator->>SPIRE: remove old root from trust bundle
    SPIRE->>Agents: distribute final trust bundle
    Note over Agents: Only new root trusted
```

| Step | Detail |
|---|---|
| **Generate new root** | New key pair created in HSM — old key remains active |
| **Add to trust bundle** | Both old and new root CAs are trusted simultaneously |
| **Overlap period** | Minimum 7 days — all agents receive updated trust bundle before old root is removed |
| **Sign new intermediate** | New intermediate CA signed by new root — SPIRE begins issuing SVIDs under new chain |
| **Remove old root** | Only after all active SVIDs chain to the new root — verified by SPIRE telemetry |

### SVID TTL Policy

Aggressive TTLs limit the damage window from a compromised SVID.

| Parameter | Value | Rationale |
|---|---|---|
| **SVID TTL** | 5 minutes | Compromise window bounded — stolen SVID expires before meaningful exfiltration |
| **Rotation trigger** | 50% of TTL (2.5 minutes) | SPIRE agent requests renewal well before expiry |
| **Grace period** | 30 seconds after expiry | Allows in-flight requests to complete |
| **Max container TTL** | Matches [[arch-brainbox]] lifecycle TTL | SVID cannot outlive its container |

### SVID Revocation

SPIRE does not natively support certificate revocation lists (CRLs). Deleting a registration entry prevents renewal but does not invalidate an already-issued SVID. The deny-list compensates for this gap.

```mermaid
graph LR
    subgraph Detection["Compromise Detected"]
        Falco[Falco Alert]
        Operator[Operator Action]
    end

    subgraph Revocation["Revocation Path"]
        SPIRE_Delete["SPIRE: delete<br/>registration entry<br/>(stops renewal)"]
        DenyList["Deny-List: add SVID<br/>fingerprint<br/>(immediate block)"]
    end

    subgraph Enforcement["Enforcement Points"]
        Envoy_Check["Envoy<br/>check deny-list<br/>on every request"]
        Orch_Check["Orchestrator<br/>check deny-list<br/>on every request"]
        Proxy_Check["Shared State Proxy<br/>check deny-list<br/>on every request"]
    end

    Quarantine["Quarantine<br/>agent data in<br/>Shared State"]

    Falco & Operator --> SPIRE_Delete & DenyList
    DenyList --> Envoy_Check & Orch_Check & Proxy_Check
    SPIRE_Delete -.->|"SVID expires in ≤5 min"| Expired([Expired])
    DenyList -->|"immediate"| Quarantine
```

| Mechanism | Timing | What It Does |
|---|---|---|
| **Delete registration entry** | Immediate | Stops SPIRE from renewing the SVID — it expires within 5 minutes |
| **Deny-list at enforcement points** | Immediate | Envoy, orchestrator, and shared state proxy reject any request bearing the denied SVID fingerprint |
| **Quarantine shared state** | Immediate | All data attributed to the revoked SVID is flagged as untrusted — see [[arch-shared-state#Quarantine]] |
| **Natural expiry** | ≤ 5 minutes | Even without deny-list, the short TTL ensures the SVID dies quickly |

---

## Image Integrity & Supply Chain

Before a container is provisioned, the image itself must be verified. This happens at the Provision phase, before SPIRE attestation.

```mermaid
graph LR
    Registry[(Container<br/>Registry)]
    Cosign[cosign verify<br/>check signature]
    Scan[Vulnerability Scan<br/>reject critical CVEs]
    Policy[Policy Engine<br/>approved base image?]
    Provision[Provision<br/>Container]

    Registry --> Cosign
    Cosign -->|"valid signature"| Scan
    Cosign -.->|"unsigned / invalid"| Reject([Reject])
    Scan -->|"no critical CVEs"| Policy
    Scan -.->|"critical CVEs found"| Reject
    Policy -->|"approved base"| Provision
    Policy -.->|"unapproved base"| Reject

    style Reject stroke:#f00,stroke-width:2px
```

| Gate | What's Checked | Failure Mode |
|---|---|---|
| **Signature (cosign)** | Image signed by trusted key, digest matches manifest | Unsigned or tampered → rejected |
| **Vulnerability scan** | No critical CVEs in image layers | Critical CVE → blocked until patched |
| **Base image policy** | Image built from an approved base | Unapproved base → rejected |

---

## Message & Data Integrity

All messages through the orchestrator carry the sender's SVID. The orchestrator validates identity on every request.

```mermaid
graph LR
    Agent[Agent A]
    Msg["Message<br/>+ SVID<br/>+ nonce + timestamp"]
    Orch((Orchestrator))
    Verify{Validate SVID<br/>+ nonce + timestamp}
    Route[Route to<br/>recipient]
    Reject([Reject])

    Agent --> Msg --> Orch --> Verify
    Verify -->|"valid"| Route
    Verify -.->|"expired / replay / invalid"| Reject

    style Reject stroke:#f00,stroke-width:2px
```

| Control | How |
|---|---|
| **Identity on every message** | SVID is presented with each request — orchestrator validates against SPIRE |
| **Replay prevention** | Nonce + timestamp + signature on each message — orchestrator rejects duplicates and expired payloads |
| **Artifact attribution** | Writes to shared state include the SVID — origin is cryptographically verifiable |
| **Log attribution** | Observability layer records the SVID claim — unsigned log entries are flagged |
| **mTLS** | x509 SVIDs enable mutual TLS between agent containers and the orchestrator |

### Replay Protection Detail

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Orch as Orchestrator
    participant NonceStore as Nonce Store<br/>(durable)

    Agent->>Orch: request (payload + nonce + timestamp + HMAC)
    Orch->>Orch: verify HMAC covers payload + nonce + timestamp
    Orch->>Orch: check timestamp within ±30s of server clock
    Orch->>NonceStore: has this nonce been seen?
    NonceStore-->>Orch: no → first use
    Orch->>NonceStore: store nonce (TTL = clock skew window)
    Orch-->>Agent: 200 accepted

    Note over Agent,Orch: Replay attempt
    Agent->>Orch: same request replayed
    Orch->>NonceStore: has this nonce been seen?
    NonceStore-->>Orch: yes → duplicate
    Orch-->>Agent: 409 rejected (replay)
```

| Parameter | Value | Rationale |
|---|---|---|
| **Nonce generation** | Server-issued or agent-generated UUID v4 | Unpredictable, non-sequential |
| **Nonce storage** | Durable key-value store with TTL-based expiry | Survives orchestrator restart — prevents replay after recovery |
| **Clock skew tolerance** | ±30 seconds | Requires NTP on all hosts — reject messages outside window |
| **Cryptographic binding** | HMAC-SHA256 over `payload \|\| nonce \|\| timestamp` using SVID-derived key | Attacker cannot modify payload without invalidating the signature |
| **Nonce TTL** | 60 seconds (2× clock skew window) | Nonces expire after replay window closes — bounds storage growth |

---

## Gaps This Page Addresses

- [x] No authentication model (user → orchestrator → agent)
- [x] Agent impersonation on the orchestrator
- [x] No image signing or supply chain verification
- [x] No message integrity or replay protection
- [x] No cryptographic attribution for shared state writes or audit logs
- [x] No encryption in transit (mTLS via SPIFFE x509 SVIDs)
- [x] SPIRE root CA lifecycle unspecified — root key in HSM, intermediate CA for daily issuance, rotation ceremony with overlap
- [x] SVID revocation not possible — compensated by 5-minute TTLs and deny-list at all enforcement points
- [x] No SVID TTL policy — 5-minute TTLs bound compromise window
- [x] SVID type (x509 vs JWT) unspecified — x509 for mTLS, JWT restricted to external APIs with audience claim and ≤60s TTL
- [x] Replay protection underspecified — server-issued nonces, durable storage, HMAC binding, clock skew tolerance
