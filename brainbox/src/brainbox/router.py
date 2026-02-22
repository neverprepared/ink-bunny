"""Task router: dispatch tasks to agents, manage lifecycle coordination."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from .config import settings
from .log import get_logger
from .models import Task, TaskStatus
from .policy import evaluate_task_assignment
from .registry import get_agent, issue_token, revoke_token

log = get_logger()

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_tasks: dict[str, Task] = {}
_listeners: list[Callable[[str, Task], None]] = []


def _emit(event: str, task: Task) -> None:
    for fn in _listeners:
        try:
            fn(event, task)
        except Exception:
            pass


def on_event(fn: Callable[[str, Task], None]) -> None:
    """Register an event listener (for SSE bridge)."""
    _listeners.append(fn)


# ---------------------------------------------------------------------------
# Task management
# ---------------------------------------------------------------------------


async def submit_task(description: str, agent_name: str) -> Task:
    """Create and launch a task for the given agent."""
    from . import lifecycle

    if not description:
        raise ValueError("Task description is required")
    if not agent_name:
        raise ValueError("Agent name is required")

    agent_def = get_agent(agent_name)
    if not agent_def:
        raise ValueError(f"Agent '{agent_name}' not found")

    task_id = str(uuid.uuid4())
    now = _now_ms()
    task = Task(
        id=task_id,
        description=description,
        agent_name=agent_name,
        status=TaskStatus.PENDING,
        created_at=now,
        updated_at=now,
    )

    # Policy check
    check = evaluate_task_assignment(agent_def, task)
    if not check.allowed:
        raise ValueError(f"Policy denied: {check.reason}")

    # Issue token with configurable TTL
    token = issue_token(agent_name, task_id, ttl=settings.hub.token_ttl)
    task.token_id = token.token_id

    # Build session name
    session_name = f"task-{task_id[:8]}"
    task.session_name = session_name
    task.status = TaskStatus.RUNNING
    task.updated_at = _now_ms()
    _tasks[task_id] = task

    # Launch container
    try:
        await lifecycle.run_pipeline(
            session_name=session_name,
            hardened=agent_def.hardened,
            token=token,
        )
    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.error = str(exc)
        task.updated_at = _now_ms()
        revoke_token(token.token_id)
        log.error("router.task_launch_failed", metadata={"task_id": task_id, "reason": str(exc)})
        _emit("task.failed", task)
        raise

    log.info(
        "router.task_started",
        metadata={"task_id": task_id, "session": session_name, "agent": agent_name},
    )
    _emit("task.started", task)
    return task


def get_task(task_id: str) -> Task | None:
    return _tasks.get(task_id)


def list_tasks(
    *,
    status: str | None = None,
    agent_name: str | None = None,
) -> list[Task]:
    result = list(_tasks.values())
    if status:
        result = [t for t in result if t.status == status]
    if agent_name:
        result = [t for t in result if t.agent_name == agent_name]
    result.sort(key=lambda t: t.created_at, reverse=True)
    return result


async def complete_task(task_id: str, result: Any = None) -> Task:
    """Mark a task as completed and recycle its container."""
    from . import lifecycle

    task = _tasks.get(task_id)
    if not task:
        raise ValueError(f"Task '{task_id}' not found")
    if task.status != TaskStatus.RUNNING:
        raise ValueError(f"Task '{task_id}' is not running (status: {task.status})")

    task.status = TaskStatus.COMPLETED
    task.result = result
    task.updated_at = _now_ms()

    # Recycle container
    if task.session_name:
        try:
            await lifecycle.recycle(task.session_name, reason="task_completed")
        except Exception as exc:
            log.warning("router.recycle_failed", metadata={"task_id": task_id, "reason": str(exc)})

    # Revoke token
    if task.token_id:
        revoke_token(task.token_id)

    log.info("router.task_completed", metadata={"task_id": task_id})
    _emit("task.completed", task)
    return task


async def fail_task(task_id: str, error: str | None = None) -> Task:
    from . import lifecycle

    task = _tasks.get(task_id)
    if not task:
        raise ValueError(f"Task '{task_id}' not found")

    task.status = TaskStatus.FAILED
    task.error = error or "Unknown error"
    task.updated_at = _now_ms()

    if task.session_name:
        try:
            await lifecycle.recycle(task.session_name, reason="task_failed")
        except Exception as exc:
            log.warning("router.recycle_failed", metadata={"task_id": task_id, "reason": str(exc)})

    if task.token_id:
        revoke_token(task.token_id)

    log.info("router.task_failed", metadata={"task_id": task_id, "error": error})
    _emit("task.failed", task)
    return task


async def cancel_task(task_id: str) -> Task:
    from . import lifecycle

    task = _tasks.get(task_id)
    if not task:
        raise ValueError(f"Task '{task_id}' not found")
    if task.status not in (TaskStatus.RUNNING, TaskStatus.PENDING):
        raise ValueError(f"Task '{task_id}' cannot be cancelled (status: {task.status})")

    task.status = TaskStatus.CANCELLED
    task.updated_at = _now_ms()

    if task.session_name:
        try:
            await lifecycle.recycle(task.session_name, reason="task_cancelled")
        except Exception as exc:
            log.warning("router.recycle_failed", metadata={"task_id": task_id, "reason": str(exc)})

    if task.token_id:
        revoke_token(task.token_id)

    log.info("router.task_cancelled", metadata={"task_id": task_id})
    _emit("task.cancelled", task)
    return task


async def check_running_tasks() -> None:
    """Check running tasks for missing or recycled containers."""
    from . import lifecycle

    for task in list(_tasks.values()):
        if task.status != TaskStatus.RUNNING:
            continue

        session = lifecycle.get_session(task.session_name)
        if not session:
            await fail_task(task.id, "Container no longer exists")
            continue

        from .models import SessionState

        if session.state == SessionState.RECYCLED:
            await fail_task(task.id, "Container was recycled externally")


# ---------------------------------------------------------------------------
# State serialization
# ---------------------------------------------------------------------------


def get_state() -> dict:
    return {"tasks": [(tid, t.model_dump()) for tid, t in _tasks.items()]}


def restore_state(state: dict | None) -> None:
    if not state or "tasks" not in state:
        return
    _terminal = {"completed", "failed", "cancelled"}
    for tid, data in state["tasks"]:
        task = Task(**data)
        if task.status in _terminal:
            continue
        _tasks[tid] = task


def _now_ms() -> int:
    return int(time.time() * 1000)
