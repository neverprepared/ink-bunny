"""Tests for the secrets module — everything except live 1Password calls."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from container_lifecycle.config import settings
from container_lifecycle.secrets import (
    _to_env_name,
    get_sa_token,
    has_op_integration,
    resolve_from_files,
    resolve_from_op,
    resolve_secrets,
)


@pytest.fixture()
def isolated_config(tmp_path, monkeypatch):
    """Point settings.config_dir at a temp dir so derived properties resolve there."""
    config_dir = tmp_path / "developer"
    config_dir.mkdir()
    monkeypatch.setattr(settings, "config_dir", config_dir)
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    return config_dir


# ---------------------------------------------------------------------------
# _to_env_name
# ---------------------------------------------------------------------------


class TestToEnvName:
    def test_basic(self):
        assert _to_env_name("langfuse-api", "public-key") == "LANGFUSE_API_PUBLIC_KEY"

    def test_single_word_field(self):
        assert _to_env_name("uptime-kuma", "password") == "UPTIME_KUMA_PASSWORD"

    def test_oauth_token(self):
        assert _to_env_name("claude-code", "oauth-token") == "CLAUDE_CODE_OAUTH_TOKEN"

    def test_underscores_preserved(self):
        assert _to_env_name("my_item", "my_field") == "MY_ITEM_MY_FIELD"

    def test_dots_replaced(self):
        assert _to_env_name("api.v2", "key.name") == "API_V2_KEY_NAME"

    def test_spaces_replaced(self):
        assert _to_env_name("my item", "secret key") == "MY_ITEM_SECRET_KEY"

    def test_leading_trailing_junk(self):
        assert _to_env_name("-item-", "-field-") == "ITEM_FIELD"

    def test_multiple_consecutive_separators(self):
        assert _to_env_name("foo--bar", "baz..qux") == "FOO_BAR_BAZ_QUX"


# ---------------------------------------------------------------------------
# get_sa_token / has_op_integration
# ---------------------------------------------------------------------------


class TestGetSaToken:
    def test_env_var_takes_priority(self, isolated_config, monkeypatch):
        token_file = isolated_config / ".op-sa-token"
        token_file.write_text("file-token")
        monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "env-token")

        assert get_sa_token() == "env-token"

    def test_reads_from_file(self, isolated_config):
        token_file = isolated_config / ".op-sa-token"
        token_file.write_text("  file-token  \n")

        assert get_sa_token() == "file-token"

    def test_returns_none_when_missing(self, isolated_config):
        assert get_sa_token() is None

    def test_returns_none_for_empty_file(self, isolated_config):
        token_file = isolated_config / ".op-sa-token"
        token_file.write_text("   \n")

        assert get_sa_token() is None

    def test_has_op_integration_true(self, isolated_config, monkeypatch):
        monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "tok")
        assert has_op_integration() is True

    def test_has_op_integration_false(self, isolated_config):
        assert has_op_integration() is False


# ---------------------------------------------------------------------------
# resolve_from_files
# ---------------------------------------------------------------------------


class TestResolveFromFiles:
    def test_reads_files(self, isolated_config):
        secrets_dir = isolated_config / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "GH_TOKEN").write_text("ghp_abc123\n")
        (secrets_dir / "API_KEY").write_text("  sk-xyz  ")

        result = resolve_from_files()
        assert result == {"GH_TOKEN": "ghp_abc123", "API_KEY": "sk-xyz"}

    def test_empty_dir(self, isolated_config):
        secrets_dir = isolated_config / ".secrets"
        secrets_dir.mkdir()

        assert resolve_from_files() == {}

    def test_missing_dir(self, isolated_config):
        assert resolve_from_files() == {}

    def test_skips_subdirectories(self, isolated_config):
        secrets_dir = isolated_config / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "GOOD").write_text("value")
        (secrets_dir / "subdir").mkdir()

        assert resolve_from_files() == {"GOOD": "value"}


# ---------------------------------------------------------------------------
# resolve_from_op (mocked op CLI)
# ---------------------------------------------------------------------------


def _mock_op_run_factory(items_list: list[dict], items_detail: dict[str, dict]):
    """Return a mock _op_run that returns canned JSON for list and get."""

    def _mock(args: list[str], sa_token: str) -> str:
        if args[:2] == ["item", "list"]:
            return json.dumps(items_list)
        if args[:2] == ["item", "get"]:
            item_id = args[2]
            return json.dumps(items_detail[item_id])
        raise RuntimeError(f"unexpected op call: {args}")

    return _mock


class TestResolveFromOp:
    def test_discovers_items(self, monkeypatch):
        items_list = [
            {"id": "id1", "title": "langfuse-api"},
            {"id": "id2", "title": "uptime-kuma"},
        ]
        items_detail = {
            "id1": {
                "id": "id1",
                "title": "langfuse-api",
                "fields": [
                    {"id": "username", "type": "STRING", "label": "public-key", "value": "pk-123"},
                    {"id": "password", "type": "CONCEALED", "label": "secret-key", "value": "sk-456"},
                    {"id": "notesPlain", "type": "STRING", "label": "notesPlain", "value": "some note"},
                ],
            },
            "id2": {
                "id": "id2",
                "title": "uptime-kuma",
                "fields": [
                    {"id": "username", "type": "STRING", "label": "username", "value": "admin"},
                    {"id": "password", "type": "CONCEALED", "label": "password", "value": "secret"},
                    {"id": "otp", "type": "OTP", "label": "one-time password", "value": "otpauth://..."},
                ],
            },
        }

        monkeypatch.setattr(settings, "op_vault", "")
        mock = _mock_op_run_factory(items_list, items_detail)

        with patch("container_lifecycle.secrets._op_run", side_effect=mock):
            result = resolve_from_op("fake-token")

        assert result == {
            "LANGFUSE_API_PUBLIC_KEY": "pk-123",
            "LANGFUSE_API_SECRET_KEY": "sk-456",
            "UPTIME_KUMA_USERNAME": "admin",
            "UPTIME_KUMA_PASSWORD": "secret",
        }

    def test_skips_empty_values(self, monkeypatch):
        items_list = [{"id": "id1", "title": "test-item"}]
        items_detail = {
            "id1": {
                "id": "id1",
                "title": "test-item",
                "fields": [
                    {"id": "f1", "type": "STRING", "label": "filled", "value": "yes"},
                    {"id": "f2", "type": "STRING", "label": "empty", "value": ""},
                    {"id": "f3", "type": "STRING", "label": "", "value": "no-label"},
                ],
            },
        }

        monkeypatch.setattr(settings, "op_vault", "")
        mock = _mock_op_run_factory(items_list, items_detail)

        with patch("container_lifecycle.secrets._op_run", side_effect=mock):
            result = resolve_from_op("fake-token")

        assert result == {"TEST_ITEM_FILLED": "yes"}

    def test_empty_vault(self, monkeypatch):
        monkeypatch.setattr(settings, "op_vault", "")

        with patch("container_lifecycle.secrets._op_run", return_value="[]"):
            result = resolve_from_op("fake-token")

        assert result == {}

    def test_vault_arg_passed(self, monkeypatch):
        monkeypatch.setattr(settings, "op_vault", "MyVault")

        captured_args: list[list[str]] = []

        def _capture(args, sa_token):
            captured_args.append(args)
            return "[]"

        with patch("container_lifecycle.secrets._op_run", side_effect=_capture):
            resolve_from_op("fake-token")

        assert "--vault" in captured_args[0]
        assert "MyVault" in captured_args[0]

    def test_no_vault_arg_when_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "op_vault", "")

        captured_args: list[list[str]] = []

        def _capture(args, sa_token):
            captured_args.append(args)
            return "[]"

        with patch("container_lifecycle.secrets._op_run", side_effect=_capture):
            resolve_from_op("fake-token")

        assert "--vault" not in captured_args[0]

    def test_op_list_failure_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "op_vault", "")

        with patch(
            "container_lifecycle.secrets._op_run",
            side_effect=RuntimeError("op item list failed: auth error"),
        ):
            with pytest.raises(RuntimeError, match="auth error"):
                resolve_from_op("fake-token")

    def test_op_get_failure_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "op_vault", "")

        call_count = 0

        def _mock(args, sa_token):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return json.dumps([{"id": "id1", "title": "item"}])
            raise RuntimeError("op item get failed: not found")

        with patch("container_lifecycle.secrets._op_run", side_effect=_mock):
            with pytest.raises(RuntimeError, match="not found"):
                resolve_from_op("fake-token")

    def test_name_collision_last_wins(self, monkeypatch):
        """When two fields produce the same env name, last one wins."""
        items_list = [
            {"id": "id1", "title": "foo-bar"},
            {"id": "id2", "title": "foo"},
        ]
        items_detail = {
            "id1": {
                "id": "id1",
                "title": "foo-bar",
                "fields": [
                    {"id": "f1", "type": "STRING", "label": "key", "value": "first"},
                ],
            },
            "id2": {
                "id": "id2",
                "title": "foo",
                "fields": [
                    {"id": "f1", "type": "STRING", "label": "bar-key", "value": "second"},
                ],
            },
        }

        monkeypatch.setattr(settings, "op_vault", "")
        mock = _mock_op_run_factory(items_list, items_detail)

        with patch("container_lifecycle.secrets._op_run", side_effect=mock):
            result = resolve_from_op("fake-token")

        # FOO_BAR_KEY from both — second write wins
        assert result["FOO_BAR_KEY"] == "second"


# ---------------------------------------------------------------------------
# resolve_secrets (strategy selection)
# ---------------------------------------------------------------------------


class TestResolveSecrets:
    def test_uses_op_when_token_available(self, isolated_config, monkeypatch):
        monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "tok")

        with patch(
            "container_lifecycle.secrets.resolve_from_op", return_value={"A": "1"}
        ) as mock_op:
            result = resolve_secrets()

        mock_op.assert_called_once_with("tok")
        assert result == {"A": "1"}

    def test_falls_back_to_files(self, isolated_config):
        secrets_dir = isolated_config / ".secrets"
        secrets_dir.mkdir()
        (secrets_dir / "MY_KEY").write_text("my_val")

        result = resolve_secrets()
        assert result == {"MY_KEY": "my_val"}


# ---------------------------------------------------------------------------
# config.py: _default_config_dir
# ---------------------------------------------------------------------------


class TestDefaultConfigDir:
    def test_xdg_takes_priority(self, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/config")
        monkeypatch.setenv("WORKSPACE_HOME", "/ws")

        from container_lifecycle.config import _default_config_dir

        assert _default_config_dir() == Path("/xdg/config/developer")

    def test_workspace_home_fallback(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("WORKSPACE_HOME", "/ws")

        from container_lifecycle.config import _default_config_dir

        assert _default_config_dir() == Path("/ws/.config/developer")

    def test_home_fallback(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("WORKSPACE_HOME", raising=False)

        from container_lifecycle.config import _default_config_dir

        result = _default_config_dir()
        assert result == Path.home() / ".config" / "developer"
