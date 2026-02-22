# Brainbox Documentation

Brainbox is a FastAPI backend with a Svelte 5 dashboard for managing sandboxed Claude Code sessions. It provisions containers (Docker) or VMs (UTM), injects secrets, monitors health, and exposes a REST API and MCP server for programmatic control.

## Quick Start

```bash
just bb-api              # Start API on :9999
just bb-dashboard        # Start API + built dashboard
just bb-docker-build     # Build the brainbox container image
just bb-docker-start     # Launch a default session
```

## Module Map

```mermaid
graph TD
    subgraph API["API Layer"]
        api[api.py<br/>FastAPI routes + SSE]
        mcp[mcp_server.py<br/>MCP tool adapter]
        rate[rate_limit.py<br/>slowapi limiter]
        val[validation.py<br/>input validators]
        models_api[models_api.py<br/>request schemas]
    end

    subgraph Lifecycle["Container Lifecycle"]
        lc[lifecycle.py<br/>5-phase pipeline]
        cosign[cosign.py<br/>image verification]
        hard[hardening.py<br/>seccomp + caps]
        secrets[secrets.py<br/>1Password / files]
        mon[monitor.py<br/>health check loop]
    end

    subgraph Backends["Backends"]
        be_init[backends/__init__.py<br/>factory]
        docker_be[backends/docker.py<br/>Docker SDK]
        utm_be[backends/utm.py<br/>UTM + SSH]
    end

    subgraph Hub["Hub / Orchestration"]
        hub[hub.py<br/>init + state persistence]
        reg[registry.py<br/>agents + tokens]
        router[router.py<br/>task dispatch]
        msg[messages.py<br/>message routing]
        pol[policy.py<br/>authorization]
    end

    subgraph Observability["Observability"]
        lf[langfuse_client.py<br/>trace queries]
        art[artifacts.py<br/>MinIO S3 store]
    end

    subgraph Core["Core"]
        cfg[config.py<br/>pydantic settings]
        models[models.py<br/>domain models]
        logmod[log.py<br/>structlog JSON]
    end

    api --> lc
    api --> hub
    api --> lf
    api --> art
    api --> rate
    api --> val
    api --> models_api
    mcp --> api

    lc --> be_init --> docker_be & utm_be
    lc --> cosign
    lc --> hard
    lc --> secrets
    lc --> mon

    hub --> reg
    hub --> router
    hub --> msg
    router --> pol
    msg --> pol
    router --> lc

    cfg -.-> api & lc & hub & lf & art & mon
    models -.-> lc & hub & router & reg & msg
    logmod -.-> api & lc & hub & router & reg & msg & mon

    classDef apiStyle fill:#f97316,stroke:#ea580c,color:#fff
    classDef lcStyle fill:#22c55e,stroke:#16a34a,color:#fff
    classDef hubStyle fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef obsStyle fill:#6b7280,stroke:#4b5563,color:#fff
    classDef coreStyle fill:#a855f7,stroke:#9333ea,color:#fff
    classDef beStyle fill:#14b8a6,stroke:#0d9488,color:#fff

    class api,mcp,rate,val,models_api apiStyle
    class lc,cosign,hard,secrets,mon lcStyle
    class hub,reg,router,msg,pol hubStyle
    class lf,art obsStyle
    class cfg,models,logmod coreStyle
    class be_init,docker_be,utm_be beStyle
```

## Capability Overview

```mermaid
mindmap
  root((Brainbox))
    Session Management
      Docker containers
      UTM virtual machines
      5-phase lifecycle
      Cosign verification
      Volume mounts
      Profile credentials
    Hub / Orchestration
      Agent registry
      Token issuance
      Task routing
      Message routing
      Policy engine
      State persistence
    Observability
      LangFuse traces
      Qdrant vector DB
      Container metrics
      Health monitoring
      Structured logging
    Security
      1Password secrets
      Cosign signatures
      Rate limiting
      Input validation
      Audit logging
      Container hardening
    Dashboard
      Svelte 5 SPA
      Real-time SSE
      Container metrics
      Terminal access
      Trace timeline
      Tool breakdown
```

## Module Reference

| Module | Responsibility | Doc |
|--------|---------------|-----|
| `api.py` | FastAPI routes, SSE, lifespan | [api-reference.md](api-reference.md) |
| `mcp_server.py` | MCP tool adapter (16 tools) | [api-reference.md](api-reference.md) |
| `rate_limit.py` | slowapi rate limiter | [api-reference.md](api-reference.md) |
| `validation.py` | Session name, artifact key, volume, port, role validators | [api-reference.md](api-reference.md) |
| `models_api.py` | Pydantic request schemas | [api-reference.md](api-reference.md) |
| `lifecycle.py` | 5-phase pipeline: provision, configure, start, monitor, recycle | [lifecycle.md](lifecycle.md) |
| `cosign.py` | Container image signature verification (keyless + key-based) | [lifecycle.md](lifecycle.md) |
| `hardening.py` | Seccomp, cap_drop, read-only rootfs, tmpfs, resource limits | [lifecycle.md](lifecycle.md) |
| `secrets.py` | 1Password service account or plaintext file resolution | [observability.md](observability.md) |
| `monitor.py` | Async health check loop with TTL enforcement | [observability.md](observability.md) |
| `backends/__init__.py` | Backend factory (`create_backend`) | [lifecycle.md](lifecycle.md) |
| `backends/docker.py` | Docker SDK: provision, configure, start, stop, health, exec | [lifecycle.md](lifecycle.md) |
| `backends/utm.py` | UTM/SSH: provision, configure, start, stop, health, exec | [lifecycle.md](lifecycle.md) |
| `hub.py` | Hub init/shutdown, state persistence, periodic flush | [hub.md](hub.md) |
| `registry.py` | Agent loading, token issuance/validation/revocation | [hub.md](hub.md) |
| `router.py` | Task submit, complete, fail, cancel, check running | [hub.md](hub.md) |
| `messages.py` | Message routing with pending queue and audit log | [hub.md](hub.md) |
| `policy.py` | Task assignment, message, and capability authorization | [hub.md](hub.md) |
| `langfuse_client.py` | LangFuse trace/observation queries via HTTP | [observability.md](observability.md) |
| `artifacts.py` | MinIO S3 artifact upload/download/list/delete | [observability.md](observability.md) |
| `config.py` | Pydantic settings from `CL_*` env vars | [lifecycle.md](lifecycle.md) |
| `models.py` | Domain models (Agent, Session, Task, Token, Message) | [hub.md](hub.md) |
| `log.py` | structlog JSON logging with session context | [observability.md](observability.md) |
| `dashboard/` | Svelte 5 SPA with 3 panels | [dashboard.md](dashboard.md) |

## Documents

1. **[lifecycle.md](lifecycle.md)** — Container lifecycle pipeline, backends, cosign, hardening, volume mounts
2. **[hub.md](hub.md)** — Hub orchestration: agents, tokens, tasks, messages, policy
3. **[api-reference.md](api-reference.md)** — REST API endpoints, MCP server, rate limits
4. **[observability.md](observability.md)** — Monitoring, metrics, LangFuse, artifacts, secrets, SSE
5. **[dashboard.md](dashboard.md)** — Svelte 5 dashboard components, state, data flow
