"""Docker backend implementation for brainbox."""

from __future__ import annotations

import asyncio
import io
import json
import re
import shlex
import tarfile
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import docker
from docker.errors import NotFound

from ..log import get_logger
from ..models import SessionContext, SessionState

# Docker client singleton
_client: docker.DockerClient | None = None
_executor = ThreadPoolExecutor(max_workers=4)

log = get_logger()


def _extract_from_bundle(bundle_bytes: bytes, arcname: str) -> str | None:
    """Extract a single text file from a tar.gz bundle by archive name."""
    try:
        with tarfile.open(fileobj=io.BytesIO(bundle_bytes), mode="r:gz") as tf:
            member = tf.getmember(arcname)
            f = tf.extractfile(member)
            return f.read().decode("utf-8") if f else None
    except (KeyError, tarfile.TarError, OSError):
        return None


def _docker(docker_host: str | None = None) -> docker.DockerClient:
    """Get or create Docker client, optionally targeting a remote host."""
    global _client
    if docker_host:
        # Remote host: create a fresh client (not cached — could be per-session)
        return docker.DockerClient(base_url=docker_host)
    if _client is None:
        macos_sock = Path.home() / ".docker" / "run" / "docker.sock"
        if macos_sock.is_socket():
            _client = docker.DockerClient(base_url=f"unix://{macos_sock}")
        else:
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
        client = _docker(ctx.docker_host)

        # Always pull latest image before provision (ensures up-to-date; falls back to cache)
        try:
            await _run(client.images.pull, image_or_template)
            slog.info("container.image_pulled", metadata={"image": image_or_template})
        except Exception as pull_exc:
            slog.warning(
                "container.image_pull_failed",
                metadata={"image": image_or_template, "reason": str(pull_exc)},
            )
            # Fall back to locally cached image
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
        port_bindings: dict[str, tuple[str, int]] = {"7681/tcp": ("127.0.0.1", ctx.port)}

        # Add custom port mappings if specified
        if ctx.ports:
            for container_port, host_port in ctx.ports.items():
                port_bindings[f"{container_port}/tcp"] = ("127.0.0.1", host_port)

        kwargs: dict[str, Any] = {
            "image": image_or_template,
            "name": ctx.container_name,
            "command": ["sleep", "infinity"],
            "ports": port_bindings,
            "labels": {
                "brainbox.managed": "true",
                "brainbox.role": ctx.role,
                "brainbox.llm_provider": ctx.llm_provider,
                "brainbox.llm_model": ctx.llm_model or "",
                "brainbox.workspace_profile": (ctx.workspace_profile or "").upper(),
            },
            "environment": {
                "BRAINBOX_ROLE": ctx.role,
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
        client = _docker(ctx.docker_host)
        container = await _run(client.containers.get, ctx.container_name)

        # Start container temporarily if not running (needed for exec)
        if container.status != "running":
            await _run(container.start)

        if ctx.hardened:
            # Write each secret to /run/secrets
            for name, value in secrets.items():
                # Validate secret name — only allow safe characters
                if not re.match(r"^[A-Za-z0-9_.-]+$", name):
                    slog.warning(
                        "container.secret_name_rejected",
                        metadata={"secret": name, "reason": "invalid characters"},
                    )
                    continue
                safe_name = shlex.quote(name)
                try:
                    await _run(
                        container.exec_run,
                        [
                            "sh",
                            "-c",
                            f"echo {shlex.quote(value)} > /run/secrets/{safe_name} && chmod 400 /run/secrets/{safe_name}",
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

        # Inject role prompt file for --append-system-prompt-file
        if ctx.role_prompt_file:
            try:
                from ..registry import get_role_prompt

                prompt_content = get_role_prompt(ctx.role)
                if prompt_content:
                    await _run(
                        container.exec_run,
                        [
                            "sh",
                            "-c",
                            f"mkdir -p /home/developer/.brainbox"
                            f" && echo {shlex.quote(prompt_content)} > /home/developer/.brainbox/role-prompt.md"
                            f" && chmod 644 /home/developer/.brainbox/role-prompt.md",
                        ],
                    )
                    # Configure Claude Code to use the role prompt
                    await _run(
                        container.exec_run,
                        [
                            "sh",
                            "-c",
                            'python3 -c "'
                            "import json, pathlib; "
                            "p = pathlib.Path('/home/developer/.claude/settings.json'); "
                            "d = json.loads(p.read_text()) if p.exists() else {}; "
                            "d['appendSystemPromptFiles'] = ['/home/developer/.brainbox/role-prompt.md']; "
                            "p.write_text(json.dumps(d, indent=2))"
                            '"',
                        ],
                    )
                    slog.info(
                        "container.role_prompt_injected",
                        metadata={"role": ctx.role},
                    )
            except Exception as exc:
                slog.warning(
                    "container.role_prompt_injection_failed",
                    metadata={"role": ctx.role, "reason": str(exc)},
                )

        # Inject task description + completion helper for hub-spawned workers
        if ctx.task_description:
            try:
                complete_script = (
                    "#!/bin/sh\n"
                    "# Call this when your task is done to mark it complete in the hub.\n"
                    "TOKEN=$(cat /home/developer/.agent-token 2>/dev/null)\n"
                    "HUB=$(cat /home/developer/.brainbox/hub-url.txt 2>/dev/null || echo 'http://host.docker.internal:9999')\n"
                    'RESULT="${1:-done}"\n'
                    'curl -sf -X POST "${HUB}/api/hub/messages" \\\n'
                    '  -H "Authorization: Bearer ${TOKEN}" \\\n'
                    '  -H "Content-Type: application/json" \\\n'
                    '  -d "{\\"payload\\": {\\"event\\": \\"task.completed\\", \\"result\\": \\"${RESULT}\\"}}" \\\n'
                    "  && echo 'Task marked complete.' || echo 'Warning: could not reach hub.'\n"
                )
                task_with_footer = (
                    ctx.task_description
                    + "\n\nWhen your task is fully complete (PR opened or final output delivered), "
                    'run this to notify the hub: ~/.brainbox/complete.sh "<brief result summary>"'
                )
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        f"mkdir -p /home/developer/.brainbox"
                        f" && echo {shlex.quote(task_with_footer)} > /home/developer/.brainbox/task.txt"
                        f" && chmod 644 /home/developer/.brainbox/task.txt"
                        f" && echo 'http://host.docker.internal:9999' > /home/developer/.brainbox/hub-url.txt"
                        f" && printf {shlex.quote(complete_script)} > /home/developer/.brainbox/complete.sh"
                        f" && chmod 755 /home/developer/.brainbox/complete.sh",
                    ],
                )
                slog.info(
                    "container.task_injected", metadata={"task_len": len(ctx.task_description)}
                )
            except Exception as exc:
                slog.warning("container.task_injection_failed", metadata={"reason": str(exc)})

        # Claude config is delivered via inject_config_bundle() before configure() runs —
        # no staging copy needed here. bypassPermissions is already forced in the bundle.

        ctx.state = SessionState.STARTING
        slog.info("container.configured", metadata={"hardened": ctx.hardened})
        return ctx

    async def start(self, ctx: SessionContext) -> SessionContext:
        """Start Docker container and launch ttyd terminal."""
        from ..lifecycle import _resolve_profile_env

        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker(ctx.docker_host)

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

            # For autonomous containers (ci-ratchet workers), also start the wrapper
            # directly so task injection fires without requiring a browser connection.
            # When someone later opens the web terminal, ttyd re-runs the wrapper which
            # detects the existing tmux session and simply attaches.
            if ctx.task_description:
                try:
                    await _run(
                        container.exec_run,
                        ["/home/developer/ttyd-wrapper.sh"],
                        detach=True,
                        user="developer",
                    )
                    slog.info("container.wrapper_autostarted")
                except Exception as exc:
                    slog.warning(
                        "container.wrapper_autostart_failed", metadata={"reason": str(exc)}
                    )

        # Write profile env to /run/profile/.env (after start)
        profile_env = _resolve_profile_env(
            workspace_profile=ctx.workspace_profile,
            workspace_home=ctx.workspace_home,
        )
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
        client = _docker(ctx.docker_host)
        try:
            container = await _run(client.containers.get, ctx.container_name)
            await _run(container.stop, timeout=5)
        except Exception:
            pass
        return ctx

    async def remove(self, ctx: SessionContext) -> SessionContext:
        """Remove Docker container."""
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker(ctx.docker_host)

        try:
            container = await _run(client.containers.get, ctx.container_name)
            await _run(container.remove)
            slog.info("container.removed")
        except Exception:
            pass

        return ctx

    async def health_check(self, ctx: SessionContext) -> dict[str, Any]:
        """Check Docker container health and collect CPU/memory metrics."""
        client = _docker(ctx.docker_host)

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
        client = _docker(ctx.docker_host)
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

    async def inject_config_bundle(self, ctx: SessionContext, bundle_bytes: bytes) -> None:
        """Inject translated ~/.claude config bundle into the container via put_archive.

        put_archive may silently fail to write files inside ~/.claude/ when
        ~/.claude/projects is a bind mount (overlayfs + bind mount conflict).
        settings.json is therefore also written explicitly via exec_run.
        """
        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker(ctx.docker_host)
        try:
            container = await _run(client.containers.get, ctx.container_name)
            # put_archive works on stopped containers.
            await _run(container.put_archive, "/home/developer", bundle_bytes)
            # Fix ownership — tar is assembled with host uid, container user = developer.
            # exec_run requires a running container; start it now if it hasn't been started
            # yet (inject_config_bundle runs before configure() in the provision pipeline).
            await _run(container.reload)
            if container.status != "running":
                await _run(container.start)
            await _run(
                container.exec_run,
                [
                    "sh",
                    "-c",
                    "chown -R developer:developer /home/developer/.claude 2>/dev/null || true",
                ],
                user="root",
            )

            # Explicitly write settings.json via exec_run — put_archive may fail to
            # write inside ~/.claude/ when ~/.claude/projects is a bind mount.
            settings_json = _extract_from_bundle(bundle_bytes, ".claude/settings.json")
            if settings_json:
                await _run(
                    container.exec_run,
                    [
                        "sh",
                        "-c",
                        f"echo {shlex.quote(settings_json)}"
                        " > /home/developer/.claude/settings.json",
                    ],
                )

                # Merge user mcpServers into .claude.json workspace project —
                # Claude Code reads MCP servers from .claude.json, not settings.json.
                user_mcps = json.loads(settings_json).get("mcpServers", {})
                if user_mcps:
                    mcp_json = json.dumps(user_mcps)
                    await _run(
                        container.exec_run,
                        [
                            "sh",
                            "-c",
                            f'echo {shlex.quote(mcp_json)} | python3 -c "'
                            "import json, pathlib, sys; "
                            "p = pathlib.Path('/home/developer/.claude.json'); "
                            "d = json.loads(p.read_text()) if p.exists() else {}; "
                            "u = json.load(sys.stdin); "
                            "ws = '/home/developer/workspace'; "
                            "d.setdefault('projects', {}).setdefault(ws, {}).setdefault('mcpServers', {}).update(u); "
                            "p.write_text(json.dumps(d, indent=2))"
                            '"',
                        ],
                    )

            slog.info("container.config_bundle_injected")
        except Exception as exc:
            slog.warning("container.config_bundle_inject_failed", metadata={"reason": str(exc)})

    async def inject_remote_credentials(self, ctx: SessionContext) -> None:
        """Set up credential proxies for remote Docker mode.

        - AWS: credential_process pointing to /api/credentials/aws-token
        - SSH: websocat relay connecting unix socket to WebSocket endpoint
        """
        from ..config import settings

        slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
        client = _docker(ctx.docker_host)
        try:
            container = await _run(client.containers.get, ctx.container_name)
        except Exception as exc:
            slog.warning(
                "container.remote_credentials_failed",
                metadata={"reason": str(exc)},
            )
            return

        hub_url = f"http://host.docker.internal:{settings.api_port}"

        # AWS credential_process — SDK calls this on token expiry for always-fresh creds
        aws_config = textwrap.dedent(f"""\
            [default]
            credential_process = sh -c 'curl -sf \\
              -H "Authorization: Bearer $(cat /home/developer/.agent-token 2>/dev/null)" \\
              {hub_url}/api/credentials/aws-token'
        """)
        try:
            await _run(
                container.exec_run,
                [
                    "sh",
                    "-c",
                    f"mkdir -p /home/developer/.aws"
                    f" && printf '%s' {shlex.quote(aws_config)} > /home/developer/.aws/config",
                ],
                user="developer",
            )
        except Exception as exc:
            slog.warning("container.aws_credential_process_failed", metadata={"reason": str(exc)})

        # SSH agent WebSocket relay — websocat proxies unix socket to brainbox API
        # The relay runs in background; SSH_AUTH_SOCK points to the local unix socket
        hub_host = "host.docker.internal"
        hub_port = settings.api_port
        ssh_setup = textwrap.dedent(f"""\
            TOKEN=$(cat /home/developer/.agent-token 2>/dev/null || echo "")
            nohup websocat -b unix-l:/tmp/ssh-agent.sock \\
              "ws://{hub_host}:{hub_port}/api/credentials/ssh-agent" \\
              --header "Authorization: Bearer $TOKEN" \\
              >/dev/null 2>&1 &
            echo 'export SSH_AUTH_SOCK=/tmp/ssh-agent.sock' >> /home/developer/.env
        """)
        try:
            await _run(
                container.exec_run,
                ["sh", "-c", ssh_setup],
                user="developer",
            )
        except Exception as exc:
            slog.warning("container.ssh_relay_failed", metadata={"reason": str(exc)})

        slog.info("container.remote_credentials_injected")

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
