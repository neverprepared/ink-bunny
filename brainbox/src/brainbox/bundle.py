"""Config bundle builder — assembles ~/.claude into a container-ready tar.gz.

Translates host paths to container paths, merges forced container settings,
suppresses macOS-only hooks, and delivers the user's actual plugins/skills/agents.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tarfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .log import get_logger

log = get_logger()

# ~/.claude dirs/files to include in the bundle
CLAUDE_INCLUDE_DIRS = {"plugins", "hooks", "skills", "agents", "commands"}
CLAUDE_INCLUDE_FILES = {"CLAUDE.md"}
CLAUDE_SKIP = {"settings.local.json", ".claude.json"}

# Patterns indicating macOS-only hooks (suppress in containers)
MACOS_PATTERNS = [
    "osascript",
    "terminal-notifier",
    "open -a",
    ".app/",
    "/usr/bin/open",
    "afplay",
]

# Settings keys always forced in containers
FORCED_SETTINGS: dict[str, Any] = {
    "bypassPermissions": True,
    "dangerouslySkipPermissions": True,
}


def _default_path_map() -> dict[str, str]:
    """Build default host→container path substitutions from environment."""
    # When running inside the brainbox-api container, Path.home() returns /root.
    # BRAINBOX_HOST_HOME carries the actual host user home for path translation.
    home = os.environ.get("BRAINBOX_HOST_HOME") or str(Path.home())
    ws = os.environ.get("WORKSPACE_HOME", home)
    claude_config = os.environ.get("CLAUDE_CONFIG_DIR", home + "/.claude")

    path_map: dict[str, str] = {
        home + "/": "/home/developer/",
        ws: "/home/developer/workspace",
        "$WORKSPACE_HOME": "/home/developer/workspace",
        "$CLAUDE_CONFIG_DIR": "/home/developer/.claude",
        claude_config: "/home/developer/.claude",
    }

    # Detect Homebrew prefix (macOS/Linux)
    try:
        brew = subprocess.check_output(["brew", "--prefix"], text=True, timeout=5).strip()
        path_map[brew + "/bin/"] = "/home/linuxbrew/.linuxbrew/bin/"
        path_map[brew + "/"] = "/home/linuxbrew/.linuxbrew/"
    except Exception:
        # brew not available — skip
        pass

    return path_map


def _translate(obj: Any, path_map: dict[str, str]) -> Any:
    """Recursively apply path_map substitutions to all string values."""
    if isinstance(obj, str):
        # Apply longest-match-first to avoid partial substitutions
        for src, dst in sorted(path_map.items(), key=lambda x: -len(x[0])):
            if src and src in obj:
                obj = obj.replace(src, dst)
        return obj
    elif isinstance(obj, dict):
        return {k: _translate(v, path_map) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_translate(item, path_map) for item in obj]
    return obj


def _filter_macos_hooks(hooks: dict) -> dict:
    """Remove hook entries that call macOS-specific tools."""
    result: dict = {}
    for event, entries in hooks.items():
        filtered = []
        entry_list = entries if isinstance(entries, list) else [entries]
        for entry in entry_list:
            cmd = entry.get("command", "") if isinstance(entry, dict) else str(entry)
            if not any(p in cmd for p in MACOS_PATTERNS):
                filtered.append(entry)
        if filtered:
            result[event] = filtered
    return result


def _build_container_settings(
    settings_path: Path, claude_json_path: Path, path_map: dict[str, str]
) -> str:
    """Load user settings.json, apply translations, force container overrides.

    MCP servers are merged from three sources (later wins on collision):
      1. settings.json mcpServers (workspace-specific, path-translated)
      2. ~/.claude.json mcpServers (user-level, path-translated)
    """
    user: dict = {}
    if settings_path.exists():
        try:
            user = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    result = deepcopy(user)

    # Translate all string values recursively
    result = _translate(result, path_map)

    # Merge user-level MCP servers from ~/.claude.json (user-level wins)
    if claude_json_path.exists():
        try:
            claude_json = json.loads(claude_json_path.read_text())
            user_servers = claude_json.get("mcpServers", {})
            if user_servers:
                merged = {**result.get("mcpServers", {}), **user_servers}
                result["mcpServers"] = _translate(merged, path_map)
        except (json.JSONDecodeError, OSError):
            pass

    # Force container-required settings
    result.update(FORCED_SETTINGS)

    # Suppress macOS-only hooks
    if "hooks" in result:
        result["hooks"] = _filter_macos_hooks(result["hooks"])

    return json.dumps(result, indent=2)


def _build_container_mcp(
    mcp_path: Path, claude_json_path: Path, path_map: dict[str, str]
) -> str | None:
    """Merge MCP servers from ~/.mcp.json and ~/.claude/.claude.json, translate binary paths.

    Claude Code stores user-level MCP servers in .claude.json under mcpServers.
    We extract them and merge with ~/.mcp.json so containers get all servers.
    """
    mcp: dict = {}

    # Load ~/.mcp.json (project-level)
    if mcp_path.exists():
        try:
            mcp = json.loads(mcp_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Merge user-level servers from .claude.json
    if claude_json_path.exists():
        try:
            claude_json = json.loads(claude_json_path.read_text())
            user_servers = claude_json.get("mcpServers", {})
            if user_servers:
                mcp.setdefault("mcpServers", {})
                # ~/.mcp.json takes precedence if same key exists
                mcp["mcpServers"] = {**user_servers, **mcp["mcpServers"]}
        except (json.JSONDecodeError, OSError):
            pass

    if not mcp:
        return None
    return json.dumps(_translate(mcp, path_map), indent=2)


def _add_bytes(tf: tarfile.TarFile, arcname: str, data: bytes) -> None:
    """Add bytes as a file to a tarball."""
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mode = 0o644
    tf.addfile(info, io.BytesIO(data))


def _add_dir_translated(
    tf: tarfile.TarFile,
    src_dir: Path,
    arcname: str,
    path_map: dict[str, str],
) -> None:
    """Recursively add a directory, applying path translation to text files."""
    for item in sorted(src_dir.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(src_dir)
        arc_path = f"{arcname}/{relative}"

        # For text files, apply path translation
        try:
            text = item.read_text(encoding="utf-8")
            translated = _translate(text, path_map)
            data = translated.encode("utf-8")
            _add_bytes(tf, arc_path, data)
        except (UnicodeDecodeError, OSError):
            # Binary file — add as-is
            try:
                tf.add(item, arcname=arc_path)
            except OSError:
                pass


def build_config_bundle(
    workspace_home: str | Path | None = None,
    path_map: dict[str, str] | None = None,
) -> bytes:
    """Assemble ~/.claude config as a container-ready tar.gz bundle.

    - Path-translates all string values using path_map
    - Merges forced container settings (bypassPermissions, etc.)
    - Suppresses macOS-only hooks
    - Translates MCP binary paths in ~/.mcp.json
    - Includes user's plugins/, hooks/, skills/ (markdown content)

    Returns raw tar.gz bytes suitable for container.put_archive().
    """
    # Resolve the Claude config directory:
    # 1. explicit workspace_home → workspace_home/.claude
    # 2. CLAUDE_CONFIG_DIR env var (set by compose / local env)
    # 3. fallback to Path.home()/.claude
    if workspace_home:
        claude_dir = Path(workspace_home) / ".claude"
        user_home = Path(workspace_home)
    elif claude_config_env := os.environ.get("CLAUDE_CONFIG_DIR"):
        claude_dir = Path(claude_config_env)
        user_home = claude_dir.parent
    else:
        user_home = Path.home()
        claude_dir = user_home / ".claude"

    resolved_map = path_map if path_map is not None else _default_path_map()

    buf = io.BytesIO()

    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # settings.json — translated + forced overrides
        settings_json = _build_container_settings(
            claude_dir / "settings.json", Path.home() / ".claude.json", resolved_map
        )
        _add_bytes(tf, ".claude/settings.json", settings_json.encode())

        # .gitconfig — git identity
        gitconfig = user_home / ".gitconfig"
        if gitconfig.is_file():
            try:
                tf.add(gitconfig, arcname=".gitconfig")
            except OSError:
                pass

        # ~/.claude dirs: plugins/, hooks/, skills/, agents/, commands/
        if claude_dir.is_dir():
            for item in sorted(claude_dir.iterdir()):
                if item.is_file() and item.name in CLAUDE_INCLUDE_FILES:
                    try:
                        tf.add(item, arcname=f".claude/{item.name}")
                    except OSError:
                        pass
                elif item.is_dir() and item.name in CLAUDE_INCLUDE_DIRS:
                    _add_dir_translated(
                        tf,
                        item,
                        arcname=f".claude/{item.name}",
                        path_map=resolved_map,
                    )

    log.info(
        "bundle.built",
        metadata={
            "claude_dir": str(claude_dir),
            "bundle_bytes": buf.tell(),
        },
    )

    return buf.getvalue()
