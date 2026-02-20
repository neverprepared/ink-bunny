"""Pydantic models for API request validation."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from .validation import (
    ValidationError,
    validate_session_name,
    validate_role,
    validate_volume_mount,
)


class CreateSessionRequest(BaseModel):
    """Request model for POST /api/create endpoint."""

    name: str | None = None
    role: str | None = None
    volume: str | None = None  # Legacy single volume (backward compatibility)
    volumes: list[str] | None = None  # New multi-volume support
    llm_provider: str = "claude"
    llm_model: str | None = None
    ollama_host: str | None = None
    workspace_profile: str | None = None
    workspace_home: str | None = None
    backend: str = "docker"  # "docker" or "utm"
    vm_template: str | None = None  # UTM only: template VM name
    ports: dict[str, int] | None = None  # Additional port mappings (container_port: host_port)

    @field_validator("name")
    @classmethod
    def validate_name_field(cls, v: str | None) -> str:
        """Validate session name using existing validation function."""
        if v is None:
            return "default"
        try:
            return validate_session_name(v)
        except ValidationError as e:
            raise ValueError(str(e)) from e

    @field_validator("role")
    @classmethod
    def validate_role_field(cls, v: str | None) -> str:
        """Validate role using existing validation function."""
        if v is None:
            return "developer"
        try:
            return validate_role(v)
        except ValidationError as e:
            raise ValueError(str(e)) from e

    @model_validator(mode="after")
    def validate_volumes_and_normalize(self) -> CreateSessionRequest:
        """Normalize volumes field and validate each volume mount."""
        # Support both new "volumes" (list) and legacy "volume" (string)
        if self.volumes is None:
            # Fall back to legacy single volume parameter
            if self.volume:
                self.volumes = [self.volume]
            else:
                self.volumes = []
        elif not isinstance(self.volumes, list):
            # Normalize single string to list
            self.volumes = [self.volumes] if self.volumes else []

        # Validate each volume mount
        validated_volumes = []
        for vol in self.volumes:
            if vol and vol != "-":  # Skip empty or placeholder volumes
                try:
                    host, container, mode = validate_volume_mount(vol)
                    validated_volumes.append(f"{host}:{container}:{mode}")
                except ValidationError as e:
                    raise ValueError(str(e)) from e

        self.volumes = validated_volumes
        return self


class StopSessionRequest(BaseModel):
    """Request model for POST /api/stop endpoint."""

    name: str = Field(..., description="Container name to stop")


class DeleteSessionRequest(BaseModel):
    """Request model for POST /api/delete endpoint."""

    name: str = Field(..., description="Container name to delete")


class StartSessionRequest(BaseModel):
    """Request model for POST /api/start endpoint."""

    name: str = Field(..., description="Container name to start")


class ExecSessionRequest(BaseModel):
    """Request model for POST /api/sessions/{name}/exec endpoint."""

    command: str = Field(..., description="Command to execute in the container")

    @field_validator("command")
    @classmethod
    def validate_command_not_empty(cls, v: str) -> str:
        """Ensure command is not empty after stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("command is required")
        return stripped


class QuerySessionRequest(BaseModel):
    """Request model for POST /api/sessions/{name}/query endpoint."""

    prompt: str = Field(..., description="Prompt to send to Claude Code in the container")
    working_dir: str | None = Field(None, description="Working directory for Claude Code execution")
    timeout: int = Field(300, description="Timeout in seconds for query execution", ge=10, le=3600)
    fork_session: bool = Field(
        False, description="Fork a new conversation thread instead of using main session"
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt_not_empty(cls, v: str) -> str:
        """Ensure prompt is not empty after stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("prompt is required")
        return stripped
