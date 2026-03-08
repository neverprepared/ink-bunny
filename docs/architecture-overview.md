# ink-bunny Architecture Overview

## System Diagram

```mermaid
graph TB
    subgraph User["User Layer"]
        CLI["Claude Code CLI"]
        Browser["Browser"]
        Homebrew["Homebrew Tap<br/><i>neverprepared/ink-bunny</i>"]
    end

    subgraph Reflex["Reflex — Claude Code Plugin"]
        direction TB
        PluginManifest["Plugin Manifest"]

        subgraph Pillars["Four Pillars"]
            Skills["42 Skills<br/><i>pattern/knowledge definitions</i>"]
            Commands["19 Slash Commands<br/><i>/reflex:*</i>"]
            Agents["2 Agents<br/><i>rag-proxy, workflow-orchestrator</i>"]
            Workflows["4 Workflow Templates<br/><i>jira, github, standalone, custom</i>"]
        end

        subgraph Hooks["Hook System"]
            SessionStart["SessionStart<br/><i>dependency check, brainbox connect</i>"]
            PreToolUse["PreToolUse<br/><i>guardrails, qdrant routing</i>"]
            PostToolUse["PostToolUse<br/><i>langfuse tracing, notifications</i>"]
        end

        MCPCatalog["MCP Catalog<br/><i>17 server definitions</i>"]
        Scripts["Scripts<br/><i>guardrail.py, ingest.py,<br/>summarize.py, langfuse-trace.py</i>"]
    end

    subgraph Brainbox["Brainbox — Session Manager"]
        direction TB
        subgraph API["FastAPI Backend"]
            Router["REST API<br/><i>/api/sessions, /api/metrics,<br/>/api/hub, /api/events</i>"]
            Lifecycle["Container Lifecycle<br/><i>create, start, stop, delete</i>"]
            Monitor["Monitoring<br/><i>CPU, memory, uptime</i>"]
            Hub["Hub State<br/><i>tasks, agents, tokens</i>"]
            SSE["SSE Event Stream"]
            MCPServer["MCP Server<br/><i>brainbox mcp</i>"]
            Secrets["Secrets Manager"]
            Policy["Policy / Hardening<br/><i>cosign, config roles</i>"]
        end

        subgraph Dashboard["Svelte 5 Dashboard"]
            AppShell["AppShell<br/><i>CSS Grid layout</i>"]
            Sidebar["Sidebar<br/><i>collapsible nav</i>"]
            Containers["ContainersPanel<br/><i>session cards, terminals</i>"]
            DashPanel["DashboardPanel<br/><i>stats, metrics, hub activity</i>"]
        end
    end

    subgraph DockerContainers["Docker Containers — Sandboxed Sessions"]
        direction LR
        Developer["Developer<br/><i>full Claude Code + tools</i>"]
        Performer["Performer<br/><i>restricted execution</i>"]
        Researcher["Researcher<br/><i>read-only exploration</i>"]
    end

    subgraph ShellProfiler["Shell Profiler — Go CLI"]
        ProfileMgr["Profile Manager<br/><i>create, select, list, delete</i>"]
        Direnv["direnv Integration<br/><i>per-workspace env vars</i>"]
        Dotfiles["Dotfiles & Git Config"]
    end

    subgraph Infrastructure["Infrastructure Services"]
        Qdrant["Qdrant<br/><i>Vector DB :6333</i>"]
        LangFuse["LangFuse<br/><i>LLM Observability :3000</i>"]
        MinIO["MinIO<br/><i>Object Storage</i>"]
        Docker["Docker Engine"]
    end

    subgraph MCPServers["MCP Server Integrations"]
        direction LR
        GitHub["GitHub"]
        Atlassian["Jira / Confluence"]
        Azure["Azure / DevOps"]
        Google["Google Workspace"]
        K8s["Kubernetes"]
        Spacelift["Spacelift"]
        Playwright["Playwright"]
        SQLServer["SQL Server"]
        UptimeKuma["Uptime Kuma"]
    end

    %% Connections
    CLI --> Reflex
    CLI --> Brainbox
    Browser --> Dashboard
    Homebrew -.->|installs| CLI

    Reflex -->|manages| MCPCatalog
    MCPCatalog -->|registers| MCPServers
    Hooks -->|invoke| Scripts
    Agents -->|query| Qdrant
    Scripts -->|trace| LangFuse
    Scripts -->|ingest| Qdrant

    Router -->|manages| Lifecycle
    Lifecycle -->|provisions| DockerContainers
    Monitor -->|inspects| DockerContainers
    SSE -->|streams to| Dashboard
    MCPServer -->|exposes| Router

    DockerContainers -->|run on| Docker
    ShellProfiler -->|configures env for| DockerContainers

    Brainbox -->|connects| Docker

    classDef user fill:#4A90D9,stroke:#2C5F8A,color:#fff
    classDef plugin fill:#7B68EE,stroke:#5B4ACE,color:#fff
    classDef brainbox fill:#E8913A,stroke:#C67A2E,color:#fff
    classDef container fill:#50C878,stroke:#3AA35E,color:#fff
    classDef profiler fill:#DA70D6,stroke:#B05CAE,color:#fff
    classDef infra fill:#708090,stroke:#556B7F,color:#fff
    classDef mcp fill:#20B2AA,stroke:#178F87,color:#fff

    class CLI,Browser,Homebrew user
    class Skills,Commands,Agents,Workflows,Hooks,MCPCatalog,Scripts,PluginManifest,SessionStart,PreToolUse,PostToolUse plugin
    class Router,Lifecycle,Monitor,Hub,SSE,MCPServer,Secrets,Policy,AppShell,Sidebar,Containers,DashPanel brainbox
    class Developer,Performer,Researcher container
    class ProfileMgr,Direnv,Dotfiles profiler
    class Qdrant,LangFuse,MinIO,Docker infra
    class GitHub,Atlassian,Azure,Google,K8s,Spacelift,Playwright,SQLServer,UptimeKuma mcp
```

## Package Summary

| Package | Language | What It Does |
|---------|----------|-------------|
| **brainbox** | Python + Svelte | FastAPI backend + dashboard for managing sandboxed Claude Code sessions in Docker containers |
| **reflex** | Markdown + Bash/Python | Claude Code plugin — skills, commands, agents, workflow templates, hooks, and MCP catalog |
| **shell-profiler** | Go | CLI for managing workspace-specific environment profiles via direnv |
| **docker** | Dockerfile + Compose | Container images (3 roles) and infrastructure services (Qdrant, LangFuse, MinIO) |
| **docs** | Markdown | Three-phase architecture roadmap (Foundation → Hardened → Production) |

## Data Flow

```mermaid
sequenceDiagram
    participant U as User
    participant CC as Claude Code + Reflex
    participant BB as Brainbox API
    participant D as Docker Container
    participant Q as Qdrant
    participant LF as LangFuse

    U->>CC: Task request
    CC->>CC: Guardrail hook (PreToolUse)
    CC->>Q: RAG context lookup
    Q-->>CC: Relevant knowledge
    CC->>BB: Create/manage session
    BB->>D: Provision container (developer/performer/researcher)
    D-->>BB: Status + metrics
    BB-->>CC: Session ready
    CC->>CC: Execute task (skills, agents, MCP tools)
    CC->>LF: Trace tool calls (PostToolUse)
    CC->>Q: Store new knowledge
    CC-->>U: Result
```

## Distribution

All three packages ship via a single Homebrew tap (`neverprepared/ink-bunny`). Reflex is also available on the Claude Code plugin marketplace. Releases use scoped tags (`brainbox/vX.Y.Z`, `shell-profiler/vX.Y.Z`, `reflex/vX.Y.Z`).
