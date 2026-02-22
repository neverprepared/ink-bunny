"""Tests for unified profile environment: mounts, env injection, and settings."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docker.errors import NotFound

from brainbox.config import ProfileSettings, Settings
from brainbox.lifecycle import (
    _read_cache_vars,
    _resolve_oauth_account,
    _resolve_profile_env,
    _resolve_profile_mounts,
)
from brainbox.models import SessionContext


# ---------------------------------------------------------------------------
# ProfileSettings defaults
# ---------------------------------------------------------------------------


class TestProfileSettings:
    def test_defaults(self):
        ps = ProfileSettings()
        assert ps.mount_env is True
        assert ps.mount_aws is True
        assert ps.mount_azure is True
        assert ps.mount_kube is True
        assert ps.mount_ssh is True
        assert ps.mount_gitconfig is True
        assert ps.mount_gcloud is False
        assert ps.mount_terraform is False

    def test_disable_individual_mounts(self):
        ps = ProfileSettings(mount_aws=False, mount_ssh=False, mount_gitconfig=False)
        assert ps.mount_aws is False
        assert ps.mount_ssh is False
        assert ps.mount_gitconfig is False
        # Others remain at defaults
        assert ps.mount_azure is True
        assert ps.mount_kube is True

    def test_enable_opt_in_mounts(self):
        ps = ProfileSettings(mount_gcloud=True, mount_terraform=True)
        assert ps.mount_gcloud is True
        assert ps.mount_terraform is True

    def test_settings_includes_profile(self):
        s = Settings()
        assert hasattr(s, "profile")
        assert isinstance(s.profile, ProfileSettings)


# ---------------------------------------------------------------------------
# _resolve_profile_mounts() — host path resolution
# ---------------------------------------------------------------------------


class TestResolveProfileMounts:
    # --- AWS ---

    def test_mounts_default_aws_dir(self, tmp_path):
        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(aws_dir) in result
        assert result[str(aws_dir)]["bind"] == "/home/developer/.aws"
        assert result[str(aws_dir)]["mode"] == "ro"

    def test_mounts_aws_from_env_var(self, tmp_path):
        aws_dir = tmp_path / "custom-aws"
        aws_dir.mkdir()
        config_file = aws_dir / "config"
        config_file.touch()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict(
                "os.environ",
                {"AWS_CONFIG_FILE": str(config_file), "WORKSPACE_HOME": str(tmp_path)},
                clear=True,
            ),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(aws_dir) in result
        assert result[str(aws_dir)]["bind"] == "/home/developer/.aws"

    # --- Azure ---

    def test_mounts_default_azure_dir(self, tmp_path):
        azure_dir = tmp_path / ".azure"
        azure_dir.mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(azure_dir) in result
        assert result[str(azure_dir)]["bind"] == "/home/developer/.azure"
        assert result[str(azure_dir)]["mode"] == "ro"

    def test_mounts_azure_from_env_var(self, tmp_path):
        azure_dir = tmp_path / "custom-azure"
        azure_dir.mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict(
                "os.environ",
                {"AZURE_CONFIG_DIR": str(azure_dir), "WORKSPACE_HOME": str(tmp_path)},
                clear=True,
            ),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(azure_dir) in result
        assert result[str(azure_dir)]["bind"] == "/home/developer/.azure"

    # --- Kube ---

    def test_mounts_default_kube_dir(self, tmp_path):
        kube_dir = tmp_path / ".kube"
        kube_dir.mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(kube_dir) in result
        assert result[str(kube_dir)]["bind"] == "/home/developer/.kube"
        assert result[str(kube_dir)]["mode"] == "ro"

    def test_mounts_kube_from_env_var(self, tmp_path):
        kube_dir = tmp_path / "custom-kube"
        kube_dir.mkdir()
        kubeconfig = kube_dir / "config"
        kubeconfig.touch()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict(
                "os.environ",
                {"KUBECONFIG": str(kubeconfig), "WORKSPACE_HOME": str(tmp_path)},
                clear=True,
            ),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(kube_dir) in result
        assert result[str(kube_dir)]["bind"] == "/home/developer/.kube"

    # --- SSH ---

    def test_mounts_ssh_dir(self, tmp_path):
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(ssh_dir) in result
        assert result[str(ssh_dir)]["bind"] == "/home/developer/.ssh"
        assert result[str(ssh_dir)]["mode"] == "ro"

    def test_skips_ssh_when_disabled(self, tmp_path):
        (tmp_path / ".ssh").mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings(mount_ssh=False)
            result = _resolve_profile_mounts()
        binds = [v["bind"] for v in result.values()]
        assert "/home/developer/.ssh" not in binds

    # --- Gitconfig ---

    def test_mounts_gitconfig_file(self, tmp_path):
        gitconfig = tmp_path / ".gitconfig"
        gitconfig.write_text("[user]\n    name = Test\n")
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(gitconfig) in result
        assert result[str(gitconfig)]["bind"] == "/home/developer/.gitconfig"
        assert result[str(gitconfig)]["mode"] == "rw"

    def test_mounts_gitconfig_from_env_var(self, tmp_path):
        custom_gitconfig = tmp_path / "custom.gitconfig"
        custom_gitconfig.write_text("[user]\n    name = Custom\n")
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict(
                "os.environ",
                {"GIT_CONFIG_GLOBAL": str(custom_gitconfig), "WORKSPACE_HOME": str(tmp_path)},
                clear=True,
            ),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert str(custom_gitconfig) in result
        assert result[str(custom_gitconfig)]["bind"] == "/home/developer/.gitconfig"

    # --- Gcloud (opt-in) ---

    def test_skips_gcloud_by_default(self, tmp_path):
        (tmp_path / ".gcloud").mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        binds = [v["bind"] for v in result.values()]
        assert "/home/developer/.gcloud" not in binds

    def test_mounts_gcloud_when_enabled(self, tmp_path):
        gcloud_dir = tmp_path / ".gcloud"
        gcloud_dir.mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings(mount_gcloud=True)
            result = _resolve_profile_mounts()
        assert str(gcloud_dir) in result
        assert result[str(gcloud_dir)]["bind"] == "/home/developer/.gcloud"

    # --- Terraform (opt-in) ---

    def test_skips_terraform_by_default(self, tmp_path):
        (tmp_path / ".terraform.d").mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        binds = [v["bind"] for v in result.values()]
        assert "/home/developer/.terraform.d" not in binds

    def test_mounts_terraform_when_enabled(self, tmp_path):
        terraform_dir = tmp_path / ".terraform.d"
        terraform_dir.mkdir()
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings(mount_terraform=True)
            result = _resolve_profile_mounts()
        assert str(terraform_dir) in result
        assert result[str(terraform_dir)]["bind"] == "/home/developer/.terraform.d"

    # --- Edge cases ---

    def test_skips_missing_directories(self, tmp_path):
        """No dirs exist → no mounts (except gitconfig which is a file check)."""
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()
        assert result == {}

    def test_skips_disabled_mounts(self, tmp_path):
        """Dirs exist but settings disable them."""
        (tmp_path / ".aws").mkdir()
        (tmp_path / ".azure").mkdir()
        (tmp_path / ".kube").mkdir()
        (tmp_path / ".ssh").mkdir()
        (tmp_path / ".gitconfig").write_text("[user]\n    name = Test\n")
        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"WORKSPACE_HOME": str(tmp_path)}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings(
                mount_aws=False,
                mount_azure=False,
                mount_kube=False,
                mount_ssh=False,
                mount_gitconfig=False,
            )
            result = _resolve_profile_mounts()
        assert result == {}

    # --- Explicit workspace_home ---

    def test_mounts_with_explicit_workspace_home(self, tmp_path):
        """workspace_home + workspace_profile reads cache and resolves mounts."""
        ws = tmp_path / "firebuild"
        ws.mkdir()
        (ws / ".aws").mkdir()
        (ws / ".ssh").mkdir()
        (ws / ".gitconfig").write_text("[user]\n    name = Firebuild\n")

        # Set up volatile cache
        cache_dir = tmp_path / "sp-profiles" / "firebuild"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".env").write_text(
            'AWS_CONFIG_FILE="$WORKSPACE_HOME/.aws/config"\n'
            'GIT_CONFIG_GLOBAL="$WORKSPACE_HOME/.gitconfig"\n'
        )

        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path / "wrong"),
            patch.dict(
                "os.environ",
                {"WORKSPACE_HOME": str(tmp_path / "wrong"), "TMPDIR": str(tmp_path)},
                clear=True,
            ),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts(workspace_profile="firebuild", workspace_home=str(ws))

        assert str(ws / ".aws") in result
        assert str(ws / ".ssh") in result
        assert str(ws / ".gitconfig") in result

    def test_workspace_home_reads_cache_env_vars(self, tmp_path):
        """When workspace_home + workspace_profile are provided, mounts resolve from cache."""
        ws = tmp_path / "firebuild"
        ws.mkdir()
        (ws / ".aws").mkdir()

        wrong_aws = tmp_path / "wrong-aws"
        wrong_aws.mkdir()
        (wrong_aws / "config").touch()

        # Set up volatile cache pointing to workspace_home
        cache_dir = tmp_path / "sp-profiles" / "firebuild"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".env").write_text('AWS_CONFIG_FILE="$WORKSPACE_HOME/.aws/config"\n')

        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path / "wrong"),
            patch.dict(
                "os.environ",
                {
                    "AWS_CONFIG_FILE": str(wrong_aws / "config"),
                    "WORKSPACE_HOME": str(tmp_path / "wrong"),
                    "TMPDIR": str(tmp_path),
                },
                clear=True,
            ),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts(workspace_profile="firebuild", workspace_home=str(ws))

        # Cache-resolved path wins, NOT the API host's env var
        assert str(ws / ".aws") in result
        assert str(wrong_aws) not in result

    def test_workspace_home_without_profile_uses_fallback(self, tmp_path):
        """workspace_home without workspace_profile falls back to directory-based resolution."""
        ws = tmp_path / "firebuild"
        ws.mkdir()
        (ws / ".aws").mkdir()

        wrong_aws = tmp_path / "wrong-aws"
        wrong_aws.mkdir()
        (wrong_aws / "config").touch()

        with (
            patch("brainbox.lifecycle.Path.home", return_value=tmp_path / "wrong"),
            patch.dict(
                "os.environ",
                {
                    "AWS_CONFIG_FILE": str(wrong_aws / "config"),
                    "WORKSPACE_HOME": str(tmp_path / "wrong"),
                },
                clear=True,
            ),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts(workspace_home=str(ws))

        # No cache → env vars empty → falls back to directory
        assert str(ws / ".aws") in result
        assert str(wrong_aws) not in result

    def test_workspace_home_adds_real_sso_cache_mount(self, tmp_path):
        """When workspace_home is set, real $HOME/.aws/sso/cache/ is nested-mounted."""
        ws = tmp_path / "firebuild"
        (ws / ".aws").mkdir(parents=True)

        real_home = tmp_path / "realhome"
        sso_cache = real_home / ".aws" / "sso" / "cache"
        sso_cache.mkdir(parents=True)
        (sso_cache / "token.json").write_text("{}")

        with (
            patch("brainbox.lifecycle.Path.home", return_value=real_home),
            patch.dict("os.environ", {}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts(workspace_home=str(ws))

        # Profile .aws is mounted
        assert str(ws / ".aws") in result
        # Real home SSO cache is nested-mounted on top
        assert str(sso_cache) in result
        assert result[str(sso_cache)]["bind"] == "/home/developer/.aws/sso/cache"

    def test_no_sso_overlay_without_workspace_home(self, tmp_path):
        """Without workspace_home, no extra SSO cache mount is added."""
        home = tmp_path / "home"
        (home / ".aws" / "sso" / "cache").mkdir(parents=True)

        with (
            patch("brainbox.lifecycle.Path.home", return_value=home),
            patch.dict("os.environ", {"WORKSPACE_HOME": ""}, clear=True),
            patch("brainbox.lifecycle.settings") as mock_settings,
        ):
            mock_settings.profile = ProfileSettings()
            result = _resolve_profile_mounts()

        # .aws is mounted from home, SSO cache is already inside it — no overlay
        sso_path = str(home / ".aws" / "sso" / "cache")
        assert sso_path not in result


# ---------------------------------------------------------------------------
# _read_cache_vars() — volatile cache reader
# ---------------------------------------------------------------------------


class TestReadCacheVars:
    def test_expands_workspace_home_and_strips_quotes(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "testprofile"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".env").write_text(
            'AWS_CONFIG_FILE="$WORKSPACE_HOME/.aws/config"\n'
            "AZURE_CONFIG_DIR='$WORKSPACE_HOME/.azure'\n"
            "KUBECONFIG=$WORKSPACE_HOME/.kube/config\n"
        )
        with patch.dict("os.environ", {"TMPDIR": str(tmp_path)}, clear=True):
            result = _read_cache_vars("testprofile", "/host/ws")

        assert result["AWS_CONFIG_FILE"] == "/host/ws/.aws/config"
        assert result["AZURE_CONFIG_DIR"] == "/host/ws/.azure"
        assert result["KUBECONFIG"] == "/host/ws/.kube/config"

    def test_returns_empty_when_no_cache(self, tmp_path):
        with patch.dict("os.environ", {"TMPDIR": str(tmp_path)}, clear=True):
            result = _read_cache_vars("nonexistent", "/host/ws")
        assert result == {}

    def test_skips_comments_and_blank_lines(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "prof"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".env").write_text("# comment\n\n  \nREAL_VAR=value\n")
        with patch.dict("os.environ", {"TMPDIR": str(tmp_path)}, clear=True):
            result = _read_cache_vars("prof", "/host/ws")
        assert result == {"REAL_VAR": "value"}

    def test_handles_export_prefix(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "prof"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".env").write_text('export MY_VAR="hello"\n')
        with patch.dict("os.environ", {"TMPDIR": str(tmp_path)}, clear=True):
            result = _read_cache_vars("prof", "/host/ws")
        assert result == {"MY_VAR": "hello"}


# ---------------------------------------------------------------------------
# _resolve_profile_env() — reads volatile .env cache
# ---------------------------------------------------------------------------


class TestResolveProfileEnv:
    def test_returns_none_without_workspace_profile(self):
        with patch.dict("os.environ", {"WORKSPACE_PROFILE": ""}, clear=True):
            result = _resolve_profile_env()
        assert result is None

    def test_returns_none_when_cache_missing(self, tmp_path):
        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "personal", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env()
        assert result is None

    def test_reads_cached_env_and_prepends_identity(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "personal"
        cache_dir.mkdir(parents=True)
        env_file = cache_dir / ".env"
        env_file.write_text(
            '# A comment\nANTHROPIC_API_KEY="sk-test"\nQDRANT_URL=http://localhost:6333\n'
        )
        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "personal", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env()

        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "WORKSPACE_PROFILE=personal"
        assert lines[1] == "WORKSPACE_HOME=/home/developer"
        assert 'ANTHROPIC_API_KEY="sk-test"' in result
        assert "QDRANT_URL=http://localhost:6333" in result

    def test_strips_host_only_vars(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "personal"
        cache_dir.mkdir(parents=True)
        env_file = cache_dir / ".env"
        env_file.write_text(
            'SSH_AUTH_SOCK="/path/to/agent.sock"\n'
            'GIT_SSH_COMMAND="ssh -F /host/path"\n'
            "GOOD_VAR=keep_me\n"
        )
        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "personal", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env()

        assert result is not None
        assert "SSH_AUTH_SOCK" not in result
        assert "GIT_SSH_COMMAND" not in result
        assert "GOOD_VAR=keep_me" in result

    def test_skips_comments_and_blank_lines(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "test"
        cache_dir.mkdir(parents=True)
        env_file = cache_dir / ".env"
        env_file.write_text("# This is a comment\n\n  \nREAL_VAR=value\n")
        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "test", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env()

        assert result is not None
        # Only identity lines + REAL_VAR
        lines = [l for l in result.splitlines() if l]
        assert len(lines) == 3
        assert lines[2] == "REAL_VAR=value"

    def test_strips_claude_config_dir(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "personal"
        cache_dir.mkdir(parents=True)
        env_file = cache_dir / ".env"
        env_file.write_text(
            "CLAUDE_CONFIG_DIR=$WORKSPACE_HOME/.claude\n"
            "GEMINI_CONFIG_DIR=$WORKSPACE_HOME/.config/gemini\n"
            "GOOD_VAR=keep\n"
        )
        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "personal", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env()

        assert result is not None
        assert "CLAUDE_CONFIG_DIR" not in result
        assert "GEMINI_CONFIG_DIR" not in result
        assert "GOOD_VAR=keep" in result

    def test_handles_export_prefix(self, tmp_path):
        cache_dir = tmp_path / "sp-profiles" / "work"
        cache_dir.mkdir(parents=True)
        env_file = cache_dir / ".env"
        env_file.write_text("export HOME=/bad\nexport MY_VAR=good\n")
        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "work", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env()

        assert result is not None
        # HOME=/bad should be stripped, but WORKSPACE_HOME is prepended
        lines = result.splitlines()
        home_lines = [l for l in lines if l.startswith("export HOME=") or l == "HOME=/bad"]
        assert home_lines == []  # stripped as host-only
        assert "export MY_VAR=good" in result

    # --- Explicit workspace_profile ---

    def test_reads_env_with_explicit_profile(self, tmp_path):
        """workspace_profile param overrides WORKSPACE_PROFILE env var."""
        cache_dir = tmp_path / "sp-profiles" / "firebuild"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".env").write_text('SOME_KEY="value"\n')

        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "personal", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env(workspace_profile="firebuild")

        assert result is not None
        lines = result.splitlines()
        assert lines[0] == "WORKSPACE_PROFILE=firebuild"
        assert 'SOME_KEY="value"' in result

    def test_explicit_profile_ignores_env_var(self, tmp_path):
        """When workspace_profile is passed, the env var WORKSPACE_PROFILE is not used."""
        # Only set up cache for firebuild, not personal
        cache_dir = tmp_path / "sp-profiles" / "firebuild"
        cache_dir.mkdir(parents=True)
        (cache_dir / ".env").write_text("KEY=val\n")

        with patch.dict(
            "os.environ",
            {"WORKSPACE_PROFILE": "personal", "TMPDIR": str(tmp_path)},
            clear=True,
        ):
            result = _resolve_profile_env(workspace_profile="firebuild")

        assert result is not None
        assert "WORKSPACE_PROFILE=firebuild" in result


# ---------------------------------------------------------------------------
# _resolve_oauth_account() — host Claude auth
# ---------------------------------------------------------------------------


class TestResolveOauthAccount:
    def test_reads_oauth_account_from_host(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_json = claude_dir / ".claude.json"
        claude_json.write_text(
            '{"oauthAccount": {"accountUuid": "abc-123", "emailAddress": "test@example.com", "organizationUuid": "org-456"}}'
        )
        with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(claude_dir)}, clear=False):
            result = _resolve_oauth_account()
        assert result is not None
        assert result["accountUuid"] == "abc-123"
        assert result["emailAddress"] == "test@example.com"

    def test_returns_none_when_no_config_file(self, tmp_path):
        with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(tmp_path)}, clear=False):
            result = _resolve_oauth_account()
        assert result is None

    def test_returns_none_when_no_oauth_account(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_json = claude_dir / ".claude.json"
        claude_json.write_text('{"hasCompletedOnboarding": true}')
        with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(claude_dir)}, clear=False):
            result = _resolve_oauth_account()
        assert result is None

    def test_returns_none_on_malformed_json(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_json = claude_dir / ".claude.json"
        claude_json.write_text("not valid json")
        with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(claude_dir)}, clear=False):
            result = _resolve_oauth_account()
        assert result is None

    def test_returns_none_when_oauth_missing_account_uuid(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_json = claude_dir / ".claude.json"
        claude_json.write_text('{"oauthAccount": {"emailAddress": "test@example.com"}}')
        with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(claude_dir)}, clear=False):
            result = _resolve_oauth_account()
        assert result is None


# ---------------------------------------------------------------------------
# provision() — profile mounts in volumes
# ---------------------------------------------------------------------------


class TestProvisionProfileMounts:
    @pytest.mark.asyncio
    async def test_provision_includes_profile_volumes(self, tmp_path):
        aws_dir = tmp_path / ".aws"
        aws_dir.mkdir()
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()

        mock_client = MagicMock()
        mock_image = MagicMock()
        mock_image.attrs = {"RepoDigests": []}
        mock_client.images.get.return_value = mock_image
        mock_client.containers.get.side_effect = NotFound("not found")
        mock_client.containers.create.return_value = MagicMock()

        profile_mounts = {
            str(aws_dir): {"bind": "/home/developer/.aws", "mode": "ro"},
            str(ssh_dir): {"bind": "/home/developer/.ssh", "mode": "ro"},
        }

        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._find_available_port", return_value=7681),
            patch("brainbox.lifecycle._verify_cosign", new_callable=AsyncMock),
            patch("brainbox.lifecycle._resolve_profile_mounts", return_value=profile_mounts),
        ):
            from brainbox.lifecycle import provision

            ctx = await provision(session_name="profile-test")

        create_call = mock_client.containers.create.call_args
        volumes = create_call[1]["volumes"]
        assert str(aws_dir) in volumes
        assert volumes[str(aws_dir)]["bind"] == "/home/developer/.aws"
        assert volumes[str(aws_dir)]["mode"] == "ro"
        assert str(ssh_dir) in volumes
        assert "aws" in ctx.profile_mounts
        assert "ssh" in ctx.profile_mounts

    @pytest.mark.asyncio
    async def test_provision_sets_workspace_profile_label(self):
        mock_client = MagicMock()
        mock_image = MagicMock()
        mock_image.attrs = {"RepoDigests": []}
        mock_client.images.get.return_value = mock_image
        mock_client.containers.get.side_effect = NotFound("not found")
        mock_client.containers.create.return_value = MagicMock()

        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._find_available_port", return_value=7681),
            patch("brainbox.lifecycle._verify_cosign", new_callable=AsyncMock),
            patch("brainbox.lifecycle._resolve_profile_mounts", return_value={}),
            patch.dict("os.environ", {"WORKSPACE_PROFILE": "personal"}, clear=False),
        ):
            from brainbox.lifecycle import provision

            await provision(session_name="label-wp-test")

        create_call = mock_client.containers.create.call_args
        labels = create_call[1]["labels"]
        assert labels["brainbox.workspace_profile"] == "PERSONAL"

    @pytest.mark.asyncio
    async def test_provision_no_mounts_when_dirs_missing(self):
        mock_client = MagicMock()
        mock_image = MagicMock()
        mock_image.attrs = {"RepoDigests": []}
        mock_client.images.get.return_value = mock_image
        mock_client.containers.get.side_effect = NotFound("not found")
        mock_client.containers.create.return_value = MagicMock()

        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._find_available_port", return_value=7681),
            patch("brainbox.lifecycle._verify_cosign", new_callable=AsyncMock),
            patch("brainbox.lifecycle._resolve_profile_mounts", return_value={}),
        ):
            from brainbox.lifecycle import provision

            ctx = await provision(session_name="no-mount-test")

        assert ctx.profile_mounts == set()

    @pytest.mark.asyncio
    async def test_provision_passes_workspace_home_to_mounts(self):
        """workspace_profile and workspace_home are threaded to _resolve_profile_mounts()."""
        mock_client = MagicMock()
        mock_image = MagicMock()
        mock_image.attrs = {"RepoDigests": []}
        mock_client.images.get.return_value = mock_image
        mock_client.containers.get.side_effect = NotFound("not found")
        mock_client.containers.create.return_value = MagicMock()

        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._find_available_port", return_value=7681),
            patch("brainbox.lifecycle._verify_cosign", new_callable=AsyncMock),
            patch("brainbox.lifecycle._resolve_profile_mounts", return_value={}) as mock_mounts,
        ):
            from brainbox.lifecycle import provision

            await provision(
                session_name="ws-home-test",
                workspace_profile="firebuild",
                workspace_home="/Users/test/profiles/firebuild",
            )

        mock_mounts.assert_called_once_with(
            workspace_profile="firebuild",
            workspace_home="/Users/test/profiles/firebuild",
        )

    @pytest.mark.asyncio
    async def test_provision_stores_workspace_fields_on_ctx(self):
        """workspace_profile and workspace_home are stored on SessionContext."""
        mock_client = MagicMock()
        mock_image = MagicMock()
        mock_image.attrs = {"RepoDigests": []}
        mock_client.images.get.return_value = mock_image
        mock_client.containers.get.side_effect = NotFound("not found")
        mock_client.containers.create.return_value = MagicMock()

        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._find_available_port", return_value=7681),
            patch("brainbox.lifecycle._verify_cosign", new_callable=AsyncMock),
            patch("brainbox.lifecycle._resolve_profile_mounts", return_value={}),
        ):
            from brainbox.lifecycle import provision

            ctx = await provision(
                session_name="ctx-fields-test",
                workspace_profile="firebuild",
                workspace_home="/Users/test/profiles/firebuild",
            )

        assert ctx.workspace_profile == "firebuild"
        assert ctx.workspace_home == "/Users/test/profiles/firebuild"


# ---------------------------------------------------------------------------
# start() — profile env injection
# ---------------------------------------------------------------------------


class TestStartProfileEnv:
    @pytest.fixture()
    def ctx_with_profile(self):
        return SessionContext(
            session_name="profile-env-test",
            container_name="developer-profile-env-test",
            port=7681,
            created_at=0,
            ttl=3600,
            hardened=False,
            profile_mounts={"aws", "ssh", "gitconfig"},
        )

    @pytest.fixture()
    def ctx_without_profile(self):
        return SessionContext(
            session_name="no-profile-env-test",
            container_name="developer-no-profile-env-test",
            port=7682,
            created_at=0,
            ttl=3600,
            hardened=False,
            profile_mounts=set(),
        )

    @pytest.mark.asyncio
    async def test_writes_profile_env_file(self, ctx_with_profile):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"")
        mock_client.containers.get.return_value = mock_container

        profile_env_content = (
            'WORKSPACE_PROFILE=testing\nWORKSPACE_HOME=/home/developer\nANTHROPIC_API_KEY="sk-test"'
        )

        sessions = {ctx_with_profile.session_name: ctx_with_profile}
        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._sessions", sessions),
            patch("brainbox.lifecycle._resolve_profile_env", return_value=profile_env_content),
        ):
            from brainbox.lifecycle import start

            await start(ctx_with_profile)

        calls = mock_container.exec_run.call_args_list
        profile_env_calls = [
            c
            for c in calls
            if any("/run/profile/.env" in str(arg) for arg in c.args + tuple(c.kwargs.values()))
        ]
        # Expect: write file, source from .bashrc, source from .env
        assert len(profile_env_calls) >= 3
        # First call writes the file
        cmd_str = str(profile_env_calls[0])
        assert "WORKSPACE_PROFILE=testing" in cmd_str
        # Subsequent calls hook it into .bashrc and .env
        hook_strs = " ".join(str(c) for c in profile_env_calls[1:])
        assert "set -a" in hook_strs
        assert ".bashrc" in hook_strs
        assert ".env" in hook_strs

    @pytest.mark.asyncio
    async def test_skips_profile_env_when_no_cache(self, ctx_without_profile):
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"")
        mock_client.containers.get.return_value = mock_container

        sessions = {ctx_without_profile.session_name: ctx_without_profile}
        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._sessions", sessions),
            patch("brainbox.lifecycle._resolve_profile_env", return_value=None),
        ):
            from brainbox.lifecycle import start

            await start(ctx_without_profile)

        calls = mock_container.exec_run.call_args_list
        profile_env_calls = [
            c
            for c in calls
            if any("/run/profile/.env" in str(arg) for arg in c.args + tuple(c.kwargs.values()))
        ]
        assert len(profile_env_calls) == 0

    @pytest.mark.asyncio
    async def test_start_passes_workspace_profile_to_resolve(self):
        """start() threads ctx.workspace_profile to _resolve_profile_env()."""
        ctx = SessionContext(
            session_name="wp-thread-test",
            container_name="developer-wp-thread-test",
            port=7683,
            created_at=0,
            ttl=3600,
            hardened=False,
            workspace_profile="firebuild",
        )

        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b"")
        mock_client.containers.get.return_value = mock_container

        sessions = {ctx.session_name: ctx}
        with (
            patch("brainbox.lifecycle._docker", return_value=mock_client),
            patch("brainbox.backends.docker._docker", return_value=mock_client),
            patch("brainbox.lifecycle._sessions", sessions),
            patch("brainbox.lifecycle._resolve_profile_env", return_value=None) as mock_env,
        ):
            from brainbox.lifecycle import start

            await start(ctx)

        mock_env.assert_called_once_with(workspace_profile="firebuild")
