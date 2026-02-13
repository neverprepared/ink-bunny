"""Message router with pending queue and capped audit log."""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Any

from .config import settings
from .log import get_logger
from .policy import evaluate_message
from .registry import list_tokens, validate_token

log = get_logger()

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

# Pending messages keyed by token_id
_pending: dict[str, list[dict[str, Any]]] = {}

# Audit log (capped ring buffer)
_message_log: deque[dict[str, Any]] = deque(maxlen=settings.hub.message_retention)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route(envelope: dict[str, Any]) -> dict[str, Any]:
    """Route a message envelope. Returns {delivered, message_id, message} or raises."""
    sender_token_id = envelope.get("sender_token_id")
    token = validate_token(sender_token_id) if sender_token_id else None

    if not token:
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": _now_ms(),
            "sender_token_id": sender_token_id,
            "recipient": envelope.get("recipient"),
            "type": envelope.get("type"),
            "status": "rejected",
            "reason": "invalid_token",
        }
        _message_log.append(entry)
        log.warning("messages.rejected", metadata=entry)
        raise ValueError("Invalid or expired token")

    check = evaluate_message(token, envelope.get("recipient", "hub"), envelope)
    if not check.allowed:
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": _now_ms(),
            "sender": token.agent_name,
            "sender_token_id": token.token_id,
            "recipient": envelope.get("recipient"),
            "type": envelope.get("type"),
            "status": "rejected",
            "reason": check.reason,
        }
        _message_log.append(entry)
        log.warning("messages.rejected", metadata=entry)
        raise ValueError(check.reason)

    message_id = str(uuid.uuid4())
    message = {
        "id": message_id,
        "timestamp": _now_ms(),
        "sender": token.agent_name,
        "sender_token_id": token.token_id,
        "task_id": token.task_id,
        "recipient": envelope.get("recipient", "hub"),
        "type": envelope.get("type"),
        "payload": envelope.get("payload"),
    }

    # Enqueue for recipient agent's tokens
    recipient = envelope.get("recipient")
    if recipient and recipient != "hub":
        recipient_tokens = [t for t in list_tokens() if t.agent_name == recipient]
        for rt in recipient_tokens:
            _pending.setdefault(rt.token_id, []).append(message)

    log_entry = {
        "id": message_id,
        "timestamp": message["timestamp"],
        "sender": token.agent_name,
        "recipient": message["recipient"],
        "type": envelope.get("type"),
        "status": "delivered",
    }
    _message_log.append(log_entry)
    log.info("messages.routed", metadata=log_entry)

    return {"delivered": True, "message_id": message_id, "message": message}


# ---------------------------------------------------------------------------
# Message retrieval
# ---------------------------------------------------------------------------


def get_messages(token_id: str) -> list[dict[str, Any]]:
    """Get and drain pending messages for a token."""
    msgs = _pending.pop(token_id, [])
    return msgs


def get_message_log(
    *,
    sender: str | None = None,
    recipient: str | None = None,
    status: str | None = None,
    since: int | None = None,
) -> list[dict[str, Any]]:
    """Get audit log, optionally filtered."""
    result = list(_message_log)
    if sender:
        result = [m for m in result if m.get("sender") == sender]
    if recipient:
        result = [m for m in result if m.get("recipient") == recipient]
    if status:
        result = [m for m in result if m.get("status") == status]
    if since:
        result = [m for m in result if m.get("timestamp", 0) >= since]
    return result


# ---------------------------------------------------------------------------
# State serialization
# ---------------------------------------------------------------------------


def get_state() -> dict:
    return {
        "pending": list(_pending.items()),
        "log": list(_message_log),
    }


def restore_state(state: dict | None) -> None:
    if not state:
        return
    # Only restore pending messages for tokens that are still valid
    if state.get("pending"):
        for token_id, msgs in state["pending"]:
            if validate_token(token_id):
                _pending[token_id] = msgs
    # Drop stale audit log — messages from previous sessions are not actionable
    # The log will rebuild naturally as new messages are routed


def _now_ms() -> int:
    return int(time.time() * 1000)
