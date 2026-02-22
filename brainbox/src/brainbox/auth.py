"""API key authentication for protected endpoints."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

from fastapi import HTTPException, Request

from .config import settings
from .log import get_logger

log = get_logger()

_api_key: str = ""


def generate_api_key() -> str:
    """Generate a new 64-character hex API key."""
    return secrets.token_hex(32)


def _write_key_file(key: str, path: Path) -> None:
    """Write API key to file with 0o600 permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600


def load_or_create_key() -> str:
    """Load API key from env, file, or generate a new one.

    Priority:
    1. CL_API_KEY environment variable
    2. Key file on disk
    3. Generate new key and write to disk
    """
    global _api_key

    # 1. Environment variable takes precedence
    env_key = os.environ.get("CL_API_KEY", "").strip()
    if env_key:
        _api_key = env_key
        log.info("auth.key_loaded", metadata={"source": "environment"})
        return _api_key

    # 2. Try reading from file
    key_file = settings.api_key_file
    if key_file.exists():
        _api_key = key_file.read_text().strip()
        if _api_key:
            log.info("auth.key_loaded", metadata={"source": "file", "path": str(key_file)})
            return _api_key

    # 3. Generate new key
    _api_key = generate_api_key()
    _write_key_file(_api_key, key_file)
    log.info("auth.key_created", metadata={"path": str(key_file)})
    return _api_key


def get_api_key() -> str:
    """Return the current API key (must call load_or_create_key first)."""
    return _api_key


def require_api_key(request: Request) -> None:
    """FastAPI dependency that validates the X-API-Key header.

    Raises 401 if the key is missing or invalid.
    """
    provided = request.headers.get("x-api-key", "")
    if not provided or not _api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    if not secrets.compare_digest(provided, _api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
