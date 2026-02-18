"""Docker backend implementation for brainbox."""

from __future__ import annotations

import asyncio
import json
import shlex
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import docker
from docker.errors import NotFound

from ..log import get_logger
from ..models import SessionContext, SessionState

# Docker client singleton
_client: docker.DockerClient | None = None
_executor = ThreadPoolExecutor(max_workers=4)

log = get_logger()


def _docker() -> docker.DockerClient:
    """Get or create Docker client singleton."""
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a blocking Docker SDK function in the thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))


def _calc_cpu(stats: dict) -> float:
    """Calculate CPU percentage from docker stats."""
    cpu = stats.get("cpu_stats", {})
    precpu = stats.get("precpu_stats", {})

    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get("cpu_usage", {}).get(
        "total_usage", 0
    )
    sys_delta = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    n_cpus = cpu.get("online_cpus", 1)

    if sys_delta > 0 and cpu_delta >= 0:
        return (cpu_delta / sys_delta) * n_cpus * 100.0
    return 0.0


def _human_bytes(b: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(b) < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024  # type: ignore[assignment]
    return f"{b:.1f}TiB"


class DockerBackend:
    """Docker container backend for brainbox."""

    async def provision(
        self,
        ctx: SessionContext,
        *,
        image_or_template: str,
        volumes: dict[str, dict[str, str]],
        hardening_kwargs: dict[str, Any],
    ) -> SessionContext:
        """Create Docker container with specified image and volumes."""
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker()

        # Check image exists
        try:
            await _run(client.images.get, image_or_template)
        except Exception as exc:
            slog.error("container.provision_failed", metadata={"reason": str(exc)})
            raise

        # Remove existing container if present
        try:
            old = await _run(client.containers.get, ctx.container_name)
            await _run(old.remove, force=True)
        except NotFound:
            pass

        # Build create kwargs
        kwargs: dict[str, Any] = {
            "image": image_or_template,
            "name": ctx.container_name,
            "command": ["sleep", "infinity"],
            "ports": {"7681/tcp": ("127.0.0.1", ctx.port)},
            "labels": {
                "brainbox.managed": "true",
                "brainbox.role": ctx.role,
                "brainbox.llm_provider": ctx.llm_provider,
                "brainbox.llm_model": ctx.llm_model or "",
                "brainbox.workspace_profile": (ctx.workspace_profile or "").upper(),
            },
            "detach": True,
            "volumes": volumes,
        }

        # Apply hardening or legacy settings
        kwargs.update(hardening_kwargs)

        try:
            await _run(client.containers.create, **kwargs)
        except Exception as exc:
            slog.error("container.provision_failed", metadata={"reason": str(exc)})
            raise

        ctx.state = SessionState.CONFIGURING
        slog.info(
            "container.provisioned",
            metadata={
                "image": image_or_template,
                "role": ctx.role,
                "port": ctx.port,
                "hardened": ctx.hardened,
            },
        )
        return ctx

    async def configure(
        self,
        ctx: SessionContext,
        *,
        secrets: dict[str, str],
        env_content: str | None = None,
        oauth_account: dict[str, Any] | None = None,
        profile_env: str | None = None,
    ) -> SessionContext:
        """Write secrets and configuration to Docker container."""
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker()
        container = await _run(client.containers.get, ctx.container_name)

        # Start container temporarily if not running (needed for exec)
        if container.status != "running":
            await _run(container.start)

        if ctx.hardened:
            # Write each secret to /run/secrets
            for name, value in secrets.items():
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
                        "container.secret_write_failed",
                        metadata={"secret": name, "reason": str(exc)},
                    )
        else:
            # Legacy: write .env file
            try:
                # Create .env with secure permissions atomically
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        "rm -f /home/developer/.env && umask 077 && touch /home/developer/.env",
                    ],
                )
                if env_content:
                    for line in env_content.split("\n"):
                        if line:
                            await _run(
                                container.exec_run,
                                ["sh", "-c", f"echo {shlex.quote(line)} >> /home/developer/.env"],
                            )
            except Exception as exc:
                slog.error("container.env_write_failed", metadata={"reason": str(exc)})
                raise

            # Write agent-token file
            if "agent-token" in secrets:
                try:
                    await _run(
                        container.exec_run,
                        [
                            "sh",
                            "-c",
                            f"umask 077 && echo {shlex.quote(secrets['agent-token'])} > /home/developer/.agent-token && chmod 400 /home/developer/.agent-token",
                        ],
                    )
                except Exception as exc:
                    slog.error("container.token_write_failed", metadata={"reason": str(exc)})
                    raise

            # Pre-populate Claude Code onboarding + auth state
            claude_json_patch: dict[str, Any] = {
                "hasCompletedOnboarding": True,
                "bypassPermissionsModeAccepted": True,
            }
            if oauth_account:
                claude_json_patch["oauthAccount"] = oauth_account

            try:
                patch_json = json.dumps(claude_json_patch)
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        f'echo {shlex.quote(patch_json)} | python3 -c "'
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

        # Inject LANGFUSE_SESSION_ID
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

        ctx.state = SessionState.STARTING
        slog.info("container.configured", metadata={"hardened": ctx.hardened})
        return ctx

    async def start(self, ctx: SessionContext) -> SessionContext:
        """Start Docker container and launch ttyd terminal."""
        from ..lifecycle import _resolve_profile_env

        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker()

        container = await _run(client.containers.get, ctx.container_name)

        # Start if not already running
        if container.status != "running":
            await _run(container.start)

        # Launch ttyd + tmux (skip in hardened mode - ttyd is handled elsewhere)
        if not ctx.hardened:
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

        # Write profile env to /run/profile/.env (after start)
        profile_env = _resolve_profile_env(workspace_profile=ctx.workspace_profile)
        if profile_env:
            try:
                # Create /run/profile as root
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
                # Source from .bashrc and .env
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

        ctx.state = SessionState.RUNNING
        slog.info("container.started", metadata={"port": ctx.port})
        return ctx

    async def stop(self, ctx: SessionContext) -> SessionContext:
        """Stop Docker container."""
        client = _docker()
        try:
            container = await _run(client.containers.get, ctx.container_name)
            await _run(container.stop, timeout=5)
        except Exception:
            pass
        return ctx

    async def remove(self, ctx: SessionContext) -> SessionContext:
        """Remove Docker container."""
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker()

        try:
            container = await _run(client.containers.get, ctx.container_name)
            await _run(container.remove)
            slog.info("container.removed")
        except Exception:
            pass

        return ctx

    async def health_check(self, ctx: SessionContext) -> dict[str, Any]:
        """Check Docker container health and collect CPU/memory metrics."""
        client = _docker()

        try:
            container = await _run(client.containers.get, ctx.container_name)
            await _run(container.reload)

            is_running = container.attrs["State"]["Running"]

            if not is_running:
                return {
                    "backend": "docker",
                    "healthy": False,
                    "reason": "container not running",
                }

            # Get stats (non-streaming)
            stats = await _run(container.stats, stream=False)
            cpu_pct = _calc_cpu(stats)
            mem = stats.get("memory_stats", {})
            mem_usage = mem.get("usage", 0)
            mem_limit = mem.get("limit", 1)

            return {
                "backend": "docker",
                "healthy": True,
                "cpu_percent": round(cpu_pct, 2),
                "memory_usage": mem_usage,
                "memory_limit": mem_limit,
                "memory_usage_human": _human_bytes(mem_usage),
                "memory_limit_human": _human_bytes(mem_limit),
            }

        except NotFound:
            return {
                "backend": "docker",
                "healthy": False,
                "reason": "container not found",
            }
        except Exception as exc:
            return {
                "backend": "docker",
                "healthy": False,
                "reason": str(exc),
            }

    async def exec_command(
        self, ctx: SessionContext, command: list[str], **kwargs: Any
    ) -> tuple[int, bytes]:
        """Execute command in Docker container via docker exec."""
        client = _docker()
        container = await _run(client.containers.get, ctx.container_name)

        # Run exec_run with kwargs (detach, user, etc.)
        result = await _run(container.exec_run, command, **kwargs)

        # exec_run returns ExecResult with exit_code and output
        # Handle both detached (returns None) and attached modes
        if kwargs.get("detach"):
            return (0, b"")
        else:
            exit_code = result.exit_code if hasattr(result, "exit_code") else 0
            output = result.output if hasattr(result, "output") else b""
            return (exit_code, output)

    def get_sessions_info(self) -> list[dict[str, Any]]:
        """List all managed Docker containers."""
        sessions = []
        try:
            client = _docker()
            containers = client.containers.list(
                all=True, filters={"label": "brainbox.managed=true"}
            )

            for c in containers:
                name = c.name
                is_running = c.status == "running"
                port = None
                volume = "-"

                if is_running:
                    ports = c.attrs.get("NetworkSettings", {}).get("Ports") or {}
                    for bindings in ports.values():
                        if bindings:
                            for b in bindings:
                                hp = b.get("HostPort")
                                if hp:
                                    port = hp
                                    break

                # Get volume mounts
                mounts = c.attrs.get("Mounts", [])
                bind_mounts = [
                    f"{m['Source']}:{m['Destination']}"
                    for m in mounts
                    if m.get("Type") == "bind"
                    and not m["Destination"].endswith("/.claude/projects")
                ]
                if bind_mounts:
                    volume = ", ".join(bind_mounts)

                labels = c.labels or {}
                llm_provider = labels.get("brainbox.llm_provider", "claude")
                llm_model = labels.get("brainbox.llm_model", "")
                workspace_profile = labels.get("brainbox.workspace_profile", "")

                sessions.append(
                    {
                        "backend": "docker",
                        "name": name,
                        "port": port,
                        "url": f"http://localhost:{port}" if port else None,
                        "volume": volume,
                        "active": is_running,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                        "workspace_profile": workspace_profile,
                    }
                )

        except Exception as exc:
            log.error("docker.list_sessions_failed", metadata={"reason": str(exc)})

        return sessions
