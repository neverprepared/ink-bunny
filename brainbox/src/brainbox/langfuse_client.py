"""LangFuse API client for querying traces and observations."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field

import httpx

from .config import settings
from .log import get_logger

_log = get_logger()

# ---------------------------------------------------------------------------
# Cached HTTPx client for connection pooling
# ---------------------------------------------------------------------------

_httpx_client: httpx.Client | None = None


@dataclass(frozen=True)
class TraceResult:
    id: str
    name: str
    session_id: str
    timestamp: str
    status: str  # "ok" or "error"
    input: str = ""
    output: str = ""


@dataclass(frozen=True)
class ObservationResult:
    id: str
    trace_id: str
    name: str
    type: str  # "SPAN", "GENERATION", "EVENT"
    start_time: str
    end_time: str = ""
    status: str = "ok"
    level: str = "DEFAULT"  # DEFAULT, DEBUG, WARNING, ERROR


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    total_traces: int = 0
    total_observations: int = 0
    error_count: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)


class LangfuseError(RuntimeError):
    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(f"langfuse {operation} failed: {reason}")


def _auth_header() -> str:
    """Build HTTP Basic Auth header from public_key:secret_key."""
    creds = f"{settings.langfuse.public_key}:{settings.langfuse.secret_key}"
    encoded = base64.b64encode(creds.encode()).decode()
    return f"Basic {encoded}"


def _client() -> httpx.Client:
    """Get cached httpx client with connection pooling and auth."""
    global _httpx_client
    if _httpx_client is None:
        base_url = settings.langfuse.base_url
        if base_url.startswith("http://") and not base_url.startswith("http://localhost"):
            _log.warning(
                "langfuse.insecure_connection",
                metadata={
                    "base_url": base_url,
                    "detail": "HTTP Basic Auth credentials sent in cleartext over HTTP",
                },
            )
        _httpx_client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": _auth_header()},
            timeout=10.0,
        )
    return _httpx_client


def health_check() -> bool:
    """Check if LangFuse is reachable."""
    try:
        c = _client()
        resp = c.get("/api/public/health")
        return resp.status_code == 200
    except Exception:
        return False


def list_traces(session_id: str, limit: int = 50) -> list[TraceResult]:
    """List traces for a session."""
    try:
        c = _client()
        resp = c.get(
            "/api/public/traces",
            params={"sessionId": session_id, "limit": limit},
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for t in data.get("data", []):
            # Determine status from observations or metadata
            status = "error" if t.get("level") == "ERROR" else "ok"
            results.append(
                TraceResult(
                    id=t["id"],
                    name=t.get("name", ""),
                    session_id=t.get("sessionId", session_id),
                    timestamp=t.get("timestamp", ""),
                    status=status,
                    input=_truncate(str(t.get("input", ""))),
                    output=_truncate(str(t.get("output", ""))),
                )
            )
        return results
    except httpx.HTTPError as exc:
        raise LangfuseError("list_traces", str(exc))


def get_trace(trace_id: str) -> tuple[TraceResult, list[ObservationResult]]:
    """Get a single trace with its observations."""
    try:
        c = _client()
        trace_resp = c.get(f"/api/public/traces/{trace_id}")
        trace_resp.raise_for_status()
        t = trace_resp.json()

        obs_resp = c.get(
            "/api/public/observations",
            params={"traceId": trace_id, "limit": 100},
        )
        obs_resp.raise_for_status()
        obs_data = obs_resp.json()

        status = "error" if t.get("level") == "ERROR" else "ok"
        trace = TraceResult(
            id=t["id"],
            name=t.get("name", ""),
            session_id=t.get("sessionId", ""),
            timestamp=t.get("timestamp", ""),
            status=status,
            input=_truncate(str(t.get("input", ""))),
            output=_truncate(str(t.get("output", ""))),
        )

        observations = []
        for o in obs_data.get("data", []):
            observations.append(
                ObservationResult(
                    id=o["id"],
                    trace_id=trace_id,
                    name=o.get("name", ""),
                    type=o.get("type", "SPAN"),
                    start_time=o.get("startTime", ""),
                    end_time=o.get("endTime", ""),
                    status="error" if o.get("level") == "ERROR" else "ok",
                    level=o.get("level", "DEFAULT"),
                )
            )
        return trace, observations
    except httpx.HTTPError as exc:
        raise LangfuseError("get_trace", str(exc))


def get_session_traces_summary(session_id: str) -> SessionSummary:
    """Aggregate trace/observation counts for a session.

    Optimized to batch-fetch all observations in a single API call instead of
    N+1 queries (one per trace).
    """
    try:
        traces = list_traces(session_id, limit=100)
        total_traces = len(traces)
        error_count = sum(1 for t in traces if t.status == "error")

        # Build a set of trace IDs for filtering observations
        trace_ids = {t.id for t in traces}

        # Batch-fetch ALL observations for the session in a single API call
        tool_counts: dict[str, int] = {}
        total_observations = 0

        c = _client()
        try:
            # Fetch all observations for this session (single API call)
            obs_resp = c.get(
                "/api/public/observations",
                params={"sessionId": session_id, "limit": 1000},
            )
            obs_resp.raise_for_status()
            obs_data = obs_resp.json()

            # Process observations, filtering to only those in our trace set
            for o in obs_data.get("data", []):
                # Only count observations that belong to the traces we fetched
                if o.get("traceId") in trace_ids:
                    total_observations += 1
                    name = o.get("name", "unknown")
                    tool_counts[name] = tool_counts.get(name, 0) + 1
                    if o.get("level") == "ERROR":
                        error_count += 1
        except Exception:
            # If batch fetch fails, return partial data from traces
            pass

        return SessionSummary(
            session_id=session_id,
            total_traces=total_traces,
            total_observations=total_observations,
            error_count=error_count,
            tool_counts=tool_counts,
        )
    except LangfuseError:
        raise
    except Exception as exc:
        raise LangfuseError("get_session_traces_summary", str(exc))


def _truncate(s: str, max_len: int = 200) -> str:
    """Truncate a string for preview display."""
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."
