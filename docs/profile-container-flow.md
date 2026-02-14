# Profile-Aware Container Creation

How workspace profiles, environment variables, and volume mounts flow from the host into sandboxed containers.

## End-to-End Flow

Each workspace profile is a self-contained directory with its own `.envrc`, `.env` template, `.ssh/`, `.gitconfig`, and a dedicated 1Password vault. The flow is identical for every profile — `cd` into it, direnv activates, and `/reflex:container create` provisions a container scoped to that profile.

```mermaid
graph TB
    subgraph Host["Host Machine"]
        subgraph Profile["Workspace Profile — ~/workspaces/profiles/{name}/"]
            PEnvRC[".envrc"]
            PDotEnv[".env<br/><i>AWS_CONFIG_FILE, AWS_SHARED_CREDENTIALS_FILE,<br/>AZURE_CONFIG_DIR, KUBECONFIG, ...</i>"]
            PSSH[".ssh/"]
            PGit[".gitconfig"]
        end

        Vault["1Password Vault<br/><i>workspace-{name}</i>"]

        CachedEnv["Volatile Cache<br/><i>$TMPDIR/sp-profiles/{name}/.env</i>"]

        SSOCache["~/.aws/sso/cache/<br/><i>shared — aws sso login always writes here</i>"]
    end

    subgraph Activation["Profile Activation — cd + direnv"]
        Direnv["direnv loads .envrc<br/><i>exports WORKSPACE_PROFILE={name},<br/>WORKSPACE_HOME=$PWD</i>"]
        Merge["Merge .env template +<br/>1Password secrets →<br/>volatile cache"]
        Load["dotenv_if_exists<br/><i>all vars available in shell</i>"]
    end

    subgraph Reflex["Reflex Plugin — /reflex:container create"]
        DetectProfile["Auto-detect from env<br/>WORKSPACE_PROFILE<br/>WORKSPACE_HOME"]
        APICall["POST /api/create<br/>{name, workspace_profile,<br/>workspace_home}"]
    end

    subgraph Brainbox["Brainbox API"]
        direction TB
        Provision["1. Provision<br/><i>resolve image, name, port</i>"]
        ResolveMounts["_resolve_profile_mounts()<br/><i>read profile env vars from cache<br/>to find credential dirs on host</i>"]
        ResolveEnv["_resolve_profile_env()<br/><i>read volatile cache for profile,<br/>filter host-only vars</i>"]
        Configure["2. Configure<br/><i>resolve secrets (1Password/files)</i>"]
        Start["3. Start<br/><i>inject env + secrets + auth</i>"]
    end

    subgraph Container["Docker Container — scoped to profile"]
        subgraph Mounts["Bind Mounts (rw) — all per-profile"]
            CtrAWS["/home/developer/.aws<br/><i>← from AWS_CONFIG_FILE parent</i>"]
            CtrAzure["/home/developer/.azure<br/><i>← from AZURE_CONFIG_DIR</i>"]
            CtrKube["/home/developer/.kube<br/><i>← from KUBECONFIG parent</i>"]
            CtrSSH["/home/developer/.ssh<br/><i>← $WORKSPACE_HOME/.ssh/</i>"]
            CtrGit["/home/developer/.gitconfig<br/><i>← $WORKSPACE_HOME/.gitconfig</i>"]
        end

        subgraph SSOOverlay["SSO Overlay Mount"]
            CtrSSO["/home/developer/.aws/sso/cache<br/><i>nested bind from real $HOME</i>"]
        end

        subgraph ProfileEnv["/run/profile/.env"]
            WP["WORKSPACE_PROFILE={name}"]
            WH["WORKSPACE_HOME=/home/developer"]
            Cloud["AWS_*, AZURE_*, KUBE_*,<br/>GH_TOKEN, JIRA_*, ..."]
        end

        subgraph Secrets["/run/secrets/ or ~/.env"]
            APIKeys["ANTHROPIC_AUTH_TOKEN<br/>LANGFUSE_*, etc."]
            AgentToken["agent-token"]
        end

        subgraph Auth["Claude Code Auth"]
            OAuthPatch[".claude.json<br/><i>oauthAccount from host</i>"]
            Onboarding["hasCompletedOnboarding: true<br/>bypassPermissions: true"]
        end

        BashRC[".bashrc / .env<br/><i>sources /run/profile/.env</i>"]
        ClaudeCode["Claude Code Session"]
    end

    %% Profile activation
    PEnvRC --> Direnv
    PDotEnv --> |"template"| CachedEnv
    Vault --> |"secrets"| CachedEnv
    Direnv --> Merge
    Merge --> Load

    %% Trigger container creation
    Load --> DetectProfile
    DetectProfile --> |"reads $WORKSPACE_PROFILE,<br/>$WORKSPACE_HOME"| APICall

    %% API processing
    APICall --> Provision
    Provision --> ResolveMounts
    Provision --> ResolveEnv
    ResolveMounts --> Configure
    ResolveEnv --> Configure
    Configure --> Start

    %% Per-profile mounts from profile directory
    PSSH --> CtrSSH
    PGit --> CtrGit

    %% AWS, Azure, Kube resolved from profile env vars in volatile cache
    CachedEnv --> |"AWS_CONFIG_FILE,<br/>AWS_SHARED_CREDENTIALS_FILE<br/>→ parent dir"| CtrAWS
    CachedEnv --> |"AZURE_CONFIG_DIR"| CtrAzure
    CachedEnv --> |"KUBECONFIG<br/>→ parent dir"| CtrKube

    %% SSO cache is the only shared mount
    SSOCache --> |"cross-profile overlay"| CtrSSO

    %% Env injection
    CachedEnv --> |"filtered + identity prepended"| ProfileEnv
    Start --> |"write /run/profile/.env,<br/>patch .bashrc"| BashRC
    BashRC --> |"set -a && source"| ClaudeCode
    Secrets --> ClaudeCode

    classDef profile fill:#4A90D9,stroke:#2C5F8A,color:#fff
    classDef vault fill:#F5A623,stroke:#D48B1A,color:#fff
    classDef cache fill:#9B59B6,stroke:#7D3C98,color:#fff
    classDef creds fill:#708090,stroke:#556B7F,color:#fff
    classDef activate fill:#2ECC71,stroke:#27AE60,color:#fff
    classDef reflex fill:#7B68EE,stroke:#5B4ACE,color:#fff
    classDef brainbox fill:#E8913A,stroke:#C67A2E,color:#fff
    classDef mount fill:#50C878,stroke:#3AA35E,color:#fff
    classDef env fill:#20B2AA,stroke:#178F87,color:#fff
    classDef secret fill:#E74C3C,stroke:#C0392B,color:#fff
    classDef auth fill:#3498DB,stroke:#2980B9,color:#fff

    class PEnvRC,PDotEnv,PSSH,PGit profile
    class Vault vault
    class CachedEnv cache
    class SSOCache creds
    class Direnv,Merge,Load activate
    class DetectProfile,APICall reflex
    class Provision,ResolveMounts,ResolveEnv,Configure,Start brainbox
    class CtrAWS,CtrAzure,CtrKube,CtrSSH,CtrGit,CtrSSO mount
    class WP,WH,Cloud,BashRC env
    class APIKeys,AgentToken secret
    class OAuthPatch,Onboarding,ClaudeCode auth
```

## Profile Mount Resolution

All credential directories are resolved from the **active profile's environment variables** (read from the volatile cache). The API never uses its own process env vars or `$HOME` fallbacks for another profile's credentials. Only the SSO token cache is shared across profiles (it lives under the real `$HOME`).

```mermaid
flowchart LR
    subgraph Input
        VC["Read profile's<br/>volatile cache .env"]
    end

    VC --> Parse["Parse env vars:<br/>AWS_CONFIG_FILE,<br/>AWS_SHARED_CREDENTIALS_FILE,<br/>AZURE_CONFIG_DIR,<br/>KUBECONFIG, ..."]

    Parse --> Resolve

    subgraph Resolve["For each mount type"]
        Check["ProfileSettings<br/>enabled?"]
        Check -->|No| Skip["Skip"]
        Check -->|Yes| Find["Resolve host path<br/>from profile env var"]
        Find -->|exists| Add["Add bind mount<br/>host → container (rw)"]
        Find -->|missing| Fallback["Try fallback:<br/>workspace_home or $HOME"]
        Fallback -->|exists| Add
        Fallback -->|missing| Skip
    end

    subgraph SSO["SSO Overlay (always)"]
        RealHome["~/.aws/sso/cache/"] --> Overlay["/home/developer/.aws/sso/cache"]
    end
```

## Mount Matrix

All env vars are read from the profile's volatile cache, not the API host's own environment.

| Mount | Setting | Profile Env Var | Resolve | Fallback | Container Target | Default |
|-------|---------|----------------|---------|----------|-----------------|---------|
| AWS | `mount_aws` | `AWS_CONFIG_FILE`<br/>`AWS_SHARED_CREDENTIALS_FILE` | parent dir | `$WORKSPACE_HOME/.aws/` | `/home/developer/.aws` | on |
| Azure | `mount_azure` | `AZURE_CONFIG_DIR` | direct | `$WORKSPACE_HOME/.azure/` | `/home/developer/.azure` | on |
| Kube | `mount_kube` | `KUBECONFIG` | parent dir | `$WORKSPACE_HOME/.kube/` | `/home/developer/.kube` | on |
| SSH | `mount_ssh` | — | — | `$WORKSPACE_HOME/.ssh/` | `/home/developer/.ssh` | on |
| Git | `mount_gitconfig` | `GIT_CONFIG_GLOBAL` | direct (file) | `$WORKSPACE_HOME/.gitconfig` | `/home/developer/.gitconfig` | on |
| GCloud | `mount_gcloud` | `CLOUDSDK_CONFIG` | direct | `$WORKSPACE_HOME/.gcloud/` | `/home/developer/.gcloud` | off |
| Terraform | `mount_terraform` | `TF_CLI_CONFIG_FILE` | parent dir | `$WORKSPACE_HOME/.terraform.d/` | `/home/developer/.terraform.d` | off |

**SSO overlay**: `~/.aws/sso/cache/` from the real `$HOME` is always overlaid at `/home/developer/.aws/sso/cache/` when AWS is mounted. This is the only cross-profile shared mount — `aws sso login` always writes tokens to the real home regardless of which profile is active.

## Environment Variable Flow

```mermaid
sequenceDiagram
    participant U as User
    participant D as direnv (.envrc)
    participant OP as 1Password
    participant VC as Volatile Cache<br/>$TMPDIR/sp-profiles/{profile}/.env
    participant BB as Brainbox API
    participant C as Container

    Note over U: cd ~/workspaces/profiles/{any-profile}
    U->>D: direnv triggers .envrc
    D->>D: export WORKSPACE_PROFILE={profile}
    D->>D: export WORKSPACE_HOME=$PWD

    alt First load (no cache for this profile)
        D->>VC: cp .env (profile's template)
        D->>OP: op item list --vault workspace-{profile}
        OP-->>D: item IDs
        D->>OP: op item get {id} --format json
        OP-->>D: KEY=VALUE pairs
        D->>VC: Append secrets → $TMPDIR/sp-profiles/{profile}/.env
    end

    D->>D: dotenv_if_exists $cache/.env
    Note over D: Shell now has all profile vars

    Note over BB: /reflex:container create
    BB->>BB: Read WORKSPACE_PROFILE + WORKSPACE_HOME from caller env
    BB->>VC: Read $TMPDIR/sp-profiles/{profile}/.env
    BB->>BB: Filter _HOST_ONLY_VARS<br/>(HOME, PATH, SSH_AUTH_SOCK,<br/>CLAUDE_CONFIG_DIR, ...)
    BB->>BB: Prepend WORKSPACE_PROFILE={profile}<br/>WORKSPACE_HOME=/home/developer
    BB->>BB: Parse profile env vars from cache<br/>(AWS_CONFIG_FILE, AZURE_CONFIG_DIR, KUBECONFIG, ...)
    BB->>BB: Resolve mount paths from profile env vars<br/>+ workspace_home for .ssh/, .gitconfig
    BB->>C: Create container with per-profile bind mounts<br/>+ SSO overlay from real $HOME
    BB->>C: Write /run/profile/.env
    BB->>C: Patch .bashrc + .env to source it
    C->>C: set -a && . /run/profile/.env && set +a
    Note over C: Container has this profile's<br/>env vars, credentials, and identity
```

## Host-Only Variables (Filtered Out)

These variables are stripped when forwarding the profile env into containers because they are host-specific or would conflict with the container's own configuration:

| Variable | Reason |
|----------|--------|
| `HOME`, `USER`, `LOGNAME` | Container has its own user (`developer`) |
| `PATH`, `PWD`, `OLDPWD`, `SHLVL` | Container has its own filesystem |
| `SSH_AUTH_SOCK`, `GIT_SSH_COMMAND` | Host socket paths don't exist in container |
| `TMPDIR`, `SHELL`, `TERM_PROGRAM` | Host-specific runtime |
| `CLAUDE_CONFIG_DIR`, `GEMINI_CONFIG_DIR` | Container has build-time defaults |
| `XDG_CONFIG_HOME` | Would override container config paths |
