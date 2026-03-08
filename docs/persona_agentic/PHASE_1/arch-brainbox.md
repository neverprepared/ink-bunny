# Container Lifecycle

Every agent container follows a managed lifecycle. No container runs unbounded.

```mermaid
graph LR
    Provision[Provision<br/>Pull + Verify Image]
    Configure[Configure<br/>Inject Secrets<br/>Apply Hardening]
    Start[Start<br/>Launch Agent]
    Monitor[Monitor<br/>Health Checks<br/>Resource Tracking]
    Recycle[Recycle<br/>Teardown<br/>Scrub State]

    Provision --> Configure --> Start --> Monitor
    Monitor -->|unhealthy / complete / timeout| Recycle
    Recycle -->|restart policy| Provision
```

## Phases

| Phase | What Happens |
|---|---|
| **Provision** | Pull agent image, verify signature (cosign), allocate resources from Docker |
| **Configure** | Write secrets to tmpfs via [[arch-secrets-management|1Password + direnv]], apply hardening flags |
| **Start** | Launch the agent process inside the container |
| **Monitor** | Continuous health checks, resource usage tracking, heartbeat validation |
| **Recycle** | Teardown on completion, failure, or timeout — scrub ephemeral state, reclaim resources |

## Image Verification

```mermaid
graph LR
    CI[CI Workflow<br/>build + push]
    Sign[cosign sign<br/>keyless / GitHub OIDC]
    Registry[(Container<br/>Registry)]
    Cosign[cosign verify<br/>keyless or key-based]
    Provision[Provision<br/>Container]

    CI --> Sign --> Registry
    Registry --> Cosign
    Cosign -->|"valid signature"| Provision
    Cosign -.->|"unsigned / invalid"| Reject([Reject])

    style Reject stroke:#f00,stroke-width:2px
```

**CI signing**: The Docker workflow signs all images (base + role variants) using Sigstore keyless cosign with GitHub OIDC identity. No key pair to manage — signatures are cryptographically tied to the GitHub Actions workflow via Fulcio certificates and recorded in the Rekor transparency log.

**Runtime verification**: Brainbox verifies image signatures during the Provision phase. Two strategies are supported:

| Strategy | Config | CLI flags |
|---|---|---|
| **Keyless** (preferred) | `CL_COSIGN__CERTIFICATE_IDENTITY` + `CL_COSIGN__OIDC_ISSUER` | `--certificate-identity-regexp` + `--certificate-oidc-issuer` |
| **Key-based** (fallback) | `CL_COSIGN__KEY` (path to PEM public key) | `--key` |

When both are configured, keyless takes precedence. The `CL_COSIGN__MODE` setting controls behavior:

| Mode | Behavior |
|---|---|
| `off` | Skip verification entirely |
| `warn` (default) | Log warning on failure, continue provisioning |
| `enforce` | Block provisioning on verification failure |

| Requirement | Phase 1 | Later Phases |
|---|---|---|
| **cosign signature** | Required | Required |
| **Vulnerability scan** | Not required | Required (reject critical CVEs) |
| **Base image** | Dev images with debugging tools permitted | Distroless/scratch only |
| **Shells / network tools** | Permitted (aids debugging) | Removed (reduces attack surface) |

## Container Hardening

Applied at the Configure phase to every container.

```mermaid
graph LR
    subgraph Hardening["Basic Hardening"]
        Seccomp[seccomp<br/>default profile]
        Caps[Drop Dangerous<br/>Capabilities]
        RootFS[Read-Only<br/>Root FS]
        User[Non-Root<br/>User]
        Privesc[No Privilege<br/>Escalation]
    end

    subgraph Writable["Writable Mounts (tmpfs)"]
        Workspace["/workspace<br/>agent working data"]
        Tmp["/tmp<br/>scratch space"]
        Secrets["/run/secrets<br/>secret files, mode 0400"]
    end
```

| Control | Setting | Purpose |
|---|---|---|
| **seccomp** | Docker default profile | Blocks most dangerous syscalls out of the box |
| **Capabilities** | Drop NET_RAW, SYS_ADMIN, MKNOD, SYS_CHROOT, NET_ADMIN | Removes ARP spoofing, mount manipulation, device creation |
| **Read-only rootfs** | `readOnlyRootFilesystem: true` | Prevents modification of container binaries |
| **Non-root user** | `runAsNonRoot: true`, `runAsUser: 65534` | Limits host impact on container escape |
| **No privilege escalation** | `--security-opt=no-new-privileges:true` | Blocks setuid/setgid escalation |
| **Secrets delivery** | File-based via tmpfs at `/run/secrets/<name>`, mode 0400 | Eliminates `/proc/*/environ` exposure |

### Docker Equivalent

```bash
docker run \
  --cap-drop NET_RAW --cap-drop SYS_ADMIN --cap-drop MKNOD \
  --cap-drop SYS_CHROOT --cap-drop NET_ADMIN \
  --security-opt no-new-privileges:true \
  --read-only \
  --tmpfs /workspace:size=500M \
  --tmpfs /tmp:size=100M \
  --mount type=tmpfs,destination=/run/secrets,tmpfs-mode=0400 \
  --user 65534:65534 \
  agent-image:latest
```

## Enforcement Boundaries

| Boundary | Purpose |
|---|---|
| **Resource Limits** | CPU, memory, ephemeral storage caps per container |
| **Egress Rules** | Allowlisted outbound destinations only |
| **Mount Policy** | No host filesystem mounts, no Docker socket |
| **Timeouts** | Every container has a maximum TTL — no indefinite execution |

## Lifecycle Rules

- **Restart policy** determines whether a recycled container re-provisions or terminates. **Now implemented** with role-aware crash recovery: persistent roles (supervisor, merge-queue, pr-shepherd) auto-restart on failure; transient roles (worker, reviewer) clean up.
- **Orphan reaping**: monitor phase detects containers with no active task and recycles them
- **State is ephemeral**: container filesystem is destroyed on recycle — durable outputs go to [[arch-shared-state|Shared State]]
