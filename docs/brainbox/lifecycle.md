# Container Lifecycle & Backends

Brainbox manages sandboxed environments through a 5-phase pipeline: **provision → configure → start → monitor → recycle**. Two backends are supported — Docker containers and macOS UTM virtual machines — accessed through a common protocol.

## Session State Machine

Every session transitions through these states. Error recovery returns to the previous state or jumps to `RECYCLING`.

```mermaid
stateDiagram-v2
    [*] --> PROVISIONING: run_pipeline()
    PROVISIONING --> CONFIGURING: image pulled + cosign verified
    CONFIGURING --> STARTING: secrets injected
    STARTING --> RUNNING: container/VM started
    RUNNING --> MONITORING: health loop attached
    MONITORING --> RECYCLING: TTL expired / manual stop
    RECYCLING --> RECYCLED: container removed
    RECYCLED --> [*]

    PROVISIONING --> RECYCLING: provision failed
    CONFIGURING --> RECYCLING: secret injection failed
    STARTING --> RECYCLING: start failed
    MONITORING --> RECYCLING: health_failures >= 3
```

## Pipeline Sequence

`run_pipeline()` in `lifecycle.py` orchestrates the full lifecycle. Each phase delegates to the active backend.

```mermaid
sequenceDiagram
    participant API as api.py
    participant LC as lifecycle.py
    participant BE as Backend
    participant Docker as Docker/UTM

    API->>LC: run_pipeline(session_name, role, ...)

    rect rgb(34, 197, 94, 0.1)
        Note over LC: Phase 1: Provision
        LC->>LC: resolve role, prefix, port
        LC->>Docker: images.get(image_name)
        LC->>LC: _verify_cosign(image)
        LC->>LC: resolve volumes + profile mounts
        LC->>BE: backend.provision(ctx, image, volumes, hardening)
        BE->>Docker: containers.create(...)
    end

    rect rgb(59, 130, 246, 0.1)
        Note over LC: Phase 2: Configure
        LC->>LC: resolve_secrets() (1Password or files)
        LC->>LC: resolve_oauth_account()
        LC->>BE: backend.configure(ctx, secrets, oauth)
        BE->>Docker: exec_run(write secrets + .env)
    end

    rect rgb(168, 85, 247, 0.1)
        Note over LC: Phase 3: Start
        LC->>BE: backend.start(ctx)
        BE->>Docker: container.start()
        BE->>Docker: exec_run(launch ttyd)
    end

    rect rgb(107, 114, 128, 0.1)
        Note over LC: Phase 4: Monitor
        LC->>LC: start_monitoring(ctx)
        Note over LC: background loop every 30s
    end

    LC-->>API: SessionContext
```

## Backend Abstraction

Both backends implement the same interface. `create_backend(name)` returns the appropriate implementation.

```mermaid
graph LR
    LC[lifecycle.py] --> Factory[backends/__init__.py<br/>create_backend]
    Factory -->|"docker"| DB[DockerBackend<br/>Docker SDK]
    Factory -->|"utm"| UB[UTMBackend<br/>utmctl + SSH]

    DB --> Provision1[provision]
    DB --> Configure1[configure]
    DB --> Start1[start]
    DB --> Stop1[stop]
    DB --> Remove1[remove]
    DB --> Health1[health_check]
    DB --> Exec1[exec_command]
    DB --> Info1[get_sessions_info]

    UB --> Provision2[provision]
    UB --> Configure2[configure]
    UB --> Start2[start]
    UB --> Stop2[stop]
    UB --> Remove2[remove]
    UB --> Health2[health_check]
    UB --> Exec2[exec_command]
    UB --> Info2[get_sessions_info]

    classDef lcStyle fill:#22c55e,stroke:#16a34a,color:#fff
    classDef factoryStyle fill:#14b8a6,stroke:#0d9488,color:#fff
    classDef methodStyle fill:#1e293b,stroke:#334155,color:#e2e8f0

    class LC lcStyle
    class Factory,DB,UB factoryStyle
    class Provision1,Configure1,Start1,Stop1,Remove1,Health1,Exec1,Info1,Provision2,Configure2,Start2,Stop2,Remove2,Health2,Exec2,Info2 methodStyle
```

### Docker Backend

| Phase | Docker SDK Call | Details |
|-------|----------------|---------|
| provision | `containers.create()` | Image, name, `sleep infinity`, ports, labels, volumes, hardening |
| configure | `exec_run()` × N | Write `.env`, `.agent-token`, `.claude.json`, `settings.json`, profile env |
| start | `container.start()` + `exec_run(ttyd)` | Launch web terminal (skip in hardened mode) |
| stop | `container.stop(timeout=5)` | Graceful shutdown |
| remove | `container.remove()` | Cleanup |
| health_check | `container.reload()` + `stats()` | CPU %, memory usage/limit |
| exec_command | `container.exec_run(cmd)` | Arbitrary command execution |

**Labels applied:** `brainbox.managed=true`, `brainbox.role`, `brainbox.llm_provider`, `brainbox.llm_model`, `brainbox.workspace_profile`

**Port bindings:** Always expose `7681` (ttyd terminal) plus any custom ports from `ctx.ports`.

### UTM Backend

| Phase | Operation | Details |
|-------|-----------|---------|
| provision | Clone template `.utm`, edit `config.plist` | Set VM name, networking (bridged or port-forward), VirtioFS shares |
| configure | Boot VM, SSH inject secrets | Write `.env`, `.agent-token`, `.claude.json`; mount VirtioFS shares |
| start | `utmctl start` + wait for SSH | Bridged: discover IP via ARP; QEMU: use localhost + ssh_port |
| stop | `utmctl stop` | Stop VM |
| remove | `utmctl stop` + `shutil.rmtree()` | Remove VM package |
| health_check | `utmctl status` + SSH probe | VM state + SSH reachability |
| exec_command | SSH execute | Remote command via SSH |

**Networking modes:**
- **Apple VMs:** Bridged networking, IP discovered via ARP table scan
- **QEMU VMs:** Port forwarding (guest 22 → host ssh_port)

## Cosign Verification

Image signature verification runs during provision (Phase 1). The verification mode is controlled by `CL_COSIGN__MODE`.

```mermaid
flowchart TD
    Start([Provision Phase]) --> CheckMode{cosign mode?}
    CheckMode -->|off| Skip[Skip verification]
    CheckMode -->|warn / enforce| EvalStrategies[Evaluate both strategies]

    EvalStrategies --> CheckKeyless{cert_identity +<br/>oidc_issuer set?}
    EvalStrategies --> CheckKey{key path set?}

    CheckKeyless -->|yes| Keyless[verify_image_keyless<br/>Sigstore Fulcio + Rekor]
    CheckKeyless -->|no| Neither

    CheckKey -->|yes + key file exists| KeyBased[verify_image<br/>PEM public key]
    CheckKey -->|no| Neither

    Neither{neither<br/>configured?} -->|enforce| Fail1[Raise ValueError]
    Neither -->|warn| Skip

    Keyless --> Result{verified?}
    KeyBased --> Result

    Result -->|yes| Pass[Log verified, continue]
    Result -->|no| ModeCheck{mode?}

    ModeCheck -->|enforce| Fail2[Raise CosignVerificationError]
    ModeCheck -->|warn| Warn[Log warning, continue]

    classDef passStyle fill:#22c55e,stroke:#16a34a,color:#fff
    classDef failStyle fill:#ef4444,stroke:#dc2626,color:#fff
    classDef warnStyle fill:#f59e0b,stroke:#d97706,color:#fff
    classDef checkStyle fill:#3b82f6,stroke:#2563eb,color:#fff

    class Pass,Skip passStyle
    class Fail1,Fail2 failStyle
    class Warn warnStyle
    class CheckMode,CheckKeyless,CheckKey,Neither,Result,ModeCheck checkStyle
```

**Verification strategies:**

| Strategy | Config | Mechanism |
|----------|--------|-----------|
| Keyless (preferred) | `CL_COSIGN__CERTIFICATE_IDENTITY` + `CL_COSIGN__OIDC_ISSUER` | Sigstore Fulcio/Rekor transparency log |
| Key-based (fallback) | `CL_COSIGN__KEY` (path to PEM) | Local public key verification |

## Volume Mount Resolution

Volumes are assembled from three sources during provision.

```mermaid
graph TB
    subgraph Sources["Volume Sources"]
        SD[Session Data Dir<br/>~/.config/developer/sessions/NAME]
        UV[User Volumes<br/>-v host:container:mode]
        PM[Profile Mounts<br/>credentials + config]
    end

    SD -->|"bind: /home/developer/.claude/projects"| Volumes
    UV -->|parsed from volume_mounts list| Volumes
    PM -->|resolved via env vars + fallback dirs| Volumes

    Volumes[Combined Volume Dict] --> Backend[Backend.provision]

    subgraph ProfileMounts["Profile Mount Resolution"]
        direction TB
        AWS[AWS<br/>AWS_CONFIG_FILE → ~/.aws]
        Azure[Azure<br/>AZURE_CONFIG_DIR → ~/.azure]
        Kube[Kube<br/>KUBECONFIG → ~/.kube]
        SSH[SSH<br/>$WORKSPACE_HOME/.ssh]
        Git[Gitconfig<br/>GIT_CONFIG_GLOBAL → ~/.gitconfig]
        GCloud[GCloud<br/>CLOUDSDK_CONFIG → ~/.gcloud]
        TF[Terraform<br/>TF_CLI_CONFIG_FILE → ~/.terraform.d]
    end

    PM --> ProfileMounts

    classDef srcStyle fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef mountStyle fill:#22c55e,stroke:#16a34a,color:#fff

    class SD,UV,PM srcStyle
    class AWS,Azure,Kube,SSH,Git,GCloud,TF mountStyle
```

### Profile mount specs

| Mount | Env Vars | Fallback | Container Path | Default |
|-------|----------|----------|---------------|---------|
| AWS | `AWS_CONFIG_FILE`, `AWS_SHARED_CREDENTIALS_FILE` | `~/.aws` | `/home/developer/.aws` | on |
| Azure | `AZURE_CONFIG_DIR` | `~/.azure` | `/home/developer/.azure` | on |
| Kube | `KUBECONFIG` | `~/.kube` | `/home/developer/.kube` | on |
| SSH | — | `$WORKSPACE_HOME/.ssh` | `/home/developer/.ssh` | on |
| Gitconfig (file) | `GIT_CONFIG_GLOBAL` | `$WORKSPACE_HOME/.gitconfig` | `/home/developer/.gitconfig` | on |
| GCloud | `CLOUDSDK_CONFIG` | `~/.gcloud` | `/home/developer/.gcloud` | off |
| Terraform | `TF_CLI_CONFIG_FILE` | `~/.terraform.d` | `/home/developer/.terraform.d` | off |

When `workspace_home` is provided with a `workspace_profile`, the volatile cache at `$TMPDIR/sp-profiles/{profile}/.env` is read to resolve env vars from the target profile.

**AWS SSO special case:** When `workspace_home` differs from the real home, an extra nested bind mount for `~/.aws/sso/cache/` is added so the container sees live SSO tokens.

## Hardening

Two modes controlled by `SessionContext.hardened`:

| Setting | Hardened | Legacy |
|---------|----------|--------|
| Root filesystem | Read-only | Read-write |
| IPC mode | Default | `host` |
| Capabilities dropped | `NET_RAW`, `SYS_ADMIN`, `MKNOD`, `SYS_CHROOT`, `NET_ADMIN` | None |
| `no-new-privileges` | Yes | No |
| Memory limit | `settings.resources.memory` (default 2g) | None |
| CPU limit | `settings.resources.cpus` (default 2) | None |
| tmpfs | `/workspace` (500M), `/tmp` (100M) | None |
| Secret mount | `/run/secrets` (tmpfs, 0o400, ro) | `.env` file |
| Profile env | `/run/profile` (tmpfs, 0o644, rw) | Inline in `.env` |
| Web terminal (ttyd) | Not launched — no web access | Launched on port 7681 |

**Note:** `LANGFUSE_SESSION_ID` is written to `~/.env` in both modes (for LangFuse trace correlation), even when other secrets go to `/run/secrets` in hardened mode.

## Configuration

All settings use the `CL_` env prefix with `__` as nested delimiter.

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| `role` | `CL_ROLE` | `developer` | Default container role |
| `image` | `CL_IMAGE` | `""` (resolves to `brainbox-{role}`) | Docker image name |
| `container_prefix` | `CL_CONTAINER_PREFIX` | `""` (resolves to `{role}-`) | Container name prefix |
| `ttl` | `CL_TTL` | `3600` | Session TTL in seconds |
| `api_port` | `CL_API_PORT` | `9999` | API listen port |
| `health_check_interval` | `CL_HEALTH_CHECK_INTERVAL` | `30` | Health loop interval (seconds) |
| `health_check_retries` | `CL_HEALTH_CHECK_RETRIES` | `3` | Failures before recycling |
| `cosign.mode` | `CL_COSIGN__MODE` | `warn` | `off` / `warn` / `enforce` |
| `resources.memory` | `CL_RESOURCES__MEMORY` | `2g` | Container memory limit |
| `resources.cpus` | `CL_RESOURCES__CPUS` | `2` | Container CPU limit |
| `profile.mount_aws` | `CL_PROFILE__MOUNT_AWS` | `true` | Mount AWS credentials |
| `profile.mount_ssh` | `CL_PROFILE__MOUNT_SSH` | `true` | Mount SSH directory |

See `config.py` for the full list of nested settings groups: `ResourceSettings`, `HardeningSettings`, `CosignSettings`, `ArtifactSettings`, `LangfuseSettings`, `QdrantSettings`, `ProfileSettings`, `OllamaSettings`, `UTMSettings`, `HubSettings`.
