"""Docker SDK kwargs builders for hardened and legacy container modes."""

from __future__ import annotations

from typing import Any

from docker.types import Mount

from .config import settings


def _parse_tmpfs_size(size: str) -> int:
    """Convert human-readable size (e.g. '10M') to bytes."""
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3}
    if size and size[-1].upper() in multipliers:
        return int(size[:-1]) * multipliers[size[-1].upper()]
    return int(size)


def get_hardening_kwargs(*, user: str | None = None) -> dict[str, Any]:
    """Return Docker SDK kwargs for a hardened container."""
    h = settings.hardening
    r = settings.resources

    kwargs: dict[str, Any] = {
        "read_only": h.read_only_rootfs,
        "cap_drop": list(h.drop_caps),
        "mem_limit": r.memory,
        "nano_cpus": int(float(r.cpus) * 1e9),
        "user": user or settings.user,
        "tmpfs": {
            "/workspace": f"size={r.tmpfs_workspace}",
            "/tmp": f"size={r.tmpfs_tmp}",
        },
        "mounts": [
            Mount(
                target="/run/secrets",
                source="",
                type="tmpfs",
                tmpfs_size=_parse_tmpfs_size(r.tmpfs_secrets),
                tmpfs_mode=0o400,
            ),
            Mount(
                target="/run/profile",
                source="",
                type="tmpfs",
                tmpfs_size=_parse_tmpfs_size("1M"),
                tmpfs_mode=0o644,
            ),
        ],
    }

    if h.no_new_privileges:
        kwargs["security_opt"] = ["no-new-privileges:true"]

    return kwargs


def get_legacy_kwargs() -> dict[str, Any]:
    """Return Docker SDK kwargs for legacy/dev mode (no hardening)."""
    return {}
