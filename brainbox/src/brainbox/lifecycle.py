"""Brainbox lifecycle: provision → configure → start → monitor → recycle.

All Docker operations use the Docker SDK and are wrapped with run_in_executor
so they never block the async event loop.
"""

from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import docker
from docker.errors import NotFound

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
                        f"echo '{_shell_escape(value)}' > /run/secrets/{name} && chmod 400 /run/secrets/{name}",
                    ],
                )
            except Exception as exc:
                slog.warning(
                    "container.secret_write_failed", metadata={"secret": name, "reason": str(exc)}
                )
    else:
        # Legacy: write .env file
        try:
            await _run(
                container.exec_run,
                [
                    "sh",
                    "-c",
                    "rm -f /home/developer/.env && touch /home/developer/.env && chmod 600 /home/developer/.env",
                ],
            )
            if ctx.env_content:
                for line in ctx.env_content.split("\n"):
                    if line:
                        await _run(
                            container.exec_run,
                            ["sh", "-c", f"echo '{_shell_escape(line)}' >> /home/developer/.env"],
                        )
        except Exception as exc:
            slog.warning("container.env_write_failed", metadata={"reason": str(exc)})

        # Write agent-token file
        if "agent-token" in ctx.secrets:
            try:
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        f"echo '{_shell_escape(ctx.secrets['agent-token'])}' > /home/developer/.agent-token && chmod 400 /home/developer/.agent-token",
                    ],
                )
            except Exception as exc:
                slog.warning("container.token_write_failed", metadata={"reason": str(exc)})

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


def _shell_escape(s: str) -> str:
    return s.replace("'", "'\\''")


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
