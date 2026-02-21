# Svelte 5 Dashboard

The brainbox dashboard is a Svelte 5 SPA (Single Page Application) using runes-based reactive state. It provides real-time monitoring and control of sessions across three panels: **Containers**, **Dashboard**, and **Observability**.

**Key characteristics:**
- Hash-based routing (`#containers`, `#dashboard`, `#observability`)
- Svelte 5 runes (`$state`, `$derived`, `$effect`) — no external store library
- SSE for real-time updates + polling for metrics
- Dark theme with CSS custom properties

## Component Tree

```mermaid
graph TB
    Main[main.js<br/>mount App] --> App

    subgraph App["App.svelte"]
        AS[AppShell.svelte<br/>CSS Grid layout]
        NF[Notifications.svelte<br/>Toast container]
    end

    AS --> SB[Sidebar.svelte<br/>Collapsible nav]
    AS --> Router{currentPanel}

    Router -->|containers| CP[ContainersPanel]
    Router -->|dashboard| DP[DashboardPanel]
    Router -->|observability| OP[ObservabilityPanel]

    CP --> SG1[StatsGrid]
    CP --> SC[SessionCard × N]
    CP --> TF[TerminalFrame × N]
    CP --> NSM[NewSessionModal]
    CP --> SIM[SessionInfoModal]
    CP --> ES[EmptyState]

    SC --> Badge[Badge × 4]
    NSM --> Modal1[Modal]
    SIM --> Modal2[Modal]

    DP --> SG2[StatsGrid]
    DP --> MT[MetricsTable]
    DP --> HA[HubActivity]
    MT --> Badge2[Badge × 3 per row]

    OP --> SC2[StatCard × 5]
    OP --> TT[TraceTimeline]
    OP --> TB[ToolBreakdown]

    SG1 --> SC1[StatCard × 4]
    SG2 --> SC3[StatCard × 4]

    classDef panelStyle fill:#ec4899,stroke:#db2777,color:#fff
    classDef compStyle fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef layoutStyle fill:#6b7280,stroke:#4b5563,color:#fff

    class CP,DP,OP panelStyle
    class SC,TF,NSM,SIM,ES,MT,HA,TT,TB,Badge,Badge2 compStyle
    class AS,SB,NF,Router,SG1,SG2,SC1,SC2,SC3,Modal1,Modal2 layoutStyle
```

## Startup & Real-Time Update Flow

```mermaid
sequenceDiagram
    participant Browser
    participant App as App.svelte
    participant Panel as Active Panel
    participant API as /api/*
    participant SSE as /api/events

    Browser->>App: Load SPA
    App->>App: Read hash → currentPanel
    App->>App: Read localStorage → sidebarCollapsed
    App->>Panel: Mount active panel

    Panel->>API: GET /api/sessions
    API-->>Panel: sessions[]

    Panel->>SSE: Connect EventSource
    SSE-->>Panel: data: "connected"

    loop Docker Event
        SSE-->>Panel: data: "start"
        Panel->>API: GET /api/sessions
        API-->>Panel: sessions[] (refreshed)
    end

    loop Metrics Polling (5s)
        Panel->>API: GET /api/metrics/containers
        API-->>Panel: metrics[]
    end

    loop Trace Polling (10s)
        Panel->>API: GET /api/langfuse/sessions/*/summary
        API-->>Panel: summaries[]
    end
```

## Data Flow Map

Each panel fetches specific API endpoints at different cadences.

```mermaid
flowchart LR
    subgraph Panels
        CP[ContainersPanel]
        DP[DashboardPanel]
        OP[ObservabilityPanel]
    end

    subgraph Endpoints
        E1["/api/sessions"]
        E2["/api/metrics/containers"]
        E3["/api/hub/state"]
        E4["/api/langfuse/health"]
        E5["/api/qdrant/health"]
        E6["/api/langfuse/sessions/*/traces"]
        E7["/api/langfuse/sessions/*/summary"]
        E8["/api/events (SSE)"]
    end

    CP -->|on mount + SSE| E1
    CP -->|connect| E8

    DP -->|on mount + SSE| E1
    DP -->|connect| E8

    OP -->|on mount + SSE| E1
    OP -->|on mount| E4
    OP -->|on mount| E5
    OP -->|10s poll| E6
    OP -->|on session change| E7
    OP -->|connect| E8

    subgraph ChildComponents["Child Components (own polling)"]
        MT2[MetricsTable<br/>5s poll]
        HA2[HubActivity<br/>SSE-triggered]
        TT2[TraceTimeline<br/>10s poll]
        TB2[ToolBreakdown<br/>10s poll]
    end

    DP --> MT2
    DP --> HA2
    OP --> TT2
    OP --> TB2

    MT2 -->|5s| E2
    HA2 -->|SSE| E3
    TT2 -->|10s| E6
    TB2 -->|10s| E7

    classDef panelStyle fill:#ec4899,stroke:#db2777,color:#fff
    classDef endpointStyle fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef childStyle fill:#22c55e,stroke:#16a34a,color:#fff

    class CP,DP,OP panelStyle
    class E1,E2,E3,E4,E5,E6,E7,E8 endpointStyle
    class MT2,HA2,TT2,TB2 childStyle
```

| Component | Endpoint | Cadence | Trigger |
|-----------|----------|---------|---------|
| All panels | `/api/sessions` | Event-driven | SSE Docker events |
| MetricsTable | `/api/metrics/containers` | 5s | Interval |
| HubActivity | `/api/hub/state` | Event-driven | SSE hub events |
| TraceTimeline | `/api/langfuse/sessions/*/traces` | 10s | Interval |
| ToolBreakdown | `/api/langfuse/sessions/*/summary` | 10s | Interval |
| ObservabilityPanel | `/api/langfuse/health`, `/api/qdrant/health` | Once | On mount |

## Panel Extension Pattern

New panels are added by creating a component and registering it in `panels.js`.

```mermaid
graph LR
    subgraph Registration["1. Register in panels.js"]
        PanelDef["{ id, label, icon }"]
    end

    subgraph Component["2. Create Component"]
        Svelte["NewPanel.svelte"]
    end

    subgraph Router["3. Add to App.svelte"]
        Cond["{#if currentPanel === 'new-panel'}"]
    end

    PanelDef --> Router
    Svelte --> Router

    classDef regStyle fill:#f97316,stroke:#ea580c,color:#fff
    classDef compStyle fill:#3b82f6,stroke:#2563eb,color:#fff

    class PanelDef regStyle
    class Svelte,Cond compStyle
```

**Steps:**

1. Add entry to `panels.js`:
   ```js
   { id: 'my-panel', label: 'My Panel', icon: '<svg>...</svg>' }
   ```
2. Create `MyPanel.svelte` in `dashboard/src/lib/`
3. Add conditional render in `App.svelte`:
   ```svelte
   {:else if currentPanel.value === 'my-panel'}
     <MyPanel />
   ```

## Reactive State

### Global stores (`stores.svelte.js`)

| Store | Type | Persistence | Description |
|-------|------|------------|-------------|
| `currentPanel` | `$state` | URL hash | Active panel ID, synced with `location.hash` |
| `sidebarCollapsed` | `$state` | localStorage | Sidebar collapsed state (220px ↔ 60px) |

### Notification system (`notifications.svelte.js`)

| Method | Duration | Description |
|--------|----------|-------------|
| `notifications.error(msg)` | 5s | Red toast |
| `notifications.success(msg)` | 3s | Green toast |
| `notifications.warning(msg)` | 4s | Amber toast |
| `notifications.info(msg)` | 3s | Blue toast |

### Panel-level state (representative)

**ContainersPanel:**

| State | Type | Description |
|-------|------|-------------|
| `sessions` | `$state` | All sessions from API |
| `showNewModal` | `$state` | New session dialog visibility |
| `expandedSessions` | `$state(Set)` | Sessions with open terminals |
| `activeProfile` | `$state` | Workspace profile filter |
| `filteredSessions` | `$derived` | Sessions filtered by profile |

**DashboardPanel:**

| State | Type | Description |
|-------|------|-------------|
| `sessions` | `$state` | All sessions |
| `activeSessions` | `$derived` | Filtered to active |
| `abortController` | `$state` | Fetch cancellation |

**ObservabilityPanel:**

| State | Type | Description |
|-------|------|-------------|
| `langfuseHealth` | `$state` | `{healthy, mode}` |
| `qdrantHealth` | `$state` | `{healthy, url}` |
| `summaries` | `$state` | Per-session LangFuse summaries |
| `selectedSession` | `$state` | Filter to single session |
| `totalTraces` | `$derived` | Sum of all trace counts |
| `totalErrors` | `$derived` | Sum of all error counts |

## SSE Connection

The `api.js` module provides `connectSSE(onEvent, onError, onReconnect)` with auto-reconnect using exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1 | 1s |
| 2 | 2s |
| 3 | 4s |
| 4 | 8s |
| 5 | 16s |
| 6+ | 30s (max) |

Backoff resets on successful message receipt.

## UX Patterns

**Dual-tap confirmation:** Stop and delete buttons require two clicks within 3 seconds. First click shows a warning state, second click executes. Timer expiration resets the button.

**Fetch cancellation:** Components use `AbortController` to cancel in-flight requests when new data is needed, preventing race conditions.

**Virtual scrolling:** TraceTimeline uses fixed item height (36px) with a buffer of 5 items. Only renders visible items for traces > 50.

**Modal focus management:** Modals save `document.activeElement` on mount, focus the first interactive element, and restore focus on unmount.

## Theme

Dark theme defined via CSS custom properties in `AppShell.svelte`:

| Variable | Value | Usage |
|----------|-------|-------|
| `--color-bg-primary` | `#0a0e1a` | Page background |
| `--color-bg-secondary` | `#111827` | Cards, tables |
| `--color-bg-tertiary` | `#1e293b` | Hover states |
| `--color-border-primary` | `#1e293b` | Borders |
| `--color-text-primary` | `#e2e8f0` | Body text |
| `--color-text-secondary` | `#94a3b8` | Muted text |
| `--color-accent` | `#f59e0b` | Brand amber |
| `--color-success` | `#10b981` | Active/healthy |
| `--color-error` | `#ef4444` | Errors |
| `--color-role-developer` | `#3b82f6` | Blue badge |
| `--color-role-researcher` | `#a855f7` | Purple badge |
| `--color-role-performer` | `#f97316` | Orange badge |
| `--color-llm-public` | `#ec4899` | Claude (pink) |
| `--color-llm-private` | `#22c55e` | Ollama (green) |
