"""Hub facade: init/shutdown, state persistence, convenience delegates."""

from __future__ import annotations

import asyncio
import json

from .config import settings
from .log import get_logger
from .messages import get_state as messages_get_state
from .messages import restore_state as messages_restore_state
from .registry import (
    get_state as registry_get_state,
    list_agents,
    list_tokens,
    load_agents,
    restore_state as registry_restore_state,
)
from .router import (
    check_running_tasks,
    get_state as router_get_state,
    list_tasks,
    restore_state as router_restore_state,
)

log = get_logger()

_flush_task: asyncio.Task[None] | None = None
_check_task: asyncio.Task[None] | None = None


# ---------------------------------------------------------------------------
# Init / Shutdown
# ---------------------------------------------------------------------------


async def init() -> None:
    """Initialize the hub: load agents, restore state, start background tasks."""
    load_agents()
    await _restore_state()

    loop = asyncio.get_running_loop()
    global _flush_task, _check_task
    _flush_task = loop.create_task(_periodic_flush())
    _check_task = loop.create_task(_periodic_check())

    log.info(
        "hub.initialized",
        metadata={"agents": len(list_agents()), "stateFile": str(settings.state_file)},
    )


async def shutdown() -> None:
    """Stop background tasks and flush state."""
    global _flush_task, _check_task
    if _flush_task and not _flush_task.done():
        _flush_task.cancel()
        _flush_task = None
    if _check_task and not _check_task.done():
        _check_task.cancel()
        _check_task = None

    await _flush_state()
    log.info("hub.shutdown")


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


async def _flush_state() -> None:
    import time

    state = {
        "flushed_at": int(time.time() * 1000),
        "registry": registry_get_state(),
        "router": router_get_state(),
        "messages": messages_get_state(),
    }

    state_file = settings.state_file
    tmp_file = state_file.with_suffix(".tmp")
    content = json.dumps(state, indent=2, default=str)

    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(tmp_file.write_text, content)
        await asyncio.to_thread(tmp_file.rename, state_file)
    except Exception as exc:
        log.warning("hub.flush_failed", metadata={"reason": str(exc)})


async def _restore_state() -> None:
    state_file = settings.state_file
    try:
        raw = await asyncio.to_thread(state_file.read_text)
    except FileNotFoundError:
        return

    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("hub.state_parse_failed", metadata={"reason": str(exc)})
        return

    # Restore in order: registry (tokens) first, then router (tasks), then messages
    registry_restore_state(state.get("registry"))
    router_restore_state(state.get("router"))
    messages_restore_state(state.get("messages"))

    log.info(
        "hub.state_restored",
        metadata={"tokens": len(list_tokens()), "tasks": len(list_tasks())},
    )


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------


async def _periodic_flush() -> None:
    try:
        while True:
            await asyncio.sleep(settings.hub.flush_interval)
            await _flush_state()
    except asyncio.CancelledError:
        pass


async def _periodic_check() -> None:
    try:
        while True:
            await asyncio.sleep(settings.health_check_interval)
            await check_running_tasks()
    except asyncio.CancelledError:
        pass
