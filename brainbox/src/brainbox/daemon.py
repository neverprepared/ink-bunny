"""Daemon management for running brainbox API server in the background."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings
from .log import get_logger

log = get_logger()


@dataclass
class DaemonStatus:
    """Status information for the daemon process."""

    running: bool
    pid: int | None = None
    port: int | None = None
    host: str | None = None
    started_at: str | None = None
    uptime_seconds: int | None = None
    log_file: Path | None = None


class DaemonError(Exception):
    """Base exception for daemon-related errors."""

    pass


class DaemonAlreadyRunningError(DaemonError):
    """Raised when attempting to start a daemon that's already running."""

    def __init__(self, pid: int, host: str, port: int):
        self.pid = pid
        self.host = host
        self.port = port
        super().__init__(f"Daemon already running (PID {pid}) at http://{host}:{port}")


class DaemonNotRunningError(DaemonError):
    """Raised when attempting to stop a daemon that's not running."""

    def __init__(self):
        super().__init__("Daemon not running")


class DaemonManager:
    """Manages the lifecycle of the brainbox API daemon process."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize the daemon manager.

        Args:
            config_dir: Configuration directory (defaults to settings.config_dir)
        """
        self.config_dir = config_dir or settings.config_dir
        self.pid_file = self.config_dir / "brainbox.pid"
        self.log_dir = self.config_dir / "logs"
        self.log_file = self.log_dir / "brainbox.log"

    def start(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        reload: bool = False,
    ) -> tuple[int, str]:
        """Start the daemon process.

        Args:
            host: Host to bind to
            port: Port to bind to
            reload: Enable auto-reload on code changes

        Returns:
            Tuple of (pid, message)

        Raises:
            DaemonAlreadyRunningError: If daemon is already running
            DaemonError: If daemon fails to start
        """
        # Check if already running
        status = self.status()
        if status.running:
            raise DaemonAlreadyRunningError(status.pid, status.host, status.port)

        # Clean up stale PID file
        if self.pid_file.exists():
            self.pid_file.unlink()

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [
            sys.executable,
            "-m",
            "brainbox",
            "api",
            "--host",
            host,
            "--port",
            str(port),
        ]
        if reload:
            cmd.append("--reload")

        # Start process in background
        try:
            with open(self.log_file, "a") as log:
                log.write(f"\n{'=' * 80}\n")
                log.write(f"Starting daemon at {datetime.now(timezone.utc).isoformat()}\n")
                log.write(f"Command: {' '.join(cmd)}\n")
                log.write(f"{'=' * 80}\n\n")
                log.flush()

                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    cwd=os.getcwd(),
                )
        except Exception as e:
            raise DaemonError(f"Failed to start daemon: {e}") from e

        # Wait a moment to check if process started successfully
        time.sleep(0.5)
        poll_result = process.poll()
        if poll_result is not None:
            # Process already exited
            raise DaemonError(
                f"Daemon process exited immediately with code {poll_result}. "
                f"Check logs at {self.log_file}"
            )

        # Write PID file
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            self.pid_file.write_text(
                f"{process.pid}\n{port}\n{host}\n{started_at}\n",
                encoding="utf-8",
            )
        except Exception as e:
            # Kill the process if we can't write PID file
            try:
                process.kill()
            except Exception as kill_exc:
                log.debug("daemon.kill_failed", metadata={"reason": str(kill_exc)})
            raise DaemonError(f"Failed to write PID file: {e}") from e

        url = f"http://{host}:{port}"
        message = (
            f"Daemon started successfully\n"
            f"  PID: {process.pid}\n"
            f"  URL: {url}\n"
            f"  Logs: {self.log_file}"
        )

        return process.pid, message

    def stop(self, timeout: int = 10) -> str:
        """Stop the daemon process.

        Args:
            timeout: Maximum time to wait for graceful shutdown (seconds)

        Returns:
            Success message

        Raises:
            DaemonNotRunningError: If daemon is not running
            DaemonError: If daemon fails to stop
        """
        status = self.status()
        if not status.running:
            raise DaemonNotRunningError()

        pid = status.pid

        # Try graceful shutdown with SIGTERM
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            # Process already gone
            self._cleanup_pid_file()
            return f"Daemon stopped (PID {pid})"
        except Exception as e:
            raise DaemonError(f"Failed to send SIGTERM to process {pid}: {e}") from e

        # Wait for process to exit
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                os.kill(pid, 0)  # Check if process exists
                time.sleep(0.1)
            except ProcessLookupError:
                # Process is gone
                self._cleanup_pid_file()
                return f"Daemon stopped gracefully (PID {pid})"

        # Force kill with SIGKILL
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            # Already gone
            self._cleanup_pid_file()
            return f"Daemon stopped (PID {pid})"
        except Exception as e:
            raise DaemonError(f"Failed to send SIGKILL to process {pid}: {e}") from e

        # Wait for process to die after SIGKILL
        kill_deadline = time.time() + 2  # Give it 2 more seconds
        while time.time() < kill_deadline:
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                # Process is gone
                break

        self._cleanup_pid_file()
        return f"Daemon stopped forcefully (PID {pid})"

    def status(self) -> DaemonStatus:
        """Get the current status of the daemon.

        Returns:
            DaemonStatus object with current state
        """
        if not self.pid_file.exists():
            return DaemonStatus(
                running=False,
                log_file=self.log_file if self.log_file.exists() else None,
            )

        # Read PID file
        try:
            content = self.pid_file.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            if len(lines) < 4:
                # Malformed PID file
                self._cleanup_pid_file()
                return DaemonStatus(running=False, log_file=self.log_file)

            pid = int(lines[0])
            port = int(lines[1])
            host = lines[2]
            started_at = lines[3]
        except Exception as exc:
            log.debug("daemon.pid_file_corrupt", metadata={"reason": str(exc)})
            self._cleanup_pid_file()
            return DaemonStatus(running=False, log_file=self.log_file)

        # Check if process is running
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
        except ProcessLookupError:
            # Process is dead, clean up stale PID file
            self._cleanup_pid_file()
            return DaemonStatus(running=False, log_file=self.log_file)
        except Exception:
            # Permission denied or other error - assume running
            pass

        # Calculate uptime
        try:
            started = datetime.fromisoformat(started_at)
            now = datetime.now(timezone.utc)
            uptime_seconds = int((now - started).total_seconds())
        except Exception as exc:
            log.debug("daemon.uptime_parse_failed", metadata={"reason": str(exc)})
            uptime_seconds = None

        return DaemonStatus(
            running=True,
            pid=pid,
            port=port,
            host=host,
            started_at=started_at,
            uptime_seconds=uptime_seconds,
            log_file=self.log_file if self.log_file.exists() else None,
        )

    def restart(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        reload: bool = False,
    ) -> tuple[int, str]:
        """Restart the daemon process.

        Args:
            host: Host to bind to
            port: Port to bind to
            reload: Enable auto-reload on code changes

        Returns:
            Tuple of (pid, message)

        Raises:
            DaemonError: If restart fails
        """
        # Try to stop if running
        try:
            stop_msg = self.stop()
        except DaemonNotRunningError:
            stop_msg = "Daemon was not running"

        # Wait a moment before starting
        time.sleep(0.5)

        # Start
        pid, start_msg = self.start(host=host, port=port, reload=reload)

        message = f"{stop_msg}\n{start_msg}"
        return pid, message

    def _cleanup_pid_file(self) -> None:
        """Remove the PID file if it exists."""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception as exc:
            log.debug("daemon.cleanup_failed", metadata={"reason": str(exc)})

    def to_dict(self, status: DaemonStatus) -> dict[str, Any]:
        """Convert status to dictionary format.

        Args:
            status: DaemonStatus object

        Returns:
            Dictionary representation
        """
        result: dict[str, Any] = {
            "running": status.running,
        }

        if status.running:
            result["pid"] = status.pid
            result["url"] = f"http://{status.host}:{status.port}"
            result["host"] = status.host
            result["port"] = status.port
            result["started_at"] = status.started_at
            result["uptime_seconds"] = status.uptime_seconds

        if status.log_file:
            result["log_file"] = str(status.log_file)

        return result
