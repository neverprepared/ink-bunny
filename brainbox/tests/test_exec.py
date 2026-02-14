"""Tests for container command execution endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from brainbox.api import app
from brainbox.config import settings


class TestExecEndpoint:
    @pytest.fixture()
    def client(self):
        from httpx import ASGITransport, AsyncClient

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.asyncio
    async def test_success(self, client):
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"hello world\n")

        with patch("brainbox.api.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = mock_container
            resp = await client.post(
                "/api/sessions/test-1/exec",
                json={"command": "echo hello world"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["exit_code"] == 0
        assert data["output"] == "hello world\n"

        mock_container.exec_run.assert_called_once_with(["sh", "-c", "echo hello world"])

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self, client):
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (1, b"not found\n")

        with patch("brainbox.api.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = mock_container
            resp = await client.post(
                "/api/sessions/test-1/exec",
                json={"command": "ls /nonexistent"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["exit_code"] == 1

    @pytest.mark.asyncio
    async def test_container_not_found(self, client):
        with patch("brainbox.api.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.side_effect = docker.errors.NotFound(
                "not found"
            )
            mock_docker.errors = docker.errors
            resp = await client.post(
                "/api/sessions/nope/exec",
                json={"command": "echo hi"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_command(self, client):
        resp = await client.post(
            "/api/sessions/test-1/exec",
            json={},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_empty_command(self, client):
        resp = await client.post(
            "/api/sessions/test-1/exec",
            json={"command": "   "},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_container_name_uses_prefix(self, client):
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"ok\n")

        with patch("brainbox.api.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = mock_container
            await client.post(
                "/api/sessions/mybox/exec",
                json={"command": "echo ok"},
            )

        expected_name = f"{settings.resolved_prefix}mybox"
        mock_docker.from_env.return_value.containers.get.assert_called_once_with(expected_name)
