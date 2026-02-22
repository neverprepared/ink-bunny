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
    """Periodically check health of all tracked sessions (Docker + UTM)."""
    from .backends import create_backend
    from .config import settings
    from .models import SessionState
    import time

    interval = settings.health_check_interval
    timeout = settings.health_check_timeout

    while _tracked:
        for name, ctx in list(_tracked.items()):
            slog = get_logger(session_name=name, container_name=ctx.container_name)

            try:
                # Delegate health check to backend with timeout
                backend = create_backend(ctx.backend)
                health = await asyncio.wait_for(backend.health_check(ctx), timeout=timeout)

                if not health.get("healthy", False):
                    ctx.health_failures += 1
                    slog.warning(
                        "monitor.unhealthy",
                        metadata={
                            "backend": ctx.backend,
                            "failures": ctx.health_failures,
                            "reason": health.get("reason", "unknown"),
                        },
                    )
                    # Remove from tracking if it's gone
                    if "not found" in health.get("reason", "").lower():
                        _tracked.pop(name, None)
                    continue

                # Log health metrics (backend-specific)
                if ctx.backend == "docker":
                    cpu_pct = health.get("cpu_percent", 0)
                    mem_usage_human = health.get("memory_usage_human", "0B")
                    mem_limit_human = health.get("memory_limit_human", "0B")
                    slog.debug(
                        "monitor.health_check",
                        metadata={
                            "backend": "docker",
                            "stats": {
                                "cpu": f"{cpu_pct:.2f}%",
                                "mem": f"{mem_usage_human} / {mem_limit_human}",
                            },
                        },
                    )
                elif ctx.backend == "utm":
                    vm_state = health.get("vm_state", "unknown")
                    ssh_reachable = health.get("ssh_reachable", False)
                    slog.debug(
                        "monitor.health_check",
                        metadata={
                            "backend": "utm",
                            "vm_state": vm_state,
                            "ssh_reachable": ssh_reachable,
                            "ssh_port": ctx.ssh_port,
                        },
                    )

                # Check TTL (same for all backends)
                elapsed = (time.time() * 1000 - ctx.created_at) / 1000
                if ctx.ttl > 0 and elapsed > ctx.ttl:
                    slog.warning(
                        "monitor.ttl_expired",
                        metadata={"elapsed": elapsed, "ttl": ctx.ttl, "backend": ctx.backend},
                    )
                    ctx.state = SessionState.RECYCLING

            except asyncio.TimeoutError:
                ctx.health_failures += 1
                slog.warning(
                    "monitor.health_check_timeout",
                    metadata={
                        "backend": ctx.backend,
                        "timeout": timeout,
                        "failures": ctx.health_failures,
                    },
                )
            except Exception as exc:
                slog.warning(
                    "monitor.check_failed",
                    metadata={"reason": str(exc), "backend": ctx.backend},
                )

        await asyncio.sleep(interval)
