"""Integration tests for daemon CLI commands."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
import requests

from brainbox.daemon import DaemonManager


@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch) -> Path:
    """Create a temporary config directory and set it in environment."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    # Mock the config directory
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "developer"


def run_cli(*args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run brainbox CLI command.

    Args:
        *args: CLI arguments
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess result
    """
    cmd = ["python", "-m", "brainbox"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.integration
class TestDaemonCLI:
    """Integration tests for daemon CLI commands."""

    def test_start_and_stop_lifecycle(self, temp_config_dir: Path):
        """Test complete daemon lifecycle: start -> status -> stop."""
        port = 19999

        # Start daemon
        result = run_cli("api", "--daemon", "--port", str(port))
        assert result.returncode == 0
        assert "Daemon started successfully" in result.stdout
        assert f"http://127.0.0.1:{port}" in result.stdout

        try:
            # Wait for API to be ready
            time.sleep(2)

            # Check status
            result = run_cli("status")
            assert result.returncode == 0
            assert "✓ Daemon running" in result.stdout
            assert f"URL: http://127.0.0.1:{port}" in result.stdout
            assert "PID:" in result.stdout
            assert "Uptime:" in result.stdout

            # Test API is responding
            response = requests.get(f"http://127.0.0.1:{port}/api/sessions", timeout=5)
            assert response.status_code == 200

        finally:
            # Stop daemon
            result = run_cli("stop")
            assert result.returncode == 0
            assert "Daemon stopped" in result.stdout

        # Verify stopped
        result = run_cli("status")
        assert result.returncode == 0
        assert "✗ Daemon not running" in result.stdout

    def test_status_json_format(self, temp_config_dir: Path):
        """Test status --json output format."""
        port = 19998

        # Start daemon
        result = run_cli("api", "--daemon", "--port", str(port))
        assert result.returncode == 0

        try:
            time.sleep(2)

            # Get JSON status
            result = run_cli("status", "--json")
            assert result.returncode == 0

            status = json.loads(result.stdout)
            assert status["running"] is True
            assert "pid" in status
            assert status["url"] == f"http://127.0.0.1:{port}"
            assert status["host"] == "127.0.0.1"
            assert status["port"] == port
            assert "started_at" in status
            assert "uptime_seconds" in status
            assert "log_file" in status

        finally:
            run_cli("stop")

    def test_already_running_error(self, temp_config_dir: Path):
        """Test error when trying to start daemon that's already running."""
        port = 19997

        # Start daemon
        result = run_cli("api", "--daemon", "--port", str(port))
        assert result.returncode == 0

        try:
            time.sleep(1)

            # Try to start again
            result = run_cli("api", "--daemon", "--port", str(port))
            assert result.returncode == 1
            assert "already running" in result.stderr.lower()

        finally:
            run_cli("stop")

    def test_stop_not_running_error(self, temp_config_dir: Path):
        """Test error when trying to stop daemon that's not running."""
        result = run_cli("stop")
        assert result.returncode == 1
        assert "not running" in result.stderr.lower()

    def test_restart(self, temp_config_dir: Path):
        """Test daemon restart command."""
        port = 19996

        # Start daemon
        result = run_cli("api", "--daemon", "--port", str(port))
        assert result.returncode == 0

        try:
            time.sleep(2)

            # Get initial PID
            result = run_cli("status", "--json")
            initial_status = json.loads(result.stdout)
            initial_pid = initial_status["pid"]

            # Restart
            result = run_cli("restart", "--port", str(port))
            assert result.returncode == 0
            assert "stopped" in result.stdout.lower()
            assert "started" in result.stdout.lower()

            time.sleep(2)

            # Get new PID
            result = run_cli("status", "--json")
            new_status = json.loads(result.stdout)
            new_pid = new_status["pid"]

            # PIDs should be different
            assert new_pid != initial_pid

            # API should still be running
            response = requests.get(f"http://127.0.0.1:{port}/api/sessions", timeout=5)
            assert response.status_code == 200

        finally:
            run_cli("stop")

    def test_restart_not_running(self, temp_config_dir: Path):
        """Test restart when daemon is not running."""
        port = 19995

        # Restart (should start even if not running)
        result = run_cli("restart", "--port", str(port))
        assert result.returncode == 0
        assert "not running" in result.stdout.lower()
        assert "started" in result.stdout.lower()

        try:
            time.sleep(2)

            # Verify it's running
            result = run_cli("status")
            assert result.returncode == 0
            assert "✓ Daemon running" in result.stdout

        finally:
            run_cli("stop")

    def test_stale_pid_file_cleanup(self, temp_config_dir: Path):
        """Test that stale PID file is cleaned up on start."""
        port = 19994

        # Create stale PID file
        manager = DaemonManager(config_dir=temp_config_dir)
        manager.pid_file.parent.mkdir(parents=True, exist_ok=True)
        manager.pid_file.write_text(
            "99999\n19999\n127.0.0.1\n2026-01-01T00:00:00+00:00\n",
            encoding="utf-8",
        )

        # Start daemon (should clean up stale PID and start successfully)
        result = run_cli("api", "--daemon", "--port", str(port))
        assert result.returncode == 0
        assert "Daemon started successfully" in result.stdout

        try:
            time.sleep(2)

            # Verify it's running with correct PID
            result = run_cli("status", "--json")
            status = json.loads(result.stdout)
            assert status["running"] is True
            assert status["pid"] != 99999  # Not the stale PID

        finally:
            run_cli("stop")

    def test_log_file_creation(self, temp_config_dir: Path):
        """Test that log file is created and contains output."""
        port = 19993

        manager = DaemonManager(config_dir=temp_config_dir)

        # Start daemon
        result = run_cli("api", "--daemon", "--port", str(port))
        assert result.returncode == 0

        try:
            time.sleep(2)

            # Verify log file exists and has content
            assert manager.log_file.exists()
            log_content = manager.log_file.read_text()
            assert "Starting daemon" in log_content
            assert "uvicorn" in log_content.lower() or "application" in log_content.lower()

        finally:
            run_cli("stop")

    def test_custom_host(self, temp_config_dir: Path):
        """Test daemon with custom host binding."""
        port = 19992

        # Start daemon on 0.0.0.0
        result = run_cli("api", "--daemon", "--host", "0.0.0.0", "--port", str(port))
        assert result.returncode == 0

        try:
            time.sleep(2)

            # Check status shows correct host
            result = run_cli("status", "--json")
            status = json.loads(result.stdout)
            assert status["host"] == "0.0.0.0"

        finally:
            run_cli("stop")

    def test_graceful_shutdown(self, temp_config_dir: Path):
        """Test that daemon shuts down gracefully."""
        port = 19991

        # Start daemon
        result = run_cli("api", "--daemon", "--port", str(port))
        assert result.returncode == 0

        try:
            time.sleep(2)

            # Stop with explicit timeout
            start_time = time.time()
            result = run_cli("stop", "--timeout", "5")
            stop_duration = time.time() - start_time

            assert result.returncode == 0
            assert "stopped gracefully" in result.stdout.lower()
            # Should stop quickly (within timeout)
            assert stop_duration < 5

        except Exception:
            # Cleanup in case of failure
            run_cli("stop")
            raise
