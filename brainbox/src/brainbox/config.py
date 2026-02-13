"""Application settings from environment variables and defaults."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _default_config_dir() -> Path:
    import os

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "developer"
    ws = os.environ.get("WORKSPACE_HOME")
    if ws:
        return Path(ws) / ".config" / "developer"
    return Path.home() / ".config" / "developer"


class ResourceSettings(BaseSettings):
    memory: str = "2g"
    cpus: str = "2"
    tmpfs_workspace: str = "500M"
    tmpfs_tmp: str = "100M"
    tmpfs_secrets: str = "10M"


class HardeningSettings(BaseSettings):
    read_only_rootfs: bool = True
    no_new_privileges: bool = True
    drop_caps: list[str] = Field(
        default_factory=lambda: ["NET_RAW", "SYS_ADMIN", "MKNOD", "SYS_CHROOT", "NET_ADMIN"]
    )
    seccomp_profile: str = "default"


class HubSettings(BaseSettings):
    flush_interval: int = 30  # seconds
    prune_completed_after: int = 3600  # seconds
    message_retention: int = 100


class Settings(BaseSettings):
    image: str = "developer"
    container_prefix: str = "developer-"
    user: str = "65534:65534"
    config_dir: Path = Field(default_factory=_default_config_dir)

    ttl: int = 3600
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5  # seconds
    health_check_retries: int = 3

    api_port: int = 8000
    op_vault: str = ""

    resources: ResourceSettings = Field(default_factory=ResourceSettings)
    hardening: HardeningSettings = Field(default_factory=HardeningSettings)
    hub: HubSettings = Field(default_factory=HubSettings)

    model_config = {"env_prefix": "CL_"}

    @property
    def secrets_dir(self) -> Path:
        return self.config_dir / ".secrets"

    @property
    def op_sa_token_file(self) -> Path:
        return self.config_dir / ".op-sa-token"

    @property
    def sessions_dir(self) -> Path:
        return self.config_dir / "sessions"

    @property
    def state_file(self) -> Path:
        return self.config_dir / "hub-state.json"

    @property
    def agents_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "agents"


settings = Settings()
