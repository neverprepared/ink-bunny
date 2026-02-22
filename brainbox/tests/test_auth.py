"""Tests for API key authentication."""

from __future__ import annotations

import stat
from unittest.mock import MagicMock, patch

import pytest

import brainbox.auth as auth_module
from brainbox.auth import generate_api_key, load_or_create_key, require_api_key


class TestGenerateApiKey:
    def test_length(self):
        key = generate_api_key()
        assert len(key) == 64

    def test_hex(self):
        key = generate_api_key()
        int(key, 16)  # Should not raise

    def test_unique(self):
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10


class TestLoadOrCreateKey:
    def test_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CL_API_KEY", "env-key-value")
        monkeypatch.setattr(auth_module, "_api_key", "")
        key = load_or_create_key()
        assert key == "env-key-value"
        monkeypatch.delenv("CL_API_KEY")

    def test_from_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CL_API_KEY", raising=False)
        monkeypatch.setattr(auth_module, "_api_key", "")
        key_file = tmp_path / ".api-key"
        key_file.write_text("file-key-value")
        with patch("brainbox.auth.settings") as mock_settings:
            mock_settings.api_key_file = key_file
            key = load_or_create_key()
        assert key == "file-key-value"

    def test_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CL_API_KEY", raising=False)
        monkeypatch.setattr(auth_module, "_api_key", "")
        key_file = tmp_path / ".api-key"
        with patch("brainbox.auth.settings") as mock_settings:
            mock_settings.api_key_file = key_file
            key = load_or_create_key()
        assert key_file.exists()
        assert key_file.read_text() == key
        assert len(key) == 64
        # Check permissions are 0o600
        mode = key_file.stat().st_mode
        assert mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR

    def test_env_takes_precedence_over_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CL_API_KEY", "env-wins")
        monkeypatch.setattr(auth_module, "_api_key", "")
        key_file = tmp_path / ".api-key"
        key_file.write_text("file-loses")
        with patch("brainbox.auth.settings") as mock_settings:
            mock_settings.api_key_file = key_file
            key = load_or_create_key()
        assert key == "env-wins"
        monkeypatch.delenv("CL_API_KEY")


class TestRequireApiKey:
    def _make_request(self, api_key_header: str | None = None) -> MagicMock:
        request = MagicMock()
        headers = {}
        if api_key_header is not None:
            headers["x-api-key"] = api_key_header
        request.headers.get = lambda key, default="": headers.get(key, default)
        return request

    def test_valid_key(self, monkeypatch):
        monkeypatch.setattr(auth_module, "_api_key", "valid-test-key")
        request = self._make_request("valid-test-key")
        # Should not raise
        require_api_key(request)

    def test_missing_key(self, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(auth_module, "_api_key", "valid-test-key")
        request = self._make_request()
        with pytest.raises(HTTPException) as exc_info:
            require_api_key(request)
        assert exc_info.value.status_code == 401
        assert "API key" in exc_info.value.detail

    def test_invalid_key(self, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(auth_module, "_api_key", "valid-test-key")
        request = self._make_request("wrong-key")
        with pytest.raises(HTTPException) as exc_info:
            require_api_key(request)
        assert exc_info.value.status_code == 401

    def test_no_server_key_configured(self, monkeypatch):
        """When server has no key loaded, all requests should be rejected."""
        from fastapi import HTTPException

        monkeypatch.setattr(auth_module, "_api_key", "")
        request = self._make_request("any-key")
        with pytest.raises(HTTPException) as exc_info:
            require_api_key(request)
        assert exc_info.value.status_code == 401

    def test_constant_time_comparison(self, monkeypatch):
        """Verify we use constant-time comparison (secrets.compare_digest)."""
        import secrets

        monkeypatch.setattr(auth_module, "_api_key", "valid-key")
        request = self._make_request("valid-key")
        with patch.object(secrets, "compare_digest", return_value=True) as mock_compare:
            require_api_key(request)
            mock_compare.assert_called_once_with("valid-key", "valid-key")


class TestGetApiKey:
    def test_returns_loaded_key(self, monkeypatch):
        from brainbox.auth import get_api_key

        monkeypatch.setattr(auth_module, "_api_key", "my-key")
        assert get_api_key() == "my-key"

    def test_returns_empty_before_load(self, monkeypatch):
        from brainbox.auth import get_api_key

        monkeypatch.setattr(auth_module, "_api_key", "")
        assert get_api_key() == ""
