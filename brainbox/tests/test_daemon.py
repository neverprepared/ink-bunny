"""Unit tests for daemon management."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brainbox.daemon import (
    DaemonAlreadyRunningError,
    DaemonError,
    DaemonManager,
    DaemonNotRunningError,
    DaemonStatus,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def daemon_manager(temp_config_dir: Path) -> DaemonManager:
    """Create a DaemonManager instance with temp config dir."""
    return DaemonManager(config_dir=temp_config_dir)


class TestDaemonManager:
    """Test suite for DaemonManager class."""

    def test_init(self, daemon_manager: DaemonManager, temp_config_dir: Path):
        """Test DaemonManager initialization."""
        assert daemon_manager.config_dir == temp_config_dir
        assert daemon_manager.pid_file == temp_config_dir / "brainbox.pid"
        assert daemon_manager.log_dir == temp_config_dir / "logs"
        assert daemon_manager.log_file == temp_config_dir / "logs" / "brainbox.log"

    def test_status_not_running_no_pid_file(self, daemon_manager: DaemonManager):
        """Test status when daemon is not running and no PID file exists."""
        status = daemon_manager.status()
        assert not status.running
        assert status.pid is None
        assert status.port is None
        assert status.host is None

    def test_status_stale_pid_file(self, daemon_manager: DaemonManager):
        """Test status with stale PID file (process doesn't exist)."""
        # Write PID file with non-existent process
        daemon_manager.pid_file.write_text(
            "99999\n9999\n127.0.0.1\n2026-01-01T00:00:00+00:00\n",
            encoding="utf-8",
        )

        status = daemon_manager.status()
        assert not status.running
        # Stale PID file should be cleaned up
        assert not daemon_manager.pid_file.exists()

    def test_status_malformed_pid_file(self, daemon_manager: DaemonManager):
        """Test status with malformed PID file."""
        daemon_manager.pid_file.write_text("invalid\n", encoding="utf-8")

        status = daemon_manager.status()
        assert not status.running
        # Malformed PID file should be cleaned up
        assert not daemon_manager.pid_file.exists()

    def test_status_running(self, daemon_manager: DaemonManager):
        """Test status when daemon is running."""
        # Use current process as a "running" daemon
        pid = os.getpid()
        started_at = datetime.now(timezone.utc).isoformat()
        daemon_manager.pid_file.write_text(
            f"{pid}\n9999\n127.0.0.1\n{started_at}\n",
            encoding="utf-8",
        )

        status = daemon_manager.status()
        assert status.running
        assert status.pid == pid
        assert status.port == 9999
        assert status.host == "127.0.0.1"
        assert status.started_at == started_at
        assert status.uptime_seconds is not None
        assert status.uptime_seconds >= 0

    def test_start_creates_log_directory(self, daemon_manager: DaemonManager):
        """Test that start creates the log directory."""
        assert not daemon_manager.log_dir.exists()

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            daemon_manager.start()

        assert daemon_manager.log_dir.exists()

    def test_start_writes_pid_file(self, daemon_manager: DaemonManager):
        """Test that start writes the PID file correctly."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            pid, msg = daemon_manager.start(host="0.0.0.0", port=8888)

        assert pid == 12345
        assert daemon_manager.pid_file.exists()

        content = daemon_manager.pid_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 4
        assert lines[0] == "12345"
        assert lines[1] == "8888"
        assert lines[2] == "0.0.0.0"
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(lines[3])

    def test_start_already_running(self, daemon_manager: DaemonManager):
        """Test that start raises error when daemon is already running."""
        # Use current process as a "running" daemon
        pid = os.getpid()
        started_at = datetime.now(timezone.utc).isoformat()
        daemon_manager.pid_file.write_text(
            f"{pid}\n9999\n127.0.0.1\n{started_at}\n",
            encoding="utf-8",
        )

        with pytest.raises(DaemonAlreadyRunningError) as exc_info:
            daemon_manager.start()

        assert exc_info.value.pid == pid
        assert exc_info.value.host == "127.0.0.1"
        assert exc_info.value.port == 9999

    def test_start_cleans_stale_pid_file(self, daemon_manager: DaemonManager):
        """Test that start cleans up stale PID file before starting."""
        # Write stale PID file
        daemon_manager.pid_file.write_text(
            "99999\n9999\n127.0.0.1\n2026-01-01T00:00:00+00:00\n",
            encoding="utf-8",
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            pid, msg = daemon_manager.start()

        assert pid == 12345
        # Should have new PID file
        content = daemon_manager.pid_file.read_text(encoding="utf-8")
        assert content.startswith("12345\n")

    def test_start_process_exits_immediately(self, daemon_manager: DaemonManager):
        """Test error when started process exits immediately."""
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.poll.return_value = 1  # Exit code 1

            mock_popen.return_value = mock_process

            with pytest.raises(DaemonError) as exc_info:
                daemon_manager.start()

            assert "exited immediately" in str(exc_info.value)

    def test_stop_not_running(self, daemon_manager: DaemonManager):
        """Test that stop raises error when daemon is not running."""
        with pytest.raises(DaemonNotRunningError):
            daemon_manager.stop()

    def test_stop_graceful_shutdown(self, daemon_manager: DaemonManager):
        """Test graceful shutdown sends SIGTERM and process exits."""
        # Mock a process that responds to SIGTERM
        pid = 12345
        started_at = datetime.now(timezone.utc).isoformat()
        daemon_manager.pid_file.write_text(
            f"{pid}\n9999\n127.0.0.1\n{started_at}\n",
            encoding="utf-8",
        )

        kill_calls = []

        def mock_kill(target_pid: int, sig: int):
            kill_calls.append((target_pid, sig))
            # Simulate process dying on first SIGTERM
            if sig == signal.SIGTERM:
                # First call to check if alive (sig=0) will succeed
                # Second call will fail (process dead)
                pass
            elif sig == 0:
                # Check if process alive - fail after SIGTERM sent
                if (target_pid, signal.SIGTERM) in kill_calls:
                    raise ProcessLookupError()

        with patch("os.kill", side_effect=mock_kill):
            msg = daemon_manager.stop(timeout=5)

        assert "stopped gracefully" in msg.lower()
        assert not daemon_manager.pid_file.exists()

        # Should have sent SIGTERM but not SIGKILL
        assert (pid, signal.SIGTERM) in kill_calls
        assert (pid, signal.SIGKILL) not in kill_calls

    def test_stop_force_kill(self, daemon_manager: DaemonManager):
        """Test force kill with SIGKILL after timeout."""
        # Create a process that ignores SIGTERM
        # We'll mock the kill to simulate this behavior
        pid = os.getpid()  # Use current process for testing
        started_at = datetime.now(timezone.utc).isoformat()
        daemon_manager.pid_file.write_text(
            f"{pid}\n9999\n127.0.0.1\n{started_at}\n",
            encoding="utf-8",
        )

        kill_calls = []

        def mock_kill(target_pid: int, sig: int):
            kill_calls.append((target_pid, sig))
            if sig == signal.SIGKILL:
                # Simulate process death on SIGKILL
                raise ProcessLookupError()

        with patch("os.kill", side_effect=mock_kill):
            with patch("time.sleep"):  # Speed up test
                msg = daemon_manager.stop(timeout=1)

        # Message should indicate stopped (may be "stopped" or "stopped forcefully")
        assert "stopped" in msg.lower()
        assert not daemon_manager.pid_file.exists()

        # Verify SIGTERM was sent first, then SIGKILL
        assert (pid, signal.SIGTERM) in kill_calls
        assert (pid, signal.SIGKILL) in kill_calls

    def test_stop_already_dead(self, daemon_manager: DaemonManager):
        """Test stop when process is already dead."""
        # Write PID file for dead process
        daemon_manager.pid_file.write_text(
            "99999\n9999\n127.0.0.1\n2026-01-01T00:00:00+00:00\n",
            encoding="utf-8",
        )

        # This should raise DaemonNotRunningError because status() will detect
        # the process is dead and return running=False
        with pytest.raises(DaemonNotRunningError):
            daemon_manager.stop()

    def test_restart_when_running(self, daemon_manager: DaemonManager):
        """Test restart when daemon is running."""
        with patch.object(daemon_manager, "stop") as mock_stop:
            with patch.object(daemon_manager, "start") as mock_start:
                mock_stop.return_value = "Stopped"
                mock_start.return_value = (12345, "Started")

                pid, msg = daemon_manager.restart(host="0.0.0.0", port=8888)

        assert pid == 12345
        assert "Stopped" in msg
        assert "Started" in msg
        mock_stop.assert_called_once()
        mock_start.assert_called_once_with(host="0.0.0.0", port=8888, reload=False)

    def test_restart_when_not_running(self, daemon_manager: DaemonManager):
        """Test restart when daemon is not running."""
        with patch.object(daemon_manager, "stop") as mock_stop:
            with patch.object(daemon_manager, "start") as mock_start:
                mock_stop.side_effect = DaemonNotRunningError()
                mock_start.return_value = (12345, "Started")

                pid, msg = daemon_manager.restart()

        assert pid == 12345
        assert "not running" in msg.lower()
        assert "Started" in msg

    def test_to_dict_not_running(self, daemon_manager: DaemonManager):
        """Test to_dict with not running status."""
        status = DaemonStatus(running=False, log_file=Path("/tmp/log.txt"))
        result = daemon_manager.to_dict(status)

        assert result["running"] is False
        assert result["log_file"] == "/tmp/log.txt"
        assert "pid" not in result
        assert "url" not in result

    def test_to_dict_running(self, daemon_manager: DaemonManager):
        """Test to_dict with running status."""
        status = DaemonStatus(
            running=True,
            pid=12345,
            port=9999,
            host="127.0.0.1",
            started_at="2026-02-18T10:00:00+00:00",
            uptime_seconds=3600,
            log_file=Path("/tmp/log.txt"),
        )
        result = daemon_manager.to_dict(status)

        assert result["running"] is True
        assert result["pid"] == 12345
        assert result["url"] == "http://127.0.0.1:9999"
        assert result["host"] == "127.0.0.1"
        assert result["port"] == 9999
        assert result["started_at"] == "2026-02-18T10:00:00+00:00"
        assert result["uptime_seconds"] == 3600
        assert result["log_file"] == "/tmp/log.txt"
