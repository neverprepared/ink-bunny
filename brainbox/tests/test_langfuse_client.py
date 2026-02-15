"""Tests for LangFuse API client."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import httpx
import pytest

from brainbox.config import LangfuseSettings, settings
from brainbox.langfuse_client import (
    LangfuseError,
    ObservationResult,
    SessionSummary,
    TraceResult,
    _auth_header,
    _truncate,
    get_session_traces_summary,
    get_trace,
    health_check,
    list_traces,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class TestTraceResult:
    def test_fields(self):
        t = TraceResult(
            id="t1",
            name="tool_call",
            session_id="s1",
            timestamp="2025-01-01T00:00:00Z",
            status="ok",
        )
        assert t.id == "t1"
        assert t.name == "tool_call"
        assert t.status == "ok"

    def test_frozen(self):
        t = TraceResult(id="t1", name="n", session_id="s", timestamp="ts", status="ok")
        with pytest.raises(AttributeError):
            t.id = "other"  # type: ignore[misc]


class TestObservationResult:
    def test_defaults(self):
        o = ObservationResult(
            id="o1",
            trace_id="t1",
            name="Read",
            type="SPAN",
            start_time="2025-01-01T00:00:00Z",
        )
        assert o.end_time == ""
        assert o.status == "ok"
        assert o.level == "DEFAULT"


class TestSessionSummary:
    def test_defaults(self):
        s = SessionSummary(session_id="s1")
        assert s.total_traces == 0
        assert s.total_observations == 0
        assert s.error_count == 0
        assert s.tool_counts == {}


class TestLangfuseError:
    def test_message_format(self):
        err = LangfuseError("list_traces", "connection refused")
        assert "list_traces" in str(err)
        assert "connection refused" in str(err)

    def test_fields(self):
        err = LangfuseError("op", "reason")
        assert err.operation == "op"
        assert err.reason == "reason"

    def test_is_runtime_error(self):
        assert isinstance(LangfuseError("op", "r"), RuntimeError)


# ---------------------------------------------------------------------------
# LangfuseSettings
# ---------------------------------------------------------------------------


class TestLangfuseSettings:
    def test_defaults(self, monkeypatch):
        # Clear env vars that would trigger fallback
        for var in (
            "LANGFUSE_BASE_URL",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_API_PUBLIC_KEY",
            "LANGFUSE_API_SECRET_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        s = LangfuseSettings()
        assert s.mode == "warn"
        assert s.base_url == "http://localhost:3000"
        assert s.public_key == ""
        assert s.secret_key == ""

    def test_explicit_values(self):
        s = LangfuseSettings(
            mode="enforce",
            base_url="http://langfuse.example.com:3000",
            public_key="pk-lf-123",
            secret_key="sk-lf-456",
        )
        assert s.mode == "enforce"
        assert s.base_url == "http://langfuse.example.com:3000"
        assert s.public_key == "pk-lf-123"
        assert s.secret_key == "sk-lf-456"

    def test_invalid_mode_rejected(self):
        with pytest.raises(Exception):
            LangfuseSettings(mode="invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


class TestAuthHeader:
    def test_basic_auth_format(self, monkeypatch):
        monkeypatch.setattr(settings.langfuse, "public_key", "pk-test")
        monkeypatch.setattr(settings.langfuse, "secret_key", "sk-test")
        header = _auth_header()
        assert header.startswith("Basic ")
        decoded = base64.b64decode(header[6:]).decode()
        assert decoded == "pk-test:sk-test"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @patch("brainbox.langfuse_client._client")
    def test_healthy(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.get.return_value = MagicMock(status_code=200)
        mock_client_fn.return_value = mock_client

        assert health_check() is True

    @patch("brainbox.langfuse_client._client")
    def test_unhealthy(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("refused")
        mock_client_fn.return_value = mock_client

        assert health_check() is False

    @patch("brainbox.langfuse_client._client")
    def test_non_200(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.get.return_value = MagicMock(status_code=503)
        mock_client_fn.return_value = mock_client

        assert health_check() is False


# ---------------------------------------------------------------------------
# list_traces
# ---------------------------------------------------------------------------


class TestListTraces:
    @patch("brainbox.langfuse_client._client")
    def test_success(self, mock_client_fn):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "t1",
                    "name": "tool_call",
                    "sessionId": "s1",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "level": "DEFAULT",
                    "input": "hello",
                    "output": "world",
                },
                {
                    "id": "t2",
                    "name": "error_call",
                    "sessionId": "s1",
                    "timestamp": "2025-01-01T00:01:00Z",
                    "level": "ERROR",
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        results = list_traces("s1")

        assert len(results) == 2
        assert results[0].id == "t1"
        assert results[0].status == "ok"
        assert results[1].id == "t2"
        assert results[1].status == "error"

    @patch("brainbox.langfuse_client._client")
    def test_empty(self, mock_client_fn):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        results = list_traces("s1")
        assert results == []

    @patch("brainbox.langfuse_client._client")
    def test_http_error_raises(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("refused")
        mock_client_fn.return_value = mock_client

        with pytest.raises(LangfuseError, match="list_traces"):
            list_traces("s1")


# ---------------------------------------------------------------------------
# get_trace
# ---------------------------------------------------------------------------


class TestGetTrace:
    @patch("brainbox.langfuse_client._client")
    def test_success(self, mock_client_fn):
        mock_client = MagicMock()

        trace_resp = MagicMock()
        trace_resp.json.return_value = {
            "id": "t1",
            "name": "call",
            "sessionId": "s1",
            "timestamp": "ts",
            "level": "DEFAULT",
            "input": "",
            "output": "",
        }
        trace_resp.raise_for_status = MagicMock()

        obs_resp = MagicMock()
        obs_resp.json.return_value = {
            "data": [
                {
                    "id": "o1",
                    "name": "Read",
                    "type": "SPAN",
                    "startTime": "ts1",
                    "endTime": "ts2",
                    "level": "DEFAULT",
                },
            ]
        }
        obs_resp.raise_for_status = MagicMock()

        mock_client.get.side_effect = [trace_resp, obs_resp]
        mock_client_fn.return_value = mock_client

        trace, observations = get_trace("t1")

        assert trace.id == "t1"
        assert len(observations) == 1
        assert observations[0].name == "Read"


# ---------------------------------------------------------------------------
# get_session_traces_summary
# ---------------------------------------------------------------------------


class TestGetSessionTracesSummary:
    @patch("brainbox.langfuse_client._client")
    @patch("brainbox.langfuse_client.list_traces")
    def test_aggregation(self, mock_list, mock_client_fn):
        mock_list.return_value = [
            TraceResult(id="t1", name="a", session_id="s1", timestamp="ts", status="ok"),
            TraceResult(id="t2", name="b", session_id="s1", timestamp="ts", status="error"),
        ]

        mock_client = MagicMock()

        # Optimized code now makes a SINGLE batch call for all observations
        batch_obs_resp = MagicMock()
        batch_obs_resp.json.return_value = {
            "data": [
                {"traceId": "t1", "name": "Read", "level": "DEFAULT"},
                {"traceId": "t1", "name": "Write", "level": "DEFAULT"},
                {"traceId": "t2", "name": "Read", "level": "ERROR"},
            ]
        }
        batch_obs_resp.raise_for_status = MagicMock()

        mock_client.get.return_value = batch_obs_resp
        mock_client_fn.return_value = mock_client

        summary = get_session_traces_summary("s1")

        assert summary.session_id == "s1"
        assert summary.total_traces == 2
        assert summary.total_observations == 3
        # 1 error from trace status + 1 error from observation level
        assert summary.error_count == 2
        assert summary.tool_counts["Read"] == 2
        assert summary.tool_counts["Write"] == 1

        # Verify it made a single batch call with sessionId parameter
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["sessionId"] == "s1"


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------


class TestTruncate:
    def test_short_string(self):
        assert _truncate("hello") == "hello"

    def test_long_string(self):
        s = "x" * 300
        result = _truncate(s, max_len=200)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_exact_limit(self):
        s = "x" * 200
        assert _truncate(s, max_len=200) == s
