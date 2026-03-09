"""Pydantic models for all domain objects."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


class AgentRole(str, Enum):
    """Agent roles absorbed from multiclaude's agent type system.

    Attribution: Role system originated from Dan Lorenc's multiclaude project
    (github.com/dlorenc/multiclaude).
    """
    DEVELOPER = "developer"       # Interactive session (existing default)
    SUPERVISOR = "supervisor"     # Orchestrates agents, persistent
    WORKER = "worker"            # Task executor, transient
    MERGE_QUEUE = "merge-queue"  # PR automation, persistent
    PR_SHEPHERD = "pr-shepherd"  # Fork PR coordination, persistent
    REVIEWER = "reviewer"        # Code review, transient


class AgentDefinition(BaseModel):
    name: str
    image: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    hardened: bool = False
    role_prompt: str | None = None  # Path to role prompt markdown (relative to agents dir)
    persistent: bool = False  # Persistent roles auto-restart; transient roles clean up
    repo_url: str | None = None  # GitHub repo URL for repo-specific agents


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


class Token(BaseModel):
    token_id: str
    agent_name: str
    task_id: str
    capabilities: list[str] = Field(default_factory=list)
    issued: int  # epoch ms
    expiry: int  # epoch ms


# ---------------------------------------------------------------------------
# Session context
# ---------------------------------------------------------------------------


class SessionState(str, Enum):
    PROVISIONING = "provisioning"
    CONFIGURING = "configuring"
    STARTING = "starting"
    RUNNING = "running"
    MONITORING = "monitoring"
    RECYCLING = "recycling"
    RECYCLED = "recycled"


class SessionContext(BaseModel):
    session_name: str
    container_name: str
    port: int
    role: str = "developer"
    teams_enabled: bool = False  # Claude Code Teams experimental feature
    role_prompt_file: str | None = None  # Path to role prompt injected into container
    repo_url: str | None = None  # Associated repository URL
    task_description: str | None = None  # Task description for hub-spawned workers
    state: SessionState = SessionState.PROVISIONING
    created_at: int  # epoch ms
    ttl: int  # seconds
    hardened: bool = True
    volume_mounts: list[str] = Field(default_factory=list)
    secrets: dict[str, str] = Field(default_factory=dict)
    health_failures: int = 0
    token: Token | None = None
    env_content: str | None = None  # legacy mode .env body
    llm_provider: str = "claude"  # "claude" or "ollama"
    llm_model: str | None = None  # e.g. "qwen3-coder"
    ollama_host: str | None = None  # per-session override
    profile_mounts: set[str] = Field(default_factory=set)  # {"aws", "azure", "kube", "ssh", ...}
    workspace_profile: str | None = None  # Caller's profile name
    workspace_home: str | None = None  # Caller's workspace home path
    # Backend-specific fields
    backend: str = "docker"  # "docker" or "utm"
    ports: dict[str, int] | None = None  # Additional port mappings (container_port: host_port)
    ssh_port: int | None = None  # UTM only: SSH port for VM access (deprecated - use vm_ip)
    ssh_user: str = "developer"  # UTM SSH username
    vm_template: str | None = None  # UTM only: Template VM name used for cloning
    vm_path: str | None = None  # UTM only: Full path to .utm package
    vm_ip: str | None = None  # UTM only: VM's IP address (bridged networking)
    mac_address: str | None = None  # UTM only: VM's MAC address for IP discovery


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    description: str
    agent_name: str
    repo_url: str | None = None  # Optional repo association


class Task(BaseModel):
    id: str
    description: str
    agent_name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: int  # epoch ms
    updated_at: int  # epoch ms
    token_id: str | None = None
    session_name: str | None = None
    result: Any = None
    error: str | None = None
    repo_url: str | None = None  # Associated repository


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class Repository(BaseModel):
    """A tracked repository with associated agent containers.

    Attribution: Multi-repo awareness originated from Dan Lorenc's multiclaude project.
    """
    url: str  # GitHub repo URL (e.g., "https://github.com/owner/repo")
    name: str  # Short name derived from URL (e.g., "repo")
    containers: dict[str, str] = Field(default_factory=dict)  # role -> session_name
    merge_queue_enabled: bool = False
    pr_shepherd_enabled: bool = False
    target_branch: str = "main"
    is_fork: bool = False
    upstream_url: str | None = None


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class MessageEnvelope(BaseModel):
    """Inbound message from an agent."""

    recipient: str = "hub"
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """Fully resolved message stored internally."""

    id: str
    timestamp: int  # epoch ms
    sender: str
    sender_token_id: str
    task_id: str | None = None
    recipient: str = "hub"
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MessageLogEntry(BaseModel):
    """Audit log entry for a routed or rejected message."""

    id: str
    timestamp: int  # epoch ms
    sender: str | None = None
    sender_token_id: str | None = None
    recipient: str | None = None
    type: str | None = None
    status: str  # "delivered" | "rejected"
    reason: str | None = None


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class PolicyResult(BaseModel):
    allowed: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# Hub state persistence
# ---------------------------------------------------------------------------


class RegistryState(BaseModel):
    tokens: list[tuple[str, dict[str, Any]]] = Field(default_factory=list)


class RouterState(BaseModel):
    tasks: list[tuple[str, dict[str, Any]]] = Field(default_factory=list)


class MessagesState(BaseModel):
    pending: list[tuple[str, list[dict[str, Any]]]] = Field(default_factory=list)
    log: list[dict[str, Any]] = Field(default_factory=list)


class HubState(BaseModel):
    flushed_at: int  # epoch ms
    registry: RegistryState = Field(default_factory=RegistryState)
    router: RouterState = Field(default_factory=RouterState)
    messages: MessagesState = Field(default_factory=MessagesState)
