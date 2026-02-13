"""MCP server exposing brainbox API as tools.

Stateless protocol adapter — each tool is an HTTP call to the
brainbox FastAPI backend.

Usage:
    brainbox mcp                    # stdio transport (default)
    brainbox mcp --url http://host:8000  # custom API URL
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("brainbox")


def _api_url() -> str:
    return os.environ.get("BRAINBOX_URL", "http://127.0.0.1:8000")


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Make an HTTP request to the brainbox API."""
    url = f"{_api_url()}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else str(exc)
        try:
            detail = json.loads(detail).get("detail", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        return {"error": detail, "status": exc.code}
    except urllib.error.URLError as exc:
        return {"error": f"Cannot reach API at {url}: {exc.reason}"}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_sessions() -> list[dict[str, Any]]:
    """List all container sessions with their ports, volumes, and status."""
    return _request("GET", "/api/sessions")


@mcp.tool()
def create_session(name: str = "default", volume: str | None = None) -> dict[str, Any]:
    """Create and start a new container session.

    Args:
        name: Session name (container will be named developer-{name})
        volume: Optional host:container volume mount (e.g. /path/to/code:/workspace)
    """
    body: dict[str, Any] = {"name": name}
    if volume:
        body["volume"] = volume
    return _request("POST", "/api/create", body)


@mcp.tool()
def start_session(name: str) -> dict[str, Any]:
    """Start an existing stopped container session.

    Args:
        name: Container name (e.g. developer-default)
    """
    return _request("POST", "/api/start", {"name": name})


@mcp.tool()
def stop_session(name: str) -> dict[str, Any]:
    """Stop a running container session.

    Args:
        name: Container name (e.g. developer-default)
    """
    return _request("POST", "/api/stop", {"name": name})


@mcp.tool()
def delete_session(name: str) -> dict[str, Any]:
    """Delete a container session (stops and removes the container).

    Args:
        name: Container name (e.g. developer-default)
    """
    return _request("POST", "/api/delete", {"name": name})


@mcp.tool()
def get_metrics() -> list[dict[str, Any]]:
    """Get per-container CPU %, memory usage, and uptime for all running sessions."""
    return _request("GET", "/api/metrics/containers")


@mcp.tool()
def submit_task(description: str, agent_name: str = "developer") -> dict[str, Any]:
    """Submit a task to the hub for execution in an isolated container.

    Args:
        description: Task description / instructions for the agent
        agent_name: Agent to assign the task to (default: developer)
    """
    return _request("POST", "/api/hub/tasks", {
        "description": description,
        "agent_name": agent_name,
    })


@mcp.tool()
def get_task(task_id: str) -> dict[str, Any]:
    """Get the status and result of a submitted task.

    Args:
        task_id: The task ID returned by submit_task
    """
    return _request("GET", f"/api/hub/tasks/{task_id}")


@mcp.tool()
def list_tasks(status: str | None = None) -> list[dict[str, Any]]:
    """List hub tasks, optionally filtered by status.

    Args:
        status: Filter by status (pending, running, completed, failed, cancelled)
    """
    path = "/api/hub/tasks"
    if status:
        path += f"?status={status}"
    return _request("GET", path)


@mcp.tool()
def get_hub_state() -> dict[str, Any]:
    """Get full hub state: agents, tasks, tokens, and message log."""
    return _request("GET", "/api/hub/state")


def run() -> None:
    """Run the MCP server on stdio transport."""
    mcp.run(transport="stdio")
