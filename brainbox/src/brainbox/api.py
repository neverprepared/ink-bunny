"""FastAPI application: hub API, session management, dashboard, and SSE."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import docker
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from datetime import datetime, timezone

from .config import settings
from .rate_limit import limiter, rate_limit_exceeded_handler
from .hub import init as hub_init, shutdown as hub_shutdown
from .backends.docker import _calc_cpu, _human_bytes
from .lifecycle import (
    _docker,
    provision,
    configure,
    recycle,
    run_pipeline,
    start as lifecycle_start,
    monitor as lifecycle_monitor,
)
from .validation import (
    validate_artifact_key,
    ValidationError,
)
from .log import get_logger, setup_logging
from .models import TaskCreate, Token
from .models_api import (
    CreateSessionRequest,
    DeleteSessionRequest,
    ExecSessionRequest,
    QuerySessionRequest,
    StartSessionRequest,
    StopSessionRequest,
)
from .registry import get_agent, list_agents, list_tokens, validate_token
from .router import (
    cancel_task,
    complete_task,
    get_task,
    list_tasks,
    on_event,
    submit_task,
)
from .artifacts import (
    ArtifactError,
    delete_artifact,
    download_artifact,
    health_check as artifact_health_check,
    list_artifacts,
    upload_artifact,
)
from .langfuse_client import (
    LangfuseError,
    health_check as langfuse_health_check,
    get_session_traces_summary,
    get_trace as langfuse_get_trace,
    list_traces as langfuse_list_traces,
)
from .messages import get_message_log, get_messages, route as route_message

log = get_logger()


# ---------------------------------------------------------------------------
# Audit logging helper
# ---------------------------------------------------------------------------


def _audit_log(
    request: Request,
    operation: str,
    session_name: str | None = None,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Log destructive operations with client metadata."""
    client_ip = get_remote_address(request) if hasattr(request, "client") else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    log.info(
        "audit.operation",
        metadata={
            "operation": operation,
            "session_name": session_name or "N/A",
            "client_ip": client_ip,
            "user_agent": user_agent,
            "success": success,
            "error": error,
        },
    )


# ---------------------------------------------------------------------------
# SSE client management
# ---------------------------------------------------------------------------

_sse_queues: set[asyncio.Queue] = set()


def _broadcast_sse(data: str) -> None:
    for q in list(_sse_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# Docker events watcher
# ---------------------------------------------------------------------------

_docker_events_task: asyncio.Task | None = None


async def _watch_docker_events() -> None:
    """Watch Docker events and broadcast to SSE clients."""
    loop = asyncio.get_running_loop()

    def _blocking_watch():
        """Run in thread — blocks on Docker event stream."""
        try:
            client = _docker()
            for event in client.events(filters={"label": "brainbox.managed=true"}, decode=True):
                action = event.get("Action", "")
                if action in ("create", "start", "stop", "die", "destroy"):
                    loop.call_soon_threadsafe(_broadcast_sse, action)
        except Exception:
            pass

    try:
        await loop.run_in_executor(None, _blocking_watch)
    except Exception:
        pass
    # Restart after a brief delay if the stream dies
    await asyncio.sleep(1)
    asyncio.ensure_future(_watch_docker_events())


# ---------------------------------------------------------------------------
# SPA static files
# ---------------------------------------------------------------------------

_dashboard_dist = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def _extract_token(request: Request) -> Token | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token_id = auth[7:].strip()
    return validate_token(token_id)


def require_token(request: Request) -> Token:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Bearer token")
    return token


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await hub_init()

    # Forward hub events to SSE
    on_event(
        lambda event, data: _broadcast_sse(
            json.dumps(
                {
                    "hub": True,
                    "event": event,
                    "data": data.model_dump() if hasattr(data, "model_dump") else data,
                }
            )
        )
    )

    # Start Docker events watcher
    global _docker_events_task
    _docker_events_task = asyncio.create_task(_watch_docker_events())

    log.info("api.started", metadata={"port": settings.api_port})
    yield

    if _docker_events_task:
        _docker_events_task.cancel()
    await hub_shutdown()


app = FastAPI(title="Brainbox", version="0.2.0", lifespan=lifespan)

# Add rate limiter state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Dashboard (session info helper used by API)
# ---------------------------------------------------------------------------


_ROLE_PREFIXES = ("developer-", "researcher-", "performer-")


def _extract_session_name(container_name: str) -> str:
    """Strip any known role prefix from a container name."""
    for prefix in _ROLE_PREFIXES:
        if container_name.startswith(prefix):
            return container_name[len(prefix) :]
    return container_name


def _extract_role(container: Any) -> str:
    """Get the role label from a container, defaulting to 'developer'."""
    labels = container.labels or {}
    return labels.get("brainbox.role", "developer")


def _get_sessions_info() -> list[dict[str, Any]]:
    """Get session info from all backends (Docker + UTM)."""
    from .backends import create_backend

    sessions = []

    # Get Docker sessions
    try:
        docker_backend = create_backend("docker")
        docker_sessions = docker_backend.get_sessions_info()
        for sess in docker_sessions:
            # Add legacy fields for backward compatibility
            sess["session_name"] = _extract_session_name(sess["name"])
            sess["role"] = sess.get("role", "developer")
        sessions.extend(docker_sessions)
    except Exception as exc:
        log.warning("docker.list_sessions_failed", metadata={"reason": str(exc)})

    # Get UTM sessions
    try:
        utm_backend = create_backend("utm")
        utm_sessions = utm_backend.get_sessions_info()
        sessions.extend(utm_sessions)
    except Exception as exc:
        log.warning("utm.list_sessions_failed", metadata={"reason": str(exc)})

    # Return sessions from all backends
    return sessions


def _get_sessions_info_legacy() -> list[dict[str, Any]]:
    """Legacy Docker-only session listing (deprecated)."""
    sessions = []
    try:
        client = _docker()
        containers = client.containers.list(all=True, filters={"label": "brainbox.managed=true"})

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
                if m.get("Type") == "bind" and not m["Destination"].endswith("/.claude/projects")
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
                    "session_name": _extract_session_name(name),
                    "role": _extract_role(c),
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
        log.warning("docker.list_sessions_failed", metadata={"reason": str(exc)})

    sessions.sort(key=lambda s: (not s["active"], s["name"]))
    return sessions


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------


@app.get("/api/events")
async def sse_events():
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_queues.add(queue)

    async def event_generator():
        try:
            yield {"data": "connected"}
            while True:
                data = await queue.get()
                yield {"data": data}
        except asyncio.CancelledError:
            pass
        finally:
            _sse_queues.discard(queue)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Session management routes (from dashboard/server.js)
# ---------------------------------------------------------------------------


@app.get("/api/sessions")
async def api_list_sessions():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_sessions_info)


@app.post("/api/stop")
@limiter.limit("10/minute")
async def api_stop_session(request: Request, body: StopSessionRequest):
    name = body.name
    session_name = _extract_session_name(name)
    try:
        await recycle(session_name, reason="dashboard_stop")
        _audit_log(request, "session.stop", session_name=session_name, success=True)
        return {"success": True}
    except Exception as exc:
        # Fallback to direct Docker stop
        log.warning(
            "session.recycle_failed",
            metadata={"session": session_name, "error": str(exc), "fallback": "direct_docker_stop"},
        )
        try:
            client = _docker()
            container = client.containers.get(name)
            container.stop(timeout=1)
            _audit_log(request, "session.stop", session_name=session_name, success=True)
            return {"success": True}
        except docker.errors.NotFound:
            _audit_log(
                request, "session.stop", session_name=session_name, success=False, error="not_found"
            )
            log.error("session.stop_failed.not_found", metadata={"container": name})
            raise HTTPException(status_code=404, detail=f"Container not found: {name}")
        except docker.errors.DockerException as docker_exc:
            _audit_log(
                request,
                "session.stop",
                session_name=session_name,
                success=False,
                error=str(docker_exc),
            )
            log.error(
                "session.stop_failed.docker_error",
                metadata={"container": name, "error": str(docker_exc)},
            )
            raise HTTPException(status_code=500, detail=f"Docker error: {docker_exc}")
        except Exception as fallback_exc:
            _audit_log(
                request,
                "session.stop",
                session_name=session_name,
                success=False,
                error=str(fallback_exc),
            )
            log.exception("session.stop_failed.unexpected")
            raise HTTPException(status_code=500, detail=f"Failed to stop session: {fallback_exc}")


@app.post("/api/delete")
@limiter.limit("10/minute")
async def api_delete_session(request: Request, body: DeleteSessionRequest):
    name = body.name
    session_name = _extract_session_name(name)
    try:
        await recycle(session_name, reason="dashboard_delete")
        _audit_log(request, "session.delete", session_name=session_name, success=True)
        return {"success": True}
    except Exception as exc:
        log.warning(
            "session.recycle_failed",
            metadata={
                "session": session_name,
                "error": str(exc),
                "fallback": "direct_docker_remove",
            },
        )
        try:
            client = _docker()
            container = client.containers.get(name)
            container.remove()
            _audit_log(request, "session.delete", session_name=session_name, success=True)
            return {"success": True}
        except docker.errors.NotFound:
            _audit_log(
                request,
                "session.delete",
                session_name=session_name,
                success=False,
                error="not_found",
            )
            log.error("session.delete_failed.not_found", metadata={"container": name})
            raise HTTPException(status_code=404, detail=f"Container not found: {name}")
        except docker.errors.DockerException as docker_exc:
            _audit_log(
                request,
                "session.delete",
                session_name=session_name,
                success=False,
                error=str(docker_exc),
            )
            log.error(
                "session.delete_failed.docker_error",
                metadata={"container": name, "error": str(docker_exc)},
            )
            raise HTTPException(status_code=500, detail=f"Docker error: {docker_exc}")
        except Exception as fallback_exc:
            _audit_log(
                request,
                "session.delete",
                session_name=session_name,
                success=False,
                error=str(fallback_exc),
            )
            log.exception("session.delete_failed.unexpected")
            raise HTTPException(status_code=500, detail=f"Failed to delete session: {fallback_exc}")


@app.post("/api/start")
@limiter.limit("10/minute")
async def api_start_session(request: Request, body: StartSessionRequest):
    name = body.name
    session_name = _extract_session_name(name)
    try:
        ctx = await provision(session_name=session_name, hardened=False)
        await configure(ctx)
        await lifecycle_start(ctx)
        await lifecycle_monitor(ctx)
        _audit_log(request, "session.start", session_name=session_name, success=True)
        return {"success": True, "url": f"http://localhost:{ctx.port}"}
    except Exception as exc:
        log.error(
            "session.start_failed.lifecycle", metadata={"session": session_name, "error": str(exc)}
        )
        # Fallback to direct Docker start
        try:
            client = _docker()
            container = client.containers.get(name)
            container.start()

            # Get port
            container.reload()
            ports = container.attrs.get("NetworkSettings", {}).get("Ports") or {}
            port = "7681"
            for bindings in ports.values():
                if bindings:
                    for b in bindings:
                        if b.get("HostPort"):
                            port = b["HostPort"]
                            break

            _audit_log(request, "session.start", session_name=session_name, success=True)
            return {"success": True, "url": f"http://localhost:{port}"}
        except docker.errors.NotFound:
            _audit_log(
                request,
                "session.start",
                session_name=session_name,
                success=False,
                error="not_found",
            )
            log.error("session.start_failed.not_found", metadata={"container": name})
            raise HTTPException(status_code=404, detail=f"Container not found: {name}")
        except docker.errors.DockerException as docker_exc:
            _audit_log(
                request,
                "session.start",
                session_name=session_name,
                success=False,
                error=str(docker_exc),
            )
            log.error(
                "session.start_failed.docker_error",
                metadata={"container": name, "error": str(docker_exc)},
            )
            raise HTTPException(status_code=500, detail=f"Docker error: {docker_exc}")
        except Exception as fallback_exc:
            _audit_log(
                request,
                "session.start",
                session_name=session_name,
                success=False,
                error=str(fallback_exc),
            )
            log.exception("session.start_failed.unexpected")
            raise HTTPException(status_code=500, detail=f"Failed to start session: {fallback_exc}")


@app.post("/api/create")
@limiter.limit("10/minute")
async def api_create_session(request: Request, body: CreateSessionRequest):
    try:
        ctx = await run_pipeline(
            session_name=body.name,
            role=body.role,
            hardened=False,
            volume_mounts=body.volumes,
            llm_provider=body.llm_provider,
            llm_model=body.llm_model,
            ollama_host=body.ollama_host,
            workspace_profile=body.workspace_profile,
            workspace_home=body.workspace_home,
            backend=body.backend,
            vm_template=body.vm_template,
            ports=body.ports,
        )
        _audit_log(request, "session.create", session_name=body.name, success=True)

        # Response format depends on backend
        if ctx.backend == "utm":
            return {
                "success": True,
                "backend": "utm",
                "ssh_port": ctx.ssh_port,
                "url": None,
            }
        else:
            return {
                "success": True,
                "backend": "docker",
                "url": f"http://localhost:{ctx.port}",
            }
    except Exception as exc:
        _audit_log(request, "session.create", session_name=body.name, success=False, error=str(exc))
        log.error("session.create.failed", metadata={"error": str(exc)})
        return {"success": False, "error": str(exc)}


@app.post("/api/sessions/{name}/exec")
@limiter.limit("10/minute")
async def api_exec_session(request: Request, name: str, body: ExecSessionRequest):
    """Execute a command inside a running container."""
    prefix = settings.resolved_prefix
    container_name = f"{prefix}{name}"

    try:
        client = _docker()
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        _audit_log(request, "session.exec", session_name=name, success=False, error="not_found")
        raise HTTPException(status_code=404, detail=f"Container '{name}' not found")

    loop = asyncio.get_running_loop()
    exit_code, output = await loop.run_in_executor(
        None, lambda: container.exec_run(["sh", "-c", body.command])
    )
    _audit_log(
        request,
        "session.exec",
        session_name=name,
        success=exit_code == 0,
        error=None if exit_code == 0 else f"exit_code={exit_code}",
    )
    return {
        "success": exit_code == 0,
        "exit_code": exit_code,
        "output": output.decode(errors="replace"),
    }


@app.post("/api/sessions/{name}/query")
@limiter.limit("5/minute")
async def api_query_session(request: Request, name: str, body: QuerySessionRequest):
    """Send a prompt to Claude Code running in the container via tmux.

    This endpoint sends the prompt directly to the running Claude instance
    in the tmux session using docker exec and tmux commands.
    """
    prefix = settings.resolved_prefix
    container_name = f"{prefix}{name}"
    start_time = time.time()

    # Verify container exists and is running
    try:
        client = _docker()
        container = client.containers.get(container_name)
        if container.status != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Container '{name}' is not running (status: {container.status})",
            )
    except docker.errors.NotFound:
        _audit_log(request, "session.query", session_name=name, success=False, error="not_found")
        raise HTTPException(status_code=404, detail=f"Container '{name}' not found")

    # Check if tmux session exists
    loop = asyncio.get_running_loop()
    exit_code, _ = await loop.run_in_executor(
        None, lambda: container.exec_run(["tmux", "has-session", "-t", "main"])
    )

    if exit_code != 0:
        _audit_log(
            request, "session.query", session_name=name, success=False, error="no_tmux_session"
        )
        raise HTTPException(
            status_code=503,
            detail="Claude tmux session not found in container. Is Claude running?",
        )

    try:
        # Clear any existing input
        await loop.run_in_executor(
            None, lambda: container.exec_run(["tmux", "send-keys", "-t", "main", "C-c"])
        )
        await asyncio.sleep(0.5)

        # Change to working directory if specified
        if body.working_dir:
            cd_cmd = f"cd {body.working_dir}"
            await loop.run_in_executor(
                None,
                lambda: container.exec_run(["tmux", "send-keys", "-t", "main", cd_cmd, "Enter"]),
            )
            await asyncio.sleep(0.5)

        # Capture pane before sending prompt
        exit_code, before_output = await loop.run_in_executor(
            None, lambda: container.exec_run(["tmux", "capture-pane", "-t", "main", "-p"])
        )

        # Send prompt to tmux session
        await loop.run_in_executor(
            None,
            lambda: container.exec_run(["tmux", "send-keys", "-t", "main", body.prompt, "Enter"]),
        )

        # Wait a moment for Claude to show the permission prompt
        await asyncio.sleep(2)

        # Auto-approve permissions by pressing Enter (bypass is already on)
        await loop.run_in_executor(
            None, lambda: container.exec_run(["tmux", "send-keys", "-t", "main", "Enter"])
        )

        # Wait for Claude to complete - detect completion markers
        max_wait = body.timeout
        waited = 0
        poll_interval = 0.5
        last_output = ""
        stable_count = 0

        while waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval

            # Capture current pane content
            exit_code, current_output = await loop.run_in_executor(
                None, lambda: container.exec_run(["tmux", "capture-pane", "-t", "main", "-p"])
            )
            output_text = current_output.decode("utf-8", errors="replace")

            # Check for completion markers that indicate Claude is done
            completion_markers = [
                "● Done",  # Claude's done marker
                "● Complete",  # Alternative completion
                "● Error",  # Error completion
                "● Failed",  # Failure completion
            ]

            # Also check if prompt is back (lines with ❯ that aren't in the permission UI)
            lines = output_text.splitlines()
            prompt_back = False
            for i, line in enumerate(lines):
                # Look for prompt line that's not followed by permission UI
                if line.strip().startswith("❯") and len(line.strip()) == 1:
                    # Check next few lines don't have permission UI
                    if i + 1 < len(lines):
                        next_line = lines[i + 1] if i + 1 < len(lines) else ""
                        if "bypass permissions" not in next_line and "⏵" not in next_line:
                            prompt_back = True
                            break

            # Check if any completion marker is present
            has_completion_marker = any(marker in output_text for marker in completion_markers)

            # If output hasn't changed for 2 polls and we see completion, we're done
            if output_text == last_output:
                if has_completion_marker or prompt_back:
                    stable_count += 1
                    if stable_count >= 2:  # Stable for 1 second with completion
                        break
            else:
                stable_count = 0

            last_output = output_text

        if waited >= max_wait:
            _audit_log(request, "session.query", session_name=name, success=False, error="timeout")
            raise HTTPException(
                status_code=408,
                detail=f"Query execution timed out after {body.timeout}s",
            )

        # Capture final output
        exit_code, final_output = await loop.run_in_executor(
            None,
            lambda: container.exec_run(["tmux", "capture-pane", "-t", "main", "-p", "-S", "-100"]),
        )
        output = final_output.decode("utf-8", errors="replace")

        # Calculate duration
        duration = time.time() - start_time

        # Extract response (everything after the prompt line)
        lines = output.splitlines()
        response_lines = []
        found_prompt = False

        for line in lines:
            if body.prompt in line and "❯" in line:
                found_prompt = True
                continue
            if found_prompt:
                response_lines.append(line)

        cleaned_output = "\n".join(response_lines).strip()

        _audit_log(request, "session.query", session_name=name, success=True)

        return {
            "success": True,
            "conversation_id": f"{name}-{int(time.time())}",
            "output": cleaned_output or output,
            "error": None,
            "exit_code": 0,
            "duration_seconds": duration,
            "files_modified": [],  # TODO: Implement git-based detection
        }

    except Exception as e:
        _audit_log(request, "session.query", session_name=name, success=False, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {e}",
        )


# ---------------------------------------------------------------------------
# Container metrics (with LangFuse trace count cache)
# ---------------------------------------------------------------------------

_trace_cache: dict[str, dict[str, Any]] = {}  # session_name -> {data, ts}
_TRACE_CACHE_TTL = 10  # seconds


def _get_trace_counts(session_name: str) -> dict[str, int]:
    """Get trace/error counts for a session, cached for 10s."""
    now = time.monotonic()
    cached = _trace_cache.get(session_name)
    if cached and (now - cached["ts"]) < _TRACE_CACHE_TTL:
        return cached["data"]

    if settings.langfuse.mode == "off":
        return {"trace_count": 0, "error_count": 0}

    try:
        summary = get_session_traces_summary(session_name)
        data = {"trace_count": summary.total_traces, "error_count": summary.error_count}
    except Exception:
        data = {"trace_count": 0, "error_count": 0}

    _trace_cache[session_name] = {"data": data, "ts": now}
    return data


def _get_container_metrics() -> list[dict[str, Any]]:
    """Collect per-container CPU %, memory usage, and uptime (blocking)."""
    results = []
    try:
        client = _docker()
        containers = client.containers.list(filters={"label": "brainbox.managed=true"})
        for c in containers:
            try:
                stats = c.stats(stream=False)
                cpu_pct = _calc_cpu(stats)
                mem = stats.get("memory_stats", {})
                mem_usage = mem.get("usage", 0)
                mem_limit = mem.get("limit", 1)

                # Uptime from State.StartedAt
                started_at = c.attrs.get("State", {}).get("StartedAt", "")
                uptime_seconds = 0
                if started_at:
                    try:
                        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                        uptime_seconds = (datetime.now(timezone.utc) - started).total_seconds()
                    except (ValueError, TypeError):
                        pass

                labels = c.labels or {}
                session_name = _extract_session_name(c.name)
                trace_counts = _get_trace_counts(session_name)
                results.append(
                    {
                        "name": c.name,
                        "session_name": session_name,
                        "role": _extract_role(c),
                        "llm_provider": labels.get("brainbox.llm_provider", "claude"),
                        "workspace_profile": labels.get("brainbox.workspace_profile", ""),
                        "cpu_percent": round(cpu_pct, 2),
                        "mem_usage": mem_usage,
                        "mem_usage_human": _human_bytes(mem_usage),
                        "mem_limit": mem_limit,
                        "mem_limit_human": _human_bytes(mem_limit),
                        "uptime_seconds": round(uptime_seconds),
                        "trace_count": trace_counts["trace_count"],
                        "error_count": trace_counts["error_count"],
                    }
                )
            except Exception:
                pass
    except Exception:
        pass

    results.sort(key=lambda r: r["name"])
    return results


@app.get("/api/metrics/containers")
async def api_container_metrics():
    """Per-container CPU %, memory usage, and uptime."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_container_metrics)


# ---------------------------------------------------------------------------
# Hub API routes (from hub-api.js)
# ---------------------------------------------------------------------------

# --- Agents ---


@app.get("/api/hub/agents")
async def hub_list_agents():
    return [a.model_dump() for a in list_agents()]


@app.get("/api/hub/agents/{name}")
async def hub_get_agent(name: str):
    agent = get_agent(name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return agent.model_dump()


# --- Tasks ---


@app.post("/api/hub/tasks", status_code=201)
async def hub_submit_task(body: TaskCreate):
    try:
        task = await submit_task(body.description, body.agent_name)
        return task.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/hub/tasks")
async def hub_list_tasks(status: str | None = None):
    tasks = list_tasks(status=status)
    return [t.model_dump() for t in tasks]


@app.get("/api/hub/tasks/{task_id}")
async def hub_get_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task.model_dump()


@app.delete("/api/hub/tasks/{task_id}")
async def hub_cancel_task(task_id: str):
    try:
        task = await cancel_task(task_id)
        return task.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- Messages ---


@app.post("/api/hub/messages")
async def hub_route_message(request: Request, token: Token = Depends(require_token)):
    body = await request.json()

    try:
        result = route_message(
            {
                "sender_token_id": token.token_id,
                "recipient": body.get("recipient", "hub"),
                "type": body.get("type"),
                "payload": body.get("payload"),
            }
        )
    except ValueError as exc:
        status = 401 if "token" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc))

    # Handle task completion side effect
    payload = body.get("payload", {})
    if isinstance(payload, dict) and payload.get("event") == "task.completed":
        task_id = token.task_id
        completion_result = payload.get("result")
        if task_id:
            try:
                await complete_task(task_id, completion_result)
            except Exception:
                pass

    return result


@app.get("/api/hub/messages")
async def hub_get_messages(token: Token = Depends(require_token)):
    return get_messages(token.token_id)


# --- Tokens ---


@app.get("/api/hub/tokens")
async def hub_list_tokens():
    return [t.model_dump() for t in list_tokens()]


# --- State ---


@app.get("/api/hub/state")
async def hub_state():
    return {
        "agents": [a.model_dump() for a in list_agents()],
        "tasks": [t.model_dump() for t in list_tasks()],
        "tokens": [t.model_dump() for t in list_tokens()],
        "messages": get_message_log(),
    }


# ---------------------------------------------------------------------------
# Artifact store
# ---------------------------------------------------------------------------


async def _artifact_op(operation_fn, *args, **kwargs):
    """Run an artifact operation respecting the configured mode."""
    mode = settings.artifact.mode
    if mode == "off":
        raise HTTPException(status_code=503, detail="Artifact store is disabled")
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: operation_fn(*args, **kwargs))
    except ArtifactError as exc:
        if "not found" in exc.reason:
            raise HTTPException(status_code=404, detail=str(exc))
        if mode == "enforce":
            raise HTTPException(status_code=502, detail=str(exc))
        log.warning("artifact.operation_failed", metadata={"error": str(exc)})
        return None
    except Exception as exc:
        if mode == "enforce":
            raise HTTPException(status_code=502, detail=str(exc))
        log.warning("artifact.operation_failed", metadata={"error": str(exc)})
        return None


@app.get("/api/artifacts/health")
async def api_artifact_health():
    """Check artifact store connectivity."""
    mode = settings.artifact.mode
    if mode == "off":
        return {"healthy": False, "mode": "off", "detail": "Artifact store is disabled"}
    loop = asyncio.get_running_loop()
    healthy = await loop.run_in_executor(None, artifact_health_check)
    return {"healthy": healthy, "mode": mode}


@app.get("/api/artifacts")
async def api_list_artifacts(prefix: str = Query(default="")):
    """List artifacts, optionally filtered by key prefix."""
    result = await _artifact_op(list_artifacts, prefix)
    if result is None:
        return []
    return [
        {"key": a.key, "size": a.size, "etag": a.etag, "timestamp": a.timestamp} for a in result
    ]


@app.post("/api/artifacts/{key:path}", status_code=201)
@limiter.limit("30/minute")
async def api_upload_artifact(key: str, request: Request):
    """Upload an artifact (raw bytes in request body)."""
    # Validate artifact key to prevent path traversal
    try:
        validated_key = validate_artifact_key(key)
    except ValidationError as val_err:
        log.error("artifact.upload.validation_failed", metadata={"key": key, "error": str(val_err)})
        raise HTTPException(status_code=400, detail=str(val_err))

    data = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")
    metadata = {"content_type": content_type}

    task_id = request.headers.get("x-task-id")
    if task_id:
        metadata["task_id"] = task_id

    result = await _artifact_op(upload_artifact, validated_key, data, metadata)
    if result is None:
        return {"stored": False, "key": validated_key}
    return {"stored": True, "key": result.key, "size": result.size, "etag": result.etag}


@app.get("/api/artifacts/{key:path}")
@limiter.limit("30/minute")
async def api_download_artifact(request: Request, key: str):
    """Download an artifact by key."""
    # Validate artifact key to prevent path traversal
    try:
        validated_key = validate_artifact_key(key)
    except ValidationError as val_err:
        log.error(
            "artifact.download.validation_failed", metadata={"key": key, "error": str(val_err)}
        )
        raise HTTPException(status_code=400, detail=str(val_err))

    result = await _artifact_op(download_artifact, validated_key)
    if result is None:
        raise HTTPException(status_code=404, detail="Artifact not available")
    body, metadata = result
    content_type = metadata.get("content_type", "application/octet-stream")
    return Response(content=body, media_type=content_type)


@app.delete("/api/artifacts/{key:path}")
@limiter.limit("30/minute")
async def api_delete_artifact(request: Request, key: str):
    """Delete an artifact by key."""
    await _artifact_op(delete_artifact, key)
    return {"deleted": True, "key": key}


# ---------------------------------------------------------------------------
# LangFuse observability proxy
# ---------------------------------------------------------------------------


async def _langfuse_op(operation_fn, *args, **kwargs):
    """Run a LangFuse operation respecting the configured mode."""
    mode = settings.langfuse.mode
    if mode == "off":
        raise HTTPException(status_code=503, detail="LangFuse integration is disabled")
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: operation_fn(*args, **kwargs))
    except LangfuseError as exc:
        if mode == "enforce":
            raise HTTPException(status_code=502, detail=str(exc))
        log.warning("langfuse.operation_failed", metadata={"error": str(exc)})
        return None
    except Exception as exc:
        if mode == "enforce":
            raise HTTPException(status_code=502, detail=str(exc))
        log.warning("langfuse.operation_failed", metadata={"error": str(exc)})
        return None


@app.get("/api/langfuse/health")
async def api_langfuse_health():
    """Check LangFuse connectivity."""
    mode = settings.langfuse.mode
    if mode == "off":
        return {"healthy": False, "mode": "off", "detail": "LangFuse integration is disabled"}
    loop = asyncio.get_running_loop()
    healthy = await loop.run_in_executor(None, langfuse_health_check)
    return {"healthy": healthy, "mode": mode}


@app.get("/api/langfuse/sessions/{session_name}/traces")
async def api_langfuse_session_traces(session_name: str, limit: int = Query(default=50)):
    """List traces for a container session."""
    result = await _langfuse_op(langfuse_list_traces, session_name, limit)
    if result is None:
        return []
    return [
        {
            "id": t.id,
            "name": t.name,
            "session_id": t.session_id,
            "timestamp": t.timestamp,
            "status": t.status,
            "input": t.input,
            "output": t.output,
        }
        for t in result
    ]


@app.get("/api/langfuse/sessions/{session_name}/summary")
async def api_langfuse_session_summary(session_name: str):
    """Trace count, error count, and tool breakdown for a session."""
    result = await _langfuse_op(get_session_traces_summary, session_name)
    if result is None:
        return {
            "session_id": session_name,
            "total_traces": 0,
            "total_observations": 0,
            "error_count": 0,
            "tool_counts": {},
        }
    return {
        "session_id": result.session_id,
        "total_traces": result.total_traces,
        "total_observations": result.total_observations,
        "error_count": result.error_count,
        "tool_counts": result.tool_counts,
    }


@app.get("/api/langfuse/traces/{trace_id}")
async def api_langfuse_trace_detail(trace_id: str):
    """Single trace detail with observations."""
    result = await _langfuse_op(langfuse_get_trace, trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Trace not available")
    trace, observations = result
    return {
        "trace": {
            "id": trace.id,
            "name": trace.name,
            "session_id": trace.session_id,
            "timestamp": trace.timestamp,
            "status": trace.status,
            "input": trace.input,
            "output": trace.output,
        },
        "observations": [
            {
                "id": o.id,
                "trace_id": o.trace_id,
                "name": o.name,
                "type": o.type,
                "start_time": o.start_time,
                "end_time": o.end_time,
                "status": o.status,
                "level": o.level,
            }
            for o in observations
        ],
    }


# ---------------------------------------------------------------------------
# SPA: serve built dashboard (must be last)
# ---------------------------------------------------------------------------

if _dashboard_dist.is_dir():
    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=str(_dashboard_dist / "assets")), name="assets")

    # SPA fallback: serve index.html for any non-API route
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        # Try to serve exact file first (e.g. favicon.ico)
        file = _dashboard_dist / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(_dashboard_dist / "index.html")
