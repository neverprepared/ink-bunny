"""Brainbox lifecycle: provision → configure → start → monitor → recycle.

All Docker operations use the Docker SDK and are wrapped with run_in_executor
so they never block the async event loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import docker
from docker.errors import NotFound

from pathlib import Path

from .config import settings
from .cosign import CosignVerificationError, verify_image, verify_image_keyless
from .hardening import get_hardening_kwargs, get_legacy_kwargs
from .log import get_logger
from .models import SessionContext, SessionState, Token

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_client: docker.DockerClient | None = None
_sessions: dict[str, SessionContext] = {}
_executor = ThreadPoolExecutor(max_workers=4)

log = get_logger()


def _docker() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a blocking function in the thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_dir(
    env_vars: list[str],
    fallback: Path,
    *,
    use_parent: bool = False,
    env_override: dict[str, str] | None = None,
) -> Path | None:
    """Find a host directory from env vars or a fallback path.

    When *use_parent* is True the env var value is treated as a file path and
    its parent directory is returned instead.

    When *env_override* is provided, look up variables there instead of
    ``os.environ`` (used for cross-profile cache lookups).
    """
    env_source = env_override if env_override is not None else os.environ
    for var in env_vars:
        val = env_source.get(var)
        if val:
            candidate = Path(val).parent if use_parent else Path(val)
            if candidate.is_dir():
                return candidate
    if fallback.is_dir():
        return fallback
    return None


def _read_cache_vars(
    workspace_profile: str,
    workspace_home: str,
) -> dict[str, str]:
    """Read the volatile cache for a profile and return resolved env vars.

    Expands ``$WORKSPACE_HOME`` references to the provided host path
    and strips surrounding quotes from values.
    """
    tmpdir = os.environ.get("TMPDIR", "/tmp")
    cache_env = Path(tmpdir) / "sp-profiles" / workspace_profile / ".env"
    if not cache_env.is_file():
        return {}

    result: dict[str, str] = {}
    for raw_line in cache_env.read_text().splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:]
        name, _, value = stripped.partition("=")
        name = name.strip()
        value = value.strip()
        if not name or not value:
            continue
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        # Expand $WORKSPACE_HOME to actual host path
        value = value.replace("$WORKSPACE_HOME", workspace_home)
        result[name] = value
    return result


def _resolve_profile_mounts(
    workspace_profile: str | None = None,
    workspace_home: str | None = None,
) -> dict[str, dict[str, str]]:
    """Resolve profile credential / config directories to Docker volume mounts.

    When *workspace_home* is provided with a *workspace_profile*, the volatile
    cache at ``$TMPDIR/sp-profiles/{profile}/.env`` is read to resolve env vars
    from the target profile (expanding ``$WORKSPACE_HOME`` references).  When
    only *workspace_home* is provided (no profile), falls back to directory-based
    resolution.  When neither is provided, uses the current process environment.

    Returns a dict of host_path → {"bind": container_path, "mode": "rw"}.
    """
    mounts: dict[str, dict[str, str]] = {}
    p = settings.profile

    if workspace_home:
        ws_path = Path(workspace_home)
        home = ws_path
        if workspace_profile:
            cache_vars = _read_cache_vars(workspace_profile, workspace_home)
        else:
            cache_vars = {}
        use_env = bool(cache_vars)
    else:
        home = Path.home()
        ws = os.environ.get("WORKSPACE_HOME", "")
        ws_path = Path(ws) if ws else home
        cache_vars = {}
        use_env = True

    env_override = cache_vars if cache_vars else None

    mount_specs: list[tuple[bool, str, list[str], Path, bool]] = [
        # (enabled, name, env_vars, fallback, use_parent)
        (
            p.mount_aws,
            "aws",
            ["AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE"] if (use_env or cache_vars) else [],
            home / ".aws",
            True,
        ),
        (
            p.mount_azure,
            "azure",
            ["AZURE_CONFIG_DIR"] if (use_env or cache_vars) else [],
            home / ".azure",
            False,
        ),
        (
            p.mount_kube,
            "kube",
            ["KUBECONFIG"] if (use_env or cache_vars) else [],
            home / ".kube",
            True,
        ),
        (p.mount_ssh, "ssh", [], ws_path / ".ssh", False),
        (
            p.mount_gitconfig,
            "gitconfig",
            ["GIT_CONFIG_GLOBAL"] if (use_env or cache_vars) else [],
            ws_path / ".gitconfig",
            False,
        ),
        (
            p.mount_gcloud,
            "gcloud",
            ["CLOUDSDK_CONFIG"] if (use_env or cache_vars) else [],
            home / ".gcloud",
            False,
        ),
        (
            p.mount_terraform,
            "terraform",
            ["TF_CLI_CONFIG_FILE"] if (use_env or cache_vars) else [],
            home / ".terraform.d",
            True,
        ),
    ]

    container_targets = {
        "aws": "/home/developer/.aws",
        "azure": "/home/developer/.azure",
        "kube": "/home/developer/.kube",
        "ssh": "/home/developer/.ssh",
        "gitconfig": "/home/developer/.gitconfig",
        "gcloud": "/home/developer/.gcloud",
        "terraform": "/home/developer/.terraform.d",
    }

    for enabled, name, env_vars, fallback, use_parent in mount_specs:
        if not enabled:
            continue
        # gitconfig is a file mount, not a directory
        if name == "gitconfig":
            found = None
            env_source = env_override if env_override is not None else os.environ
            for var in env_vars:
                val = env_source.get(var)
                if val and Path(val).is_file():
                    found = Path(val)
                    break
            if found is None and fallback.is_file():
                found = fallback
            if found is not None:
                mounts[str(found)] = {"bind": container_targets[name], "mode": "rw"}
        else:
            host_dir = _resolve_dir(
                env_vars, fallback, use_parent=use_parent, env_override=env_override
            )
            if host_dir is not None:
                mounts[str(host_dir)] = {"bind": container_targets[name], "mode": "rw"}

    # When workspace_home differs from the real home, AWS SSO tokens live in
    # the real $HOME/.aws/sso/cache/ (aws sso login always writes there).
    # Add a nested bind mount so the container sees live tokens.
    if workspace_home and p.mount_aws:
        real_sso_cache = Path.home() / ".aws" / "sso" / "cache"
        if real_sso_cache.is_dir():
            mounts[str(real_sso_cache)] = {
                "bind": "/home/developer/.aws/sso/cache",
                "mode": "rw",
            }

    return mounts


# Vars that are host-specific and should not be forwarded into containers
_HOST_ONLY_VARS = frozenset(
    {
        "SSH_AUTH_SOCK",
        "GIT_SSH_COMMAND",
        "TMPDIR",
        "SHELL",
        "TERM_PROGRAM",
        "TERM_SESSION_ID",
        "HOME",
        "USER",
        "LOGNAME",
        "PATH",
        "PWD",
        "OLDPWD",
        "SHLVL",
        "XDG_CONFIG_HOME",
        # Container has its own config dirs; the host paths would conflict
        # with build-time defaults and cause Claude to miss settings.
        "CLAUDE_CONFIG_DIR",
        "GEMINI_CONFIG_DIR",
    }
)


def _resolve_profile_env(workspace_profile: str | None = None) -> str | None:
    """Read the volatile .env cache and return content suitable for a container.

    When *workspace_profile* is provided it is used instead of the API
    process's own WORKSPACE_PROFILE env var.  TMPDIR is shared across
    profiles on the same OS user so we always read it from os.environ.

    Returns the file content with host-only vars stripped and workspace identity
    vars prepended, or None if no cached .env exists.
    """
    profile = workspace_profile or os.environ.get("WORKSPACE_PROFILE", "")
    if not profile:
        return None

    tmpdir = os.environ.get("TMPDIR", "/tmp")
    cache_env = Path(tmpdir) / "sp-profiles" / profile / ".env"
    if not cache_env.is_file():
        return None

    lines: list[str] = []
    # Prepend workspace identity
    lines.append(f"WORKSPACE_PROFILE={profile}")
    lines.append("WORKSPACE_HOME=/home/developer")

    try:
        for raw_line in cache_env.read_text().splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Extract var name (handle KEY=VALUE and export KEY=VALUE)
            assignment = stripped
            if assignment.startswith("export "):
                assignment = assignment[7:]
            var_name = assignment.split("=", 1)[0].strip()
            if var_name in _HOST_ONLY_VARS:
                continue
            # Rewrite $WORKSPACE_HOME references (already handled by sourcing)
            lines.append(stripped)
    except OSError:
        return None

    return "\n".join(lines)


def _resolve_oauth_account() -> dict[str, str] | None:
    """Read oauthAccount from the host's .claude.json for container auth."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    claude_json = Path(config_dir) / ".claude.json"
    if not claude_json.is_file():
        return None
    try:
        data = json.loads(claude_json.read_text())
        acct = data.get("oauthAccount")
        if isinstance(acct, dict) and "accountUuid" in acct:
            return acct
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _find_available_port(start: int = 7681) -> int:
    """Scan running containers to find a free host port."""
    client = _docker()
    try:
        containers = client.containers.list()
        used: set[int] = set()
        for c in containers:
            ports = c.attrs.get("NetworkSettings", {}).get("Ports") or {}
            for bindings in ports.values():
                if bindings:
                    for b in bindings:
                        if b.get("HostPort"):
                            used.add(int(b["HostPort"]))
        port = start
        while port in used:
            port += 1
        return port
    except Exception:
        return start


# ---------------------------------------------------------------------------
# Cosign verification
# ---------------------------------------------------------------------------


async def _verify_cosign(image: Any, image_name: str, slog: Any) -> None:
    """Run cosign signature verification according to configured mode.

    Supports two verification strategies:
    - **Keyless** (preferred): uses ``certificate_identity`` + ``oidc_issuer``
      to verify against Sigstore Fulcio/Rekor transparency log.
    - **Key-based** (fallback): uses a local PEM public key file.
    """
    mode = settings.cosign.mode
    key_path = settings.cosign.key
    cert_identity = settings.cosign.certificate_identity
    oidc_issuer = settings.cosign.oidc_issuer

    if mode == "off":
        slog.info("container.cosign_skipped", metadata={"reason": "mode is off"})
        return

    # Determine verification strategy
    use_keyless = bool(cert_identity and oidc_issuer)
    use_key = bool(key_path)

    if not use_keyless and not use_key:
        if mode == "enforce":
            raise ValueError(
                "Cosign enforce mode requires either keyless config "
                "(CL_COSIGN__CERTIFICATE_IDENTITY + CL_COSIGN__OIDC_ISSUER) "
                "or a key (CL_COSIGN__KEY)"
            )
        slog.warning("container.cosign_skipped", metadata={"reason": "no verification configured"})
        return

    # Key-based: verify key file exists on disk
    if not use_keyless and use_key:
        if not os.path.isfile(key_path):
            if mode == "enforce":
                raise FileNotFoundError(f"Cosign public key not found: {key_path}")
            slog.warning(
                "container.cosign_skipped",
                metadata={"reason": f"key file not found: {key_path}"},
            )
            return

    # Resolve repo digests from the pulled image
    repo_digests: list[str] = image.attrs.get("RepoDigests", [])

    if not repo_digests:
        if mode == "enforce":
            raise ValueError(
                f"Image '{image_name}' has no repo digests — "
                "cannot verify a local-only image in enforce mode"
            )
        slog.info(
            "container.cosign_skipped",
            metadata={"reason": "local-only image (no repo digests)"},
        )
        return

    # Run cosign verify
    if use_keyless:
        result = await _run(
            verify_image_keyless, image_name, cert_identity, oidc_issuer, repo_digests
        )
    else:
        result = await _run(verify_image, image_name, key_path, repo_digests)

    if result.verified:
        slog.info(
            "container.cosign_verified",
            metadata={"image_ref": result.image_ref, "method": "keyless" if use_keyless else "key"},
        )
        return

    if mode == "enforce":
        raise CosignVerificationError(result)

    slog.warning(
        "container.cosign_failed",
        metadata={"image_ref": result.image_ref, "stderr": result.stderr},
    )


# ---------------------------------------------------------------------------
# Phase 1: Provision
# ---------------------------------------------------------------------------


async def provision(
    *,
    session_name: str = "default",
    role: str | None = None,
    port: int | None = None,
    hardened: bool = True,
    ttl: int | None = None,
    volume_mounts: list[str] | None = None,
    token: Token | None = None,
    llm_provider: str = "claude",
    llm_model: str | None = None,
    ollama_host: str | None = None,
    workspace_profile: str | None = None,
    workspace_home: str | None = None,
) -> SessionContext:
    resolved_role = role or settings.role
    resolved_prefix = settings.container_prefix or f"{resolved_role}-"
    resolved_image = settings.image or f"brainbox-{resolved_role}"
    container_name = f"{resolved_prefix}{session_name}"
    resolved_port = port or _find_available_port()
    resolved_ttl = ttl if ttl is not None else settings.ttl

    ctx = SessionContext(
        session_name=session_name,
        container_name=container_name,
        port=resolved_port,
        role=resolved_role,
        state=SessionState.PROVISIONING,
        created_at=_now_ms(),
        ttl=resolved_ttl,
        hardened=hardened,
        volume_mounts=volume_mounts or [],
        token=token,
        llm_provider=llm_provider,
        llm_model=llm_model,
        ollama_host=ollama_host,
        workspace_profile=workspace_profile,
        workspace_home=workspace_home,
    )

    slog = get_logger(session_name=session_name, container_name=container_name)
    client = _docker()

    # Check image exists
    try:
        image = await _run(client.images.get, resolved_image)
    except Exception as exc:
        slog.error("container.provision_failed", metadata={"reason": str(exc)})
        raise

    # Cosign image signature verification
    await _verify_cosign(image, resolved_image, slog)

    # Remove existing container if present
    try:
        old = await _run(client.containers.get, container_name)
        await _run(old.remove, force=True)
    except NotFound:
        pass

    # Build create kwargs
    kwargs: dict[str, Any] = {
        "image": resolved_image,
        "name": container_name,
        "command": ["sleep", "infinity"],
        "ports": {"7681/tcp": ("127.0.0.1", resolved_port)},
        "labels": {
            "brainbox.managed": "true",
            "brainbox.role": resolved_role,
            "brainbox.llm_provider": llm_provider,
            "brainbox.llm_model": llm_model or "",
            "brainbox.workspace_profile": (
                workspace_profile or os.environ.get("WORKSPACE_PROFILE", "")
            ).upper(),
        },
        "detach": True,
    }

    # Session data volume
    session_data_dir = settings.sessions_dir / session_name
    session_data_dir.mkdir(parents=True, exist_ok=True)
    volumes = {str(session_data_dir): {"bind": "/home/developer/.claude/projects", "mode": "rw"}}

    # User-specified volume mounts
    for vol in ctx.volume_mounts:
        parts = vol.split(":")
        if len(parts) >= 2:
            host_path = parts[0]
            container_path = parts[1]
            mode = parts[2] if len(parts) > 2 else "rw"
            volumes[host_path] = {"bind": container_path, "mode": mode}

    # Profile credential / config mounts (read-only)
    profile_mounts = _resolve_profile_mounts(
        workspace_profile=workspace_profile,
        workspace_home=workspace_home,
    )
    volumes.update(profile_mounts)
    # Track which mounts were actually resolved
    _bind_to_name = {
        "/home/developer/.aws": "aws",
        "/home/developer/.azure": "azure",
        "/home/developer/.kube": "kube",
        "/home/developer/.ssh": "ssh",
        "/home/developer/.gitconfig": "gitconfig",
        "/home/developer/.gcloud": "gcloud",
        "/home/developer/.terraform.d": "terraform",
    }
    for mount in profile_mounts.values():
        name = _bind_to_name.get(mount["bind"])
        if name:
            ctx.profile_mounts.add(name)

    kwargs["volumes"] = volumes

    # Hardening or legacy
    if hardened:
        kwargs.update(get_hardening_kwargs())
    else:
        kwargs.update(get_legacy_kwargs())

    try:
        await _run(client.containers.create, **kwargs)
    except Exception as exc:
        slog.error("container.provision_failed", metadata={"reason": str(exc)})
        raise

    ctx.state = SessionState.CONFIGURING
    _sessions[session_name] = ctx
    slog.info(
        "container.provisioned",
        metadata={
            "image": resolved_image,
            "role": resolved_role,
            "port": resolved_port,
            "hardened": hardened,
            "ttl": resolved_ttl,
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# Phase 2: Configure
# ---------------------------------------------------------------------------


async def configure(ctx_or_name: SessionContext | str) -> SessionContext:
    ctx = _resolve(ctx_or_name)
    ctx.state = SessionState.CONFIGURING

    # Resolve secrets (1Password when configured, plaintext files otherwise)
    from .secrets import resolve_secrets, has_op_integration

    resolved = resolve_secrets()

    # Inject Ollama env vars when provider is ollama
    if ctx.llm_provider == "ollama":
        resolved["ANTHROPIC_AUTH_TOKEN"] = "ollama"
        resolved["ANTHROPIC_API_KEY"] = ""
        resolved["ANTHROPIC_BASE_URL"] = ctx.ollama_host or settings.ollama.host
        resolved["CLAUDE_MODEL"] = ctx.llm_model or settings.ollama.model

    ctx.secrets.update(resolved)
    if not ctx.hardened:
        ctx.env_content = "\n".join(f"export {k}={v}" for k, v in resolved.items())

    # Agent token
    if ctx.token:
        ctx.secrets["agent-token"] = ctx.token.model_dump_json()
    else:
        ctx.secrets["agent-token"] = json.dumps(
            {
                "stub": True,
                "issued": _iso_now(),
                "note": "Use hub API to get a real token",
            }
        )

    ctx.state = SessionState.STARTING
    slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
    slog.info(
        "container.configured",
        metadata={
            "secretCount": len(ctx.secrets),
            "hardened": ctx.hardened,
            "source": "1password" if has_op_integration() else "files",
        },
    )
    return ctx


# ---------------------------------------------------------------------------
# Phase 3: Start
# ---------------------------------------------------------------------------


async def start(ctx_or_name: SessionContext | str) -> SessionContext:
    ctx = _resolve(ctx_or_name)
    ctx.state = SessionState.STARTING
    slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
    client = _docker()

    container = await _run(client.containers.get, ctx.container_name)
    await _run(container.start)

    if ctx.hardened:
        # Write each secret to /run/secrets
        for name, value in ctx.secrets.items():
            try:
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        f"echo {shlex.quote(value)} > /run/secrets/{name} && chmod 400 /run/secrets/{name}",
                    ],
                )
            except Exception as exc:
                slog.warning(
                    "container.secret_write_failed", metadata={"secret": name, "reason": str(exc)}
                )
    else:
        # Legacy: write .env file
        try:
            # Create .env with secure permissions atomically (no race condition)
            await _run(
                container.exec_run,
                [
                    "sh",
                    "-c",
                    "rm -f /home/developer/.env && umask 077 && touch /home/developer/.env",
                ],
            )
            if ctx.env_content:
                for line in ctx.env_content.split("\n"):
                    if line:
                        await _run(
                            container.exec_run,
                            ["sh", "-c", f"echo {shlex.quote(line)} >> /home/developer/.env"],
                        )
        except Exception as exc:
            slog.error("container.env_write_failed", metadata={"reason": str(exc)})
            raise

        # Write agent-token file with secure permissions atomically
        if "agent-token" in ctx.secrets:
            try:
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        f"umask 077 && echo {shlex.quote(ctx.secrets['agent-token'])} > /home/developer/.agent-token && chmod 400 /home/developer/.agent-token",
                    ],
                )
            except Exception as exc:
                slog.error("container.token_write_failed", metadata={"reason": str(exc)})
                raise

        # Pre-populate Claude Code onboarding + auth state so the first-run
        # wizard is skipped.  Must run before ttyd launches Claude Code.
        claude_json_patch: dict[str, Any] = {
            "hasCompletedOnboarding": True,
            "bypassPermissionsModeAccepted": True,
        }
        oauth_account = _resolve_oauth_account()
        if oauth_account:
            claude_json_patch["oauthAccount"] = oauth_account

        try:
            patch_json = json.dumps(claude_json_patch)
            await _run(
                container.exec_run,
                [
                    "sh",
                    "-c",
                    f"echo {shlex.quote(patch_json)} | python3 -c \""
                    "import json, pathlib, sys; "
                    "p = pathlib.Path('/home/developer/.claude.json'); "
                    "d = json.loads(p.read_text()) if p.exists() else {}; "
                    "d.update(json.load(sys.stdin)); "
                    "p.write_text(json.dumps(d, indent=2))"
                    '"',
                ],
            )
        except Exception as exc:
            slog.warning("container.onboarding_patch_failed", metadata={"reason": str(exc)})

        # Ensure bypassPermissions is set in settings.json
        try:
            await _run(
                container.exec_run,
                [
                    "sh",
                    "-c",
                    'python3 -c "'
                    "import json, pathlib; "
                    "p = pathlib.Path('/home/developer/.claude/settings.json'); "
                    "d = json.loads(p.read_text()) if p.exists() else {}; "
                    "d['bypassPermissions'] = True; "
                    "p.write_text(json.dumps(d, indent=2))"
                    '"',
                ],
            )
        except Exception as exc:
            slog.warning("container.settings_patch_failed", metadata={"reason": str(exc)})

        # Launch ttyd + tmux
        title = f"{ctx.role.capitalize()} - {ctx.session_name}"
        try:
            await _run(
                container.exec_run,
                [
                    "ttyd",
                    "-W",
                    "-t",
                    f"titleFixed={title}",
                    "-p",
                    "7681",
                    "/home/developer/ttyd-wrapper.sh",
                ],
                detach=True,
            )
        except Exception as exc:
            slog.warning("container.ttyd_start_failed", metadata={"reason": str(exc)})

    # Write profile env to /run/profile/.env (replaces .cloud_env)
    profile_env = _resolve_profile_env(workspace_profile=ctx.workspace_profile)
    if profile_env:
        try:
            # Create /run/profile as root (the dir is root-owned in legacy mode;
            # in hardened mode the tmpfs already exists so mkdir is a no-op)
            await _run(
                container.exec_run,
                ["sh", "-c", "mkdir -p /run/profile && chmod 777 /run/profile"],
                user="root",
            )
            await _run(
                container.exec_run,
                [
                    "sh",
                    "-c",
                    f"echo {shlex.quote(profile_env)} > /run/profile/.env"
                    " && chmod 644 /run/profile/.env",
                ],
            )
            # Source from .bashrc (interactive shells) AND append to
            # /home/developer/.env (BASH_ENV target used by tmux/non-interactive)
            for rc_file in ("/home/developer/.bashrc", "/home/developer/.env"):
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        f"grep -q /run/profile/.env {rc_file} 2>/dev/null"
                        f" || echo '[ -f /run/profile/.env ] && set -a && . /run/profile/.env && set +a' >> {rc_file}",
                    ],
                )
        except Exception as exc:
            slog.warning("container.profile_env_write_failed", metadata={"reason": str(exc)})

    # Inject LANGFUSE_SESSION_ID so traces map back to this container session
    try:
        langfuse_line = f"export LANGFUSE_SESSION_ID={ctx.session_name}"
        await _run(
            container.exec_run,
            [
                "sh",
                "-c",
                f"echo {shlex.quote(langfuse_line)} >> /home/developer/.env",
            ],
        )
    except Exception as exc:
        slog.warning("container.langfuse_session_id_failed", metadata={"reason": str(exc)})

    ctx.state = SessionState.RUNNING
    slog.info("container.started", metadata={"port": ctx.port, "hardened": ctx.hardened})
    return ctx


# ---------------------------------------------------------------------------
# Phase 4: Monitor (delegates to monitor module)
# ---------------------------------------------------------------------------


async def monitor(ctx_or_name: SessionContext | str) -> SessionContext:
    from .monitor import start_monitoring

    ctx = _resolve(ctx_or_name)
    start_monitoring(ctx)
    ctx.state = SessionState.MONITORING
    slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
    slog.info("container.monitoring", metadata={"ttl": ctx.ttl})
    return ctx


# ---------------------------------------------------------------------------
# Phase 5: Recycle
# ---------------------------------------------------------------------------


async def recycle(ctx_or_name: SessionContext | str, reason: str = "manual") -> SessionContext:
    from .monitor import stop_monitoring

    ctx = _resolve(ctx_or_name)
    ctx.state = SessionState.RECYCLING
    slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
    client = _docker()

    stop_monitoring(ctx.session_name)

    try:
        container = await _run(client.containers.get, ctx.container_name)
        await _run(container.stop, timeout=5)
    except Exception:
        pass

    try:
        container = await _run(client.containers.get, ctx.container_name)
        await _run(container.remove)
    except Exception:
        pass

    ctx.state = SessionState.RECYCLED
    _sessions.pop(ctx.session_name, None)
    slog.info("container.recycled", metadata={"reason": reason})
    return ctx


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


async def run_pipeline(
    *,
    session_name: str = "default",
    role: str | None = None,
    port: int | None = None,
    hardened: bool = True,
    ttl: int | None = None,
    volume_mounts: list[str] | None = None,
    token: Token | None = None,
    llm_provider: str = "claude",
    llm_model: str | None = None,
    ollama_host: str | None = None,
    workspace_profile: str | None = None,
    workspace_home: str | None = None,
) -> SessionContext:
    ctx = await provision(
        session_name=session_name,
        role=role,
        port=port,
        hardened=hardened,
        ttl=ttl,
        volume_mounts=volume_mounts,
        token=token,
        llm_provider=llm_provider,
        llm_model=llm_model,
        ollama_host=ollama_host,
        workspace_profile=workspace_profile,
        workspace_home=workspace_home,
    )
    await configure(ctx)
    await start(ctx)
    await monitor(ctx)
    return ctx


# ---------------------------------------------------------------------------
# Session lookup
# ---------------------------------------------------------------------------


def _resolve(ctx_or_name: SessionContext | str) -> SessionContext:
    if isinstance(ctx_or_name, str):
        ctx = _sessions.get(ctx_or_name)
        if not ctx:
            raise ValueError(f"Session '{ctx_or_name}' not found")
        return ctx
    return ctx_or_name


def get_session(session_name: str) -> SessionContext | None:
    return _sessions.get(session_name)


def list_sessions() -> list[SessionContext]:
    return list(_sessions.values())


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
