"""MCP server exposing brainbox API as tools.

Stateless protocol adapter — each tool is an HTTP call to the
brainbox FastAPI backend.

Usage:
    brainbox mcp                    # stdio transport (default)
    brainbox mcp --url http://host:9999  # custom API URL
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("brainbox")


def _api_url() -> str:
    return os.environ.get("BRAINBOX_URL", "http://127.0.0.1:9999")


def _api_key() -> str:
    """Load API key from CL_API_KEY env, or from key file on disk."""
    key = os.environ.get("CL_API_KEY", "")
    if key:
        return key
    key_file = Path.home() / ".config" / "developer" / ".api-key"
    if key_file.exists():
        return key_file.read_text().strip()
    return ""


def _request_raw(
    method: str, path: str, data: bytes, content_type: str = "text/plain", timeout: int = 30
) -> Any:
    """Make an HTTP request with raw bytes body."""
    url = f"{_api_url()}{path}"
    headers = {"Content-Type": content_type}
    key = _api_key()
    if key:
        headers["X-API-Key"] = key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def _request(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    """Make an HTTP request to the brainbox API."""
    url = f"{_api_url()}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    key = _api_key()
    if key:
        headers["X-API-Key"] = key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
    return _request(
        "POST",
        "/api/hub/tasks",
        {
            "description": description,
            "agent_name": agent_name,
        },
    )


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


@mcp.tool()
def get_session(name: str) -> dict[str, Any]:
    """Get info for a single session by name.

    Args:
        name: Session name (e.g. test-1)
    """
    return _request("GET", f"/api/sessions/{name}")


@mcp.tool()
def exec_session(name: str, command: str) -> dict[str, Any]:
    """Execute a shell command inside a running container session.

    Args:
        name: Session name (e.g. test-1)
        command: Shell command to run (e.g. "pytest tests/", "git status")
    """
    return _request("POST", f"/api/sessions/{name}/exec", {"command": command})


@mcp.tool()
def query_session(
    name: str,
    prompt: str,
    timeout: int = 300,
) -> dict[str, Any]:
    """Send a prompt to Claude Code running in a container session.

    Args:
        name: Session name (e.g. test-1)
        prompt: The prompt/task to execute in the container
        timeout: Maximum seconds to wait for response (default: 300)
    """
    body: dict[str, Any] = {"prompt": prompt, "timeout": timeout}
    return _request("POST", f"/api/sessions/{name}/query", body, timeout=timeout + 10)


@mcp.tool()
def cancel_task(task_id: str) -> dict[str, Any]:
    """Cancel a pending or running task.

    Args:
        task_id: The task ID to cancel
    """
    return _request("DELETE", f"/api/hub/tasks/{task_id}")


@mcp.tool()
def get_langfuse_health() -> dict[str, Any]:
    """Check LangFuse observability service health and connectivity."""
    return _request("GET", "/api/langfuse/health")


@mcp.tool()
def get_qdrant_health() -> dict[str, Any]:
    """Check Qdrant vector database health and connectivity."""
    return _request("GET", "/api/qdrant/health")


@mcp.tool()
def list_agents() -> list[dict[str, Any]]:
    """List all registered agents in the hub."""
    return _request("GET", "/api/hub/agents")


@mcp.tool()
def get_agent(name: str) -> dict[str, Any]:
    """Get info for a single registered hub agent.

    Args:
        name: Agent name (e.g. developer)
    """
    return _request("GET", f"/api/hub/agents/{name}")


@mcp.tool()
def list_tokens() -> list[dict[str, Any]]:
    """List all registered hub tokens (agent identities)."""
    return _request("GET", "/api/hub/tokens")


@mcp.tool()
def refresh_secrets(name: str) -> dict[str, Any]:
    """Re-inject secrets into a running container session from the host environment.

    Args:
        name: Session name (e.g. test-1)
    """
    return _request("POST", f"/api/sessions/{name}/refresh-secrets")


@mcp.tool()
def api_info() -> dict[str, Any]:
    """Get API version and basic health status."""
    return _request("GET", "/api/info")


# ---------------------------------------------------------------------------
# Artifact tools
# ---------------------------------------------------------------------------


@mcp.tool()
def artifact_health() -> dict[str, Any]:
    """Check artifact storage (MinIO) health and connectivity."""
    return _request("GET", "/api/artifacts/health")


@mcp.tool()
def list_artifacts(prefix: str = "") -> list[dict[str, Any]]:
    """List stored artifacts, optionally filtered by key prefix.

    Args:
        prefix: Key prefix to filter by (e.g. "myproject/")
    """
    path = "/api/artifacts"
    if prefix:
        path += f"?prefix={prefix}"
    return _request("GET", path)


@mcp.tool()
def upload_artifact(key: str, content: str) -> dict[str, Any]:
    """Upload a text artifact to storage.

    Args:
        key: Storage key / path (e.g. "myproject/report.md")
        content: Text content to store
    """
    return _request_raw(
        "POST", f"/api/artifacts/{key}", content.encode(), content_type="text/plain"
    )


@mcp.tool()
def download_artifact(key: str) -> dict[str, Any]:
    """Download an artifact from storage.

    Args:
        key: Storage key / path (e.g. "myproject/report.md")
    """
    return _request("GET", f"/api/artifacts/{key}")


@mcp.tool()
def delete_artifact(key: str) -> dict[str, Any]:
    """Delete an artifact from storage.

    Args:
        key: Storage key / path (e.g. "myproject/report.md")
    """
    return _request("DELETE", f"/api/artifacts/{key}")


# ---------------------------------------------------------------------------
# LangFuse trace tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_langfuse_session_traces(session_name: str, limit: int = 50) -> list[dict[str, Any]]:
    """List LangFuse traces for a container session.

    Args:
        session_name: Session name (e.g. test-1)
        limit: Maximum number of traces to return (default: 50)
    """
    return _request("GET", f"/api/langfuse/sessions/{session_name}/traces?limit={limit}")


@mcp.tool()
def get_langfuse_session_summary(session_name: str) -> dict[str, Any]:
    """Get trace count, error count, and tool breakdown for a session.

    Args:
        session_name: Session name (e.g. test-1)
    """
    return _request("GET", f"/api/langfuse/sessions/{session_name}/summary")


@mcp.tool()
def get_langfuse_trace_detail(trace_id: str) -> dict[str, Any]:
    """Get full detail for a single LangFuse trace including observations.

    Args:
        trace_id: LangFuse trace ID
    """
    return _request("GET", f"/api/langfuse/traces/{trace_id}")


def run() -> None:
    """Run the MCP server on stdio transport."""
    mcp.run(transport="stdio")
