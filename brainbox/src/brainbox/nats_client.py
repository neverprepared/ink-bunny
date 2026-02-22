"""NATS client for container communication.

Provides pub/sub and request/reply messaging between the brainbox API
and container agents via NATS.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import nats
from nats.aio.client import Client as NATSClient

from .log import get_logger

log = get_logger()

_SUBJECT_PREFIX = "brainbox"


class BrainboxNATSClient:
    """Async NATS client for brainbox container messaging."""

    def __init__(self, nats_url: str = "nats://localhost:4222") -> None:
        self._url = nats_url
        self._nc: NATSClient | None = None
        self._subscriptions: list[Any] = []

    @property
    def is_connected(self) -> bool:
        return self._nc is not None and self._nc.is_connected

    async def connect(self) -> None:
        """Connect to the NATS server."""
        self._nc = await nats.connect(self._url)
        log.info("nats_client.connected", metadata={"url": self._url})

    async def disconnect(self) -> None:
        """Drain subscriptions and disconnect."""
        if self._nc and self._nc.is_connected:
            try:
                await self._nc.drain()
            except Exception as exc:
                log.warning("nats_client.drain_failed", metadata={"error": str(exc)})
            self._nc = None
        self._subscriptions.clear()

    async def subscribe_all_containers(self, subject: str, callback: Callable[[dict], Any]) -> None:
        """Subscribe to a subject across all containers.

        Listens on ``brainbox.*.{subject}`` (wildcard for session name).
        """
        if not self._nc:
            raise RuntimeError("Not connected to NATS")

        full_subject = f"{_SUBJECT_PREFIX}.*.{subject}"

        async def _handler(msg: Any) -> None:
            try:
                data = json.loads(msg.data.decode())
                result = callback(data)
                # Support both sync and async callbacks
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                log.warning(
                    "nats_client.handler_error",
                    metadata={"subject": full_subject, "error": str(exc)},
                )

        sub = await self._nc.subscribe(full_subject, cb=_handler)
        self._subscriptions.append(sub)
        log.debug("nats_client.subscribed", metadata={"subject": full_subject})

    async def publish_command(self, session_name: str, command: dict) -> None:
        """Publish a command to a specific container (fire-and-forget)."""
        if not self._nc:
            raise RuntimeError("Not connected to NATS")

        subject = f"{_SUBJECT_PREFIX}.{session_name}.commands"
        payload = json.dumps(command).encode()
        await self._nc.publish(subject, payload)

    async def send_command(self, session_name: str, command: dict, timeout: float = 30.0) -> dict:
        """Send a command and wait for a reply (request/reply pattern)."""
        if not self._nc:
            raise RuntimeError("Not connected to NATS")

        subject = f"{_SUBJECT_PREFIX}.{session_name}.commands"
        payload = json.dumps(command).encode()

        try:
            response = await self._nc.request(subject, payload, timeout=timeout)
            return json.loads(response.data.decode())
        except nats.errors.TimeoutError:
            raise TimeoutError(f"No response from {session_name} within {timeout}s")
