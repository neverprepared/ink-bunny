"""Backend abstraction layer for brainbox.

Provides a polymorphic interface for managing isolated development environments
using different backend technologies (Docker containers, UTM VMs, etc.).
"""

from __future__ import annotations

from typing import Protocol, Any

from ..models import SessionContext


class BackendProtocol(Protocol):
    """Protocol defining the interface all backends must implement.

    Backends manage the lifecycle of isolated development environments through
    a 5-phase process: provision → configure → start → monitor → recycle.
    """

    async def provision(
        self,
        ctx: SessionContext,
        *,
        image_or_template: str,
        volumes: dict[str, dict[str, str]],
        hardening_kwargs: dict[str, Any],
    ) -> SessionContext:
        """Phase 1: Create and prepare the environment.

        For Docker: Creates container with specified image and volumes.
        For UTM: Clones VM template and configures shared directories.

        Args:
            ctx: Session context with initial configuration
            image_or_template: Docker image name or UTM VM template name
            volumes: Volume mounts in Docker format {host_path: {"bind": container_path, "mode": "rw"}}
            hardening_kwargs: Backend-specific security configuration

        Returns:
            Updated SessionContext with provisioning details
        """
        ...

    async def configure(
        self,
        ctx: SessionContext,
        *,
        secrets: dict[str, str],
        env_content: str | None = None,
        oauth_account: dict[str, Any] | None = None,
        profile_env: str | None = None,
    ) -> SessionContext:
        """Phase 2: Inject secrets and configuration.

        For Docker: Writes secrets to /run/secrets (hardened) or ~/.env (legacy).
        For UTM: SSH into VM and write configuration files.

        Args:
            ctx: Session context
            secrets: Secret key-value pairs to inject
            env_content: Legacy .env file content (Docker legacy mode only)
            oauth_account: Claude Code OAuth account data
            profile_env: Workspace profile environment variables

        Returns:
            Updated SessionContext
        """
        ...

    async def start(self, ctx: SessionContext) -> SessionContext:
        """Phase 3: Start the environment.

        For Docker: Starts container and launches ttyd terminal.
        For UTM: Boots VM and waits for SSH availability.

        Args:
            ctx: Session context

        Returns:
            Updated SessionContext with running state
        """
        ...

    async def stop(self, ctx: SessionContext) -> SessionContext:
        """Stop the environment without removing it.

        For Docker: Stops container.
        For UTM: Shuts down VM.

        Args:
            ctx: Session context

        Returns:
            Updated SessionContext
        """
        ...

    async def remove(self, ctx: SessionContext) -> SessionContext:
        """Phase 5: Clean up and delete the environment.

        For Docker: Removes stopped container.
        For UTM: Deletes VM .utm package.

        Args:
            ctx: Session context

        Returns:
            Updated SessionContext
        """
        ...

    async def health_check(self, ctx: SessionContext) -> dict[str, Any]:
        """Phase 4: Check environment health and collect metrics.

        For Docker: Returns CPU/memory usage, container status.
        For UTM: Returns SSH connectivity, VM state.

        Args:
            ctx: Session context

        Returns:
            Health metrics dict with backend-specific fields
        """
        ...

    async def exec_command(
        self, ctx: SessionContext, command: list[str], **kwargs: Any
    ) -> tuple[int, bytes]:
        """Execute a command inside the environment.

        For Docker: Uses docker exec.
        For UTM: Uses SSH to run command.

        Args:
            ctx: Session context
            command: Command and arguments to execute
            **kwargs: Backend-specific options (detach, user, etc.)

        Returns:
            Tuple of (exit_code, output)
        """
        ...

    def get_sessions_info(self) -> list[dict[str, Any]]:
        """List all managed sessions/environments.

        For Docker: Lists containers with brainbox.managed=true label.
        For UTM: Lists VMs with brainbox- prefix.

        Returns:
            List of session info dicts with name, state, ports, etc.
        """
        ...


def create_backend(backend_type: str) -> BackendProtocol:
    """Factory function to create a backend instance.

    Args:
        backend_type: Backend type ("docker" or "utm")

    Returns:
        Backend instance implementing BackendProtocol

    Raises:
        ValueError: If backend_type is not supported
    """
    if backend_type == "docker":
        from .docker import DockerBackend

        return DockerBackend()
    elif backend_type == "utm":
        from .utm import UTMBackend

        return UTMBackend()
    else:
        raise ValueError(
            f"Unsupported backend type: {backend_type}. Supported backends: docker, utm"
        )


__all__ = [
    "BackendProtocol",
    "create_backend",
]
