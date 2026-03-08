"""Task router: dispatch tasks to agents, manage lifecycle coordination.

Enhanced with multi-repo awareness and role-aware dispatch, absorbing patterns
from multiclaude (Dan Lorenc, github.com/dlorenc/multiclaude).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from .config import settings
from .log import get_logger
from .models import Repository, Task, TaskStatus
from .policy import evaluate_task_assignment
from .registry import get_agent, issue_token, revoke_token

log = get_logger()

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_tasks: dict[str, Task] = {}
_listeners: list[Callable[[str, Task], None]] = []
_repos: dict[str, Repository] = {}  # name -> Repository


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


async def submit_task(
    description: str,
    agent_name: str,
    *,
    repo_url: str | None = None,
) -> Task:
    """Create and launch a task for the given agent.

    When *repo_url* is provided the task is associated with a tracked repo
    and the container receives the repo's volume mount + role prompt.
    """
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
        repo_url=repo_url,
    )

    # Policy check
    check = evaluate_task_assignment(agent_def, task)
    if not check.allowed:
        raise ValueError(f"Policy denied: {check.reason}")

    # Use longer TTL for persistent agents
    ttl = (
        settings.hub.persistent_token_ttl
        if agent_def.persistent
        else settings.hub.token_ttl
    )
    token = issue_token(agent_name, task_id, ttl=ttl)
    task.token_id = token.token_id

    # Build session name
    session_name = f"task-{task_id[:8]}"
    task.session_name = session_name
    task.status = TaskStatus.RUNNING
    task.updated_at = _now_ms()
    _tasks[task_id] = task

    # Launch container with role-specific configuration
    try:
        await lifecycle.run_pipeline(
            session_name=session_name,
            role=agent_name,
            hardened=agent_def.hardened,
            token=token,
            repo_url=repo_url,
        )
    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.error = str(exc)
        task.updated_at = _now_ms()
        revoke_token(token.token_id)
        log.error("router.task_launch_failed", metadata={"task_id": task_id, "reason": str(exc)})
        _emit("task.failed", task)
        raise

    # Track container in repo if applicable
    if repo_url:
        repo = _repos.get(_repo_name(repo_url))
        if repo:
            repo.containers[agent_name] = session_name

    log.info(
        "router.task_started",
        metadata={
            "task_id": task_id,
            "session": session_name,
            "agent": agent_name,
            "repo": repo_url,
        },
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
    """Check running tasks for missing or recycled containers.

    Implements role-aware recovery: persistent agents (merge-queue, PR shepherd,
    supervisor) auto-restart on failure; transient agents (worker, reviewer)
    clean up.
    """
    from . import lifecycle

    for task in list(_tasks.values()):
        if task.status != TaskStatus.RUNNING:
            continue

        session = lifecycle.get_session(task.session_name)
        if not session:
            agent_def = get_agent(task.agent_name)
            if agent_def and agent_def.persistent:
                log.info(
                    "router.persistent_agent_restart",
                    metadata={"task_id": task.id, "agent": task.agent_name},
                )
                try:
                    await _restart_persistent_task(task)
                except Exception as exc:
                    log.error(
                        "router.restart_failed",
                        metadata={"task_id": task.id, "reason": str(exc)},
                    )
                    await fail_task(task.id, f"Restart failed: {exc}")
            else:
                await fail_task(task.id, "Container no longer exists")
            continue

        from .models import SessionState

        if session.state == SessionState.RECYCLED:
            await fail_task(task.id, "Container was recycled externally")


async def _restart_persistent_task(task: Task) -> None:
    """Restart a persistent agent's container after failure."""
    from . import lifecycle

    agent_def = get_agent(task.agent_name)
    if not agent_def:
        raise ValueError(f"Agent '{task.agent_name}' not found for restart")

    # Reuse session name for continuity
    ttl = settings.hub.persistent_token_ttl
    token = issue_token(task.agent_name, task.id, ttl=ttl)
    task.token_id = token.token_id
    task.updated_at = _now_ms()

    await lifecycle.run_pipeline(
        session_name=task.session_name,
        role=task.agent_name,
        hardened=agent_def.hardened,
        token=token,
        repo_url=task.repo_url,
    )

    log.info(
        "router.persistent_agent_restarted",
        metadata={"task_id": task.id, "session": task.session_name},
    )
    _emit("task.restarted", task)


# ---------------------------------------------------------------------------
# Repository management
# ---------------------------------------------------------------------------


def _repo_name(url: str) -> str:
    """Derive a short repo name from a GitHub URL."""
    # https://github.com/owner/repo -> repo
    return url.rstrip("/").rsplit("/", 1)[-1]


def add_repo(
    url: str,
    *,
    name: str | None = None,
    merge_queue: bool = False,
    pr_shepherd: bool = False,
    target_branch: str = "main",
    is_fork: bool = False,
    upstream_url: str | None = None,
) -> Repository:
    """Register a repository for multi-agent management."""
    repo_name = name or _repo_name(url)
    if repo_name in _repos:
        raise ValueError(f"Repository '{repo_name}' already registered")

    repo = Repository(
        url=url,
        name=repo_name,
        merge_queue_enabled=merge_queue,
        pr_shepherd_enabled=pr_shepherd,
        target_branch=target_branch,
        is_fork=is_fork,
        upstream_url=upstream_url,
    )
    _repos[repo_name] = repo
    log.info(
        "router.repo_added",
        metadata={
            "name": repo_name,
            "url": url,
            "merge_queue": merge_queue,
            "pr_shepherd": pr_shepherd,
        },
    )
    return repo


def get_repo(name: str) -> Repository | None:
    return _repos.get(name)


def list_repos() -> list[Repository]:
    return list(_repos.values())


def remove_repo(name: str) -> bool:
    existed = name in _repos
    _repos.pop(name, None)
    if existed:
        log.info("router.repo_removed", metadata={"name": name})
    return existed


def update_repo(
    name: str,
    *,
    merge_queue: bool | None = None,
    pr_shepherd: bool | None = None,
    target_branch: str | None = None,
) -> Repository:
    repo = _repos.get(name)
    if not repo:
        raise ValueError(f"Repository '{name}' not found")
    if merge_queue is not None:
        repo.merge_queue_enabled = merge_queue
    if pr_shepherd is not None:
        repo.pr_shepherd_enabled = pr_shepherd
    if target_branch is not None:
        repo.target_branch = target_branch
    return repo


async def ensure_repo_agents(repo_name: str) -> list[Task]:
    """Ensure persistent agents (merge-queue, PR shepherd) are running for a repo."""
    repo = _repos.get(repo_name)
    if not repo:
        raise ValueError(f"Repository '{repo_name}' not found")

    launched: list[Task] = []

    if repo.merge_queue_enabled and "merge-queue" not in repo.containers:
        agent = get_agent("merge-queue")
        if agent:
            task = await submit_task(
                f"Merge queue for {repo.name}",
                "merge-queue",
                repo_url=repo.url,
            )
            launched.append(task)

    if repo.pr_shepherd_enabled and "pr-shepherd" not in repo.containers:
        agent = get_agent("pr-shepherd")
        if agent:
            task = await submit_task(
                f"PR shepherd for {repo.name}",
                "pr-shepherd",
                repo_url=repo.url,
            )
            launched.append(task)

    return launched


# ---------------------------------------------------------------------------
# State serialization
# ---------------------------------------------------------------------------


def get_state() -> dict:
    return {
        "tasks": [(tid, t.model_dump()) for tid, t in _tasks.items()],
        "repos": [(name, r.model_dump()) for name, r in _repos.items()],
    }


def restore_state(state: dict | None) -> None:
    if not state:
        return
    # Restore tasks
    if "tasks" in state:
        _terminal = {"completed", "failed", "cancelled"}
        for tid, data in state["tasks"]:
            task = Task(**data)
            if task.status in _terminal:
                continue
            _tasks[tid] = task
    # Restore repos
    if "repos" in state:
        for name, data in state["repos"]:
            _repos[name] = Repository(**data)


def _now_ms() -> int:
    return int(time.time() * 1000)
