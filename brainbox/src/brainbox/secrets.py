"""Secret resolution via 1Password Service Account or plaintext files.

Two strategies:
1. 1Password — when a Service Account token is available, discover all items
   in the SA's accessible vault(s) via ``op item list`` / ``op item get`` and
   derive environment variable names automatically from item titles and field
   labels (e.g. ``langfuse-api`` + ``public-key`` → ``LANGFUSE_API_PUBLIC_KEY``).
2. Plaintext files — legacy fallback, reads individual files from secrets_dir.

The host resolves secrets; containers never see the SA token or ``op`` CLI.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

from .config import settings
from .log import get_logger

log = get_logger()

# Fields to skip during vault discovery
_SKIP_FIELD_IDS = frozenset({"notesPlain"})
_SKIP_FIELD_TYPES = frozenset({"OTP"})


def get_sa_token() -> str | None:
    """Return the 1Password Service Account token, or None."""
    token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    if token:
        return token

    token_file = settings.op_sa_token_file
    try:
        return token_file.read_text().strip() or None
    except (FileNotFoundError, PermissionError):
        return None


def has_op_integration() -> bool:
    """Check whether 1Password integration is configured."""
    return get_sa_token() is not None


def _op_run(args: list[str], sa_token: str) -> str:
    """Run an ``op`` CLI command with SA token injected via environment."""
    env = {**os.environ, "OP_SERVICE_ACCOUNT_TOKEN": sa_token}
    result = subprocess.run(
        ["op", *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"op {' '.join(args)} failed: {stderr}")
    return result.stdout


def _to_env_name(item_title: str, field_label: str) -> str:
    """Derive an environment variable name from item title and field label.

    Examples:
        langfuse-api + public-key  → LANGFUSE_API_PUBLIC_KEY
        uptime-kuma  + password    → UPTIME_KUMA_PASSWORD
        claude-code  + oauth-token → CLAUDE_CODE_OAUTH_TOKEN
    """
    raw = f"{item_title}_{field_label}"
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper()


def resolve_from_op(sa_token: str) -> dict[str, str]:
    """Discover and resolve all secrets from the 1Password vault.

    Lists every item visible to the Service Account, extracts fields with
    non-empty values (skipping notes and OTP), and derives env var names
    from ``ITEM_TITLE_FIELD_LABEL``.

    Fails closed — any ``op`` CLI error aborts the entire resolution.
    """
    vault_args: list[str] = []
    if settings.op_vault:
        vault_args = ["--vault", settings.op_vault]

    # List all items
    try:
        raw = _op_run(["item", "list", *vault_args, "--format", "json"], sa_token)
    except RuntimeError as exc:
        log.error("secrets.op_list_failed", metadata={"error": str(exc)})
        raise

    items = json.loads(raw)
    if not items:
        log.warning("secrets.vault_empty", metadata={"vault": settings.op_vault or "(all)"})
        return {}

    resolved: dict[str, str] = {}
    for item_summary in items:
        item_id = item_summary["id"]
        item_title = item_summary.get("title", item_id)

        try:
            raw = _op_run(["item", "get", item_id, "--format", "json"], sa_token)
        except RuntimeError as exc:
            log.error(
                "secrets.op_get_failed",
                metadata={"item": item_title, "error": str(exc)},
            )
            raise

        item = json.loads(raw)

        for field in item.get("fields", []):
            if field.get("id") in _SKIP_FIELD_IDS:
                continue
            if field.get("type") in _SKIP_FIELD_TYPES:
                continue

            label = field.get("label", "")
            value = field.get("value", "")
            if not label or not value:
                continue

            env_name = _to_env_name(item_title, label)
            if env_name in resolved:
                log.warning(
                    "secrets.name_collision",
                    metadata={"env_name": env_name, "item": item_title, "field": label},
                )
            resolved[env_name] = value

    log.info(
        "secrets.resolved_from_op",
        metadata={"count": len(resolved), "items": len(items)},
    )
    return resolved


def resolve_from_files() -> dict[str, str]:
    """Read secrets from plaintext files in secrets_dir (legacy fallback)."""
    secrets_dir = settings.secrets_dir
    resolved: dict[str, str] = {}
    try:
        for f in secrets_dir.iterdir():
            if f.is_file():
                resolved[f.name] = f.read_text().strip()
    except FileNotFoundError:
        pass

    log.info("secrets.resolved_from_files", metadata={"count": len(resolved)})
    return resolved


def resolve_secrets() -> dict[str, str]:
    """Resolve secrets using the best available strategy.

    Prefers 1Password when a Service Account token is configured,
    otherwise falls back to plaintext files.
    """
    sa_token = get_sa_token()
    if sa_token:
        return resolve_from_op(sa_token)
    return resolve_from_files()
