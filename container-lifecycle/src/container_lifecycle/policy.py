"""Policy engine for task assignment and message routing."""

from __future__ import annotations

from .log import get_logger
from .models import AgentDefinition, PolicyResult, Task, Token
from .registry import get_agent, validate_token

log = get_logger()


def evaluate_task_assignment(agent_def: AgentDefinition | None, task: Task) -> PolicyResult:
    """Check whether a task can be assigned to a given agent."""
    if not agent_def:
        return PolicyResult(allowed=False, reason="Agent definition is null")

    if not get_agent(agent_def.name):
        return PolicyResult(allowed=False, reason=f"Agent '{agent_def.name}' is not registered")

    if not task or not task.description:
        return PolicyResult(allowed=False, reason="Task must have a description")

    log.info("policy.task_allowed", metadata={"agent": agent_def.name, "task_id": task.id})
    return PolicyResult(allowed=True)


def evaluate_message(sender_token: Token | None, recipient_name: str, payload: dict) -> PolicyResult:
    """Check whether a message from sender to recipient is allowed."""
    if not sender_token:
        return PolicyResult(allowed=False, reason="No sender token provided")

    if not validate_token(sender_token.token_id):
        return PolicyResult(allowed=False, reason="Sender token is invalid or expired")

    if recipient_name and recipient_name != "hub":
        if not get_agent(recipient_name):
            return PolicyResult(allowed=False, reason=f"Recipient '{recipient_name}' is not a registered agent")

    if not payload or "type" not in payload:
        return PolicyResult(allowed=False, reason="Payload must have a type field")

    return PolicyResult(allowed=True)


def evaluate_capability(token: Token | None, required_cap: str) -> PolicyResult:
    """Check whether a token has a specific capability."""
    if not token:
        return PolicyResult(allowed=False, reason="No token provided")

    if not validate_token(token.token_id):
        return PolicyResult(allowed=False, reason="Token is invalid or expired")

    if required_cap not in token.capabilities:
        return PolicyResult(allowed=False, reason=f"Token lacks required capability '{required_cap}'")

    return PolicyResult(allowed=True)
