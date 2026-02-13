"""Async container health monitoring.

Tracks running containers and periodically checks health via Docker SDK.
"""

from __future__ import annotations

import asyncio

from .log import get_logger
from .models import SessionContext

# Tracked sessions keyed by session_name
_tracked: dict[str, SessionContext] = {}
_task: asyncio.Task[None] | None = None


def start_monitoring(ctx: SessionContext) -> None:
    """Register a session for periodic health checks."""
    _tracked[ctx.session_name] = ctx
    slog = get_logger(session_name=ctx.session_name, container_name=ctx.container_name)
    slog.info("monitor.started")

    # Start the background loop if not already running
    global _task
    if _task is None or _task.done():
        try:
            loop = asyncio.get_running_loop()
            _task = loop.create_task(_monitor_loop())
        except RuntimeError:
            pass  # No running loop (CLI mode) — monitor won't run


def stop_monitoring(session_name: str) -> None:
    """Unregister a session from health checks."""
    _tracked.pop(session_name, None)


async def _monitor_loop() -> None:
    """Periodically check health of all tracked containers."""
    from .config import settings

    import docker
    from docker.errors import NotFound

    client = docker.from_env()
    interval = settings.health_check_interval

    while _tracked:
        for name, ctx in list(_tracked.items()):
            try:
                container = client.containers.get(ctx.container_name)
                container.reload()
                is_running = container.attrs["State"]["Running"]

                if not is_running:
                    ctx.health_failures += 1
                    slog = get_logger(session_name=name, container_name=ctx.container_name)
                    slog.warning("monitor.container_not_running", metadata={"failures": ctx.health_failures})
                    continue

                # Get stats (non-streaming)
                stats = container.stats(stream=False)
                cpu_pct = _calc_cpu(stats)
                mem = stats.get("memory_stats", {})
                mem_usage = mem.get("usage", 0)
                mem_limit = mem.get("limit", 1)

                slog = get_logger(session_name=name, container_name=ctx.container_name)
                slog.debug(
                    "container.health_check",
                    metadata={
                        "stats": {
                            "cpu": f"{cpu_pct:.2f}%",
                            "mem": f"{_human_bytes(mem_usage)} / {_human_bytes(mem_limit)}",
                        }
                    },
                )

                # Check TTL
                import time
                elapsed = (time.time() * 1000 - ctx.created_at) / 1000
                if ctx.ttl > 0 and elapsed > ctx.ttl:
                    slog.warning("monitor.ttl_expired", metadata={"elapsed": elapsed, "ttl": ctx.ttl})
                    from .models import SessionState
                    ctx.state = SessionState.RECYCLING

            except NotFound:
                slog = get_logger(session_name=name, container_name=ctx.container_name)
                slog.warning("monitor.container_gone")
                _tracked.pop(name, None)
            except Exception as exc:
                slog = get_logger(session_name=name, container_name=ctx.container_name)
                slog.warning("monitor.check_failed", metadata={"reason": str(exc)})

        await asyncio.sleep(interval)


def _calc_cpu(stats: dict) -> float:
    """Calculate CPU percentage from docker stats."""
    cpu = stats.get("cpu_stats", {})
    precpu = stats.get("precpu_stats", {})

    cpu_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get("cpu_usage", {}).get("total_usage", 0)
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
