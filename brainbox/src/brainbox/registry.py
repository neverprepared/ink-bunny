"""Agent registry and token issuance."""

from __future__ import annotations

import json
import stat
import time
import uuid

from .config import settings
from .log import get_logger
from .models import AgentDefinition, Token

log = get_logger()

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_agents: dict[str, AgentDefinition] = {}
_tokens: dict[str, Token] = {}
_last_token_sweep: float = 0.0


# ---------------------------------------------------------------------------
# Agent loading
# ---------------------------------------------------------------------------


def load_agents() -> dict[str, AgentDefinition]:
    _agents.clear()
    agents_dir = settings.agents_dir

    if not agents_dir.is_dir():
        log.warning("registry.no_agents_dir", metadata={"dir": str(agents_dir)})
        return _agents

    for f in sorted(agents_dir.iterdir()):
        if not f.suffix == ".json":
            continue
        try:
            # Check file permissions — warn if world-writable
            mode = f.stat().st_mode
            if mode & stat.S_IWOTH:
                log.warning(
                    "registry.agent_world_writable",
                    metadata={"file": f.name, "mode": oct(mode)},
                )
                # Enforce safe permissions — strip world-write bit
                f.chmod(mode & ~stat.S_IWOTH)

            raw = json.loads(f.read_text())

            # Validate required fields
            if not raw.get("name") or not raw.get("image"):
                log.warning(
                    "registry.agent_missing_fields",
                    metadata={
                        "file": f.name,
                        "has_name": bool(raw.get("name")),
                        "has_image": bool(raw.get("image")),
                    },
                )
                continue

            agent = AgentDefinition(**raw)
            _agents[agent.name] = agent
            log.info("registry.agent_loaded", metadata={"name": agent.name, "file": f.name})
        except Exception as exc:
            log.warning("registry.agent_load_failed", metadata={"file": f.name, "reason": str(exc)})

    return _agents


def get_agent(name: str) -> AgentDefinition | None:
    return _agents.get(name)


def list_agents() -> list[AgentDefinition]:
    return list(_agents.values())


# ---------------------------------------------------------------------------
# Token issuance
# ---------------------------------------------------------------------------


def issue_token(agent_name: str, task_id: str, ttl: int = 3600) -> Token:
    agent = _agents.get(agent_name)
    if not agent:
        raise ValueError(f"Agent '{agent_name}' not registered")

    now = int(time.time() * 1000)
    token = Token(
        token_id=str(uuid.uuid4()),
        agent_name=agent_name,
        task_id=task_id,
        capabilities=list(agent.capabilities),
        issued=now,
        expiry=now + ttl * 1000,
    )

    _tokens[token.token_id] = token
    log.info(
        "registry.token_issued",
        metadata={
            "token_id": token.token_id,
            "agent_name": agent_name,
            "task_id": task_id,
            "ttl": ttl,
        },
    )
    return token


def validate_token(token_id: str) -> Token | None:
    token = _tokens.get(token_id)
    if not token:
        return None
    now = int(time.time() * 1000)
    if now > token.expiry:
        _tokens.pop(token_id, None)
        return None
    return token


def revoke_token(token_id: str) -> bool:
    existed = token_id in _tokens
    _tokens.pop(token_id, None)
    if existed:
        log.info("registry.token_revoked", metadata={"token_id": token_id})
    return existed


def list_tokens() -> list[Token]:
    global _last_token_sweep
    if time.monotonic() - _last_token_sweep > 60 or len(_tokens) > 100:
        now = int(time.time() * 1000)
        expired = [tid for tid, t in _tokens.items() if now > t.expiry]
        for tid in expired:
            _tokens.pop(tid, None)
        _last_token_sweep = time.monotonic()
    return list(_tokens.values())


# ---------------------------------------------------------------------------
# State serialization
# ---------------------------------------------------------------------------


def get_state() -> dict:
    return {"tokens": [(tid, t.model_dump()) for tid, t in _tokens.items()]}


def restore_state(state: dict | None) -> None:
    if not state or "tokens" not in state:
        return
    now = int(time.time() * 1000)
    for tid, data in state["tokens"]:
        token = Token(**data)
        if now <= token.expiry:
            _tokens[tid] = token
