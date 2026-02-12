"""FastAPI application: hub API, session management, dashboard, and SSE."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import docker
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from datetime import datetime, timezone

from .config import settings
from .hub import init as hub_init, shutdown as hub_shutdown
from .monitor import _calc_cpu, _human_bytes
from .lifecycle import (
    provision,
    configure,
    recycle,
    run_pipeline,
    start as lifecycle_start,
    monitor as lifecycle_monitor,
)
from .log import get_logger, setup_logging
from .models import TaskCreate, Token
from .registry import get_agent, list_agents, list_tokens, validate_token
from .router import (
    cancel_task,
    complete_task,
    get_task,
    list_tasks,
    on_event,
    submit_task,
)
from .messages import get_message_log, get_messages, route as route_message

log = get_logger()

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
            client = docker.from_env()
            for event in client.events(filters={"name": "developer"}, decode=True):
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
    on_event(lambda event, data: _broadcast_sse(
        json.dumps({"hub": True, "event": event, "data": data.model_dump() if hasattr(data, "model_dump") else data})
    ))

    # Start Docker events watcher
    global _docker_events_task
    _docker_events_task = asyncio.create_task(_watch_docker_events())

    log.info("api.started", metadata={"port": settings.api_port})
    yield

    if _docker_events_task:
        _docker_events_task.cancel()
    await hub_shutdown()


app = FastAPI(title="Container Lifecycle", version="0.2.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Dashboard (session info helper used by API)
# ---------------------------------------------------------------------------


def _get_sessions_info() -> list[dict[str, Any]]:
    """Get session info from Docker."""
    sessions = []
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "developer-"})

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

            sessions.append({
                "name": name,
                "port": port,
                "url": f"http://localhost:{port}" if port else None,
                "volume": volume,
                "active": is_running,
            })
    except Exception:
        pass

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
    return _get_sessions_info()


@app.post("/api/stop")
async def api_stop_session(request: Request):
    body = await request.json()
    name = body.get("name", "")
    session_name = name.replace("developer-", "")
    try:
        await recycle(session_name, reason="dashboard_stop")
        return {"success": True}
    except Exception:
        # Fallback to direct Docker stop
        try:
            client = docker.from_env()
            container = client.containers.get(name)
            container.stop(timeout=1)
            return {"success": True}
        except Exception:
            return {"success": False}


@app.post("/api/delete")
async def api_delete_session(request: Request):
    body = await request.json()
    name = body.get("name", "")
    session_name = name.replace("developer-", "")
    try:
        await recycle(session_name, reason="dashboard_delete")
        return {"success": True}
    except Exception:
        try:
            client = docker.from_env()
            container = client.containers.get(name)
            container.remove()
            return {"success": True}
        except Exception:
            return {"success": False}


@app.post("/api/start")
async def api_start_session(request: Request):
    body = await request.json()
    name = body.get("name", "")
    session_name = name.replace("developer-", "")
    try:
        ctx = await provision(session_name=session_name, hardened=False)
        await configure(ctx)
        await lifecycle_start(ctx)
        await lifecycle_monitor(ctx)
        return {"success": True, "url": f"http://localhost:{ctx.port}"}
    except Exception:
        # Fallback to direct Docker start
        try:
            client = docker.from_env()
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

            return {"success": True, "url": f"http://localhost:{port}"}
        except Exception:
            return {"success": False}


@app.post("/api/create")
async def api_create_session(request: Request):
    body = await request.json()
    name = body.get("name")
    volume = body.get("volume")
    try:
        ctx = await run_pipeline(
            session_name=name or "default",
            hardened=False,
            volume_mounts=[volume] if volume else [],
        )
        return {"success": True, "url": f"http://localhost:{ctx.port}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Container metrics
# ---------------------------------------------------------------------------


@app.get("/api/metrics/containers")
async def api_container_metrics():
    """Per-container CPU %, memory usage, and uptime."""
    results = []
    try:
        client = docker.from_env()
        containers = client.containers.list(filters={"name": "developer-"})
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

                results.append({
                    "name": c.name,
                    "cpu_percent": round(cpu_pct, 2),
                    "mem_usage": mem_usage,
                    "mem_usage_human": _human_bytes(mem_usage),
                    "mem_limit": mem_limit,
                    "mem_limit_human": _human_bytes(mem_limit),
                    "uptime_seconds": round(uptime_seconds),
                })
            except Exception:
                pass
    except Exception:
        pass

    results.sort(key=lambda r: r["name"])
    return results


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
        result = route_message({
            "sender_token_id": token.token_id,
            "recipient": body.get("recipient", "hub"),
            "type": body.get("type"),
            "payload": body.get("payload"),
        })
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
