"""Tests for cosign image signature verification."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from docker.errors import NotFound

from brainbox.config import CosignSettings, settings
from brainbox.cosign import (
    CosignResult,
    CosignVerificationError,
    _cosign_run,
    verify_image,
    verify_image_keyless,
)


# ---------------------------------------------------------------------------
# CosignResult
# ---------------------------------------------------------------------------


class TestCosignResult:
    def test_fields(self):
        r = CosignResult(verified=True, image_ref="img@sha256:abc", stdout="ok", stderr="")
        assert r.verified is True
        assert r.image_ref == "img@sha256:abc"
        assert r.stdout == "ok"
        assert r.stderr == ""

    def test_frozen(self):
        r = CosignResult(verified=True, image_ref="x", stdout="", stderr="")
        with pytest.raises(AttributeError):
            r.verified = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CosignVerificationError
# ---------------------------------------------------------------------------


class TestCosignVerificationError:
    def test_message_format(self):
        r = CosignResult(verified=False, image_ref="img@sha256:abc", stdout="", stderr="no sig")
        err = CosignVerificationError(r)
        assert "img@sha256:abc" in str(err)
        assert "no sig" in str(err)

    def test_result_attached(self):
        r = CosignResult(verified=False, image_ref="x", stdout="", stderr="fail")
        err = CosignVerificationError(r)
        assert err.result is r

    def test_is_runtime_error(self):
        r = CosignResult(verified=False, image_ref="x", stdout="", stderr="")
        assert isinstance(CosignVerificationError(r), RuntimeError)


# ---------------------------------------------------------------------------
# _cosign_run
# ---------------------------------------------------------------------------


class TestCosignRun:
    def test_success(self):
        fake = subprocess.CompletedProcess(args=["cosign"], returncode=0, stdout="ok", stderr="")
        with patch("brainbox.cosign.subprocess.run", return_value=fake) as mock_run:
            result = _cosign_run(["verify", "--key", "k.pub", "img"])

        assert result.returncode == 0
        mock_run.assert_called_once_with(
            ["cosign", "verify", "--key", "k.pub", "img"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_failure_returns_result(self):
        fake = subprocess.CompletedProcess(args=["cosign"], returncode=1, stdout="", stderr="error")
        with patch("brainbox.cosign.subprocess.run", return_value=fake):
            result = _cosign_run(["verify", "--key", "k.pub", "img"])

        assert result.returncode == 1
        assert result.stderr == "error"

    def test_binary_not_found(self):
        with patch("brainbox.cosign.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError, match="cosign binary not found"):
                _cosign_run(["verify"])

    def test_timeout(self):
        with patch(
            "brainbox.cosign.subprocess.run", side_effect=subprocess.TimeoutExpired("cosign", 30)
        ):
            with pytest.raises(subprocess.TimeoutExpired):
                _cosign_run(["verify"])


# ---------------------------------------------------------------------------
# verify_image
# ---------------------------------------------------------------------------


class TestVerifyImage:
    def test_success(self):
        fake = subprocess.CompletedProcess(
            args=["cosign"], returncode=0, stdout="Verification OK", stderr=""
        )
        with patch("brainbox.cosign._cosign_run", return_value=fake) as mock_run:
            result = verify_image("myimg:latest", "/tmp/k.pub", ["myimg@sha256:abc123"])

        assert result.verified is True
        assert result.image_ref == "myimg@sha256:abc123"
        mock_run.assert_called_once_with(["verify", "--key", "/tmp/k.pub", "myimg@sha256:abc123"])

    def test_failure(self):
        fake = subprocess.CompletedProcess(
            args=["cosign"], returncode=1, stdout="", stderr="no matching sig"
        )
        with patch("brainbox.cosign._cosign_run", return_value=fake):
            result = verify_image("myimg:latest", "/tmp/k.pub", ["myimg@sha256:abc123"])

        assert result.verified is False
        assert result.stderr == "no matching sig"

    def test_uses_first_digest(self):
        fake = subprocess.CompletedProcess(args=["cosign"], returncode=0, stdout="ok", stderr="")
        with patch("brainbox.cosign._cosign_run", return_value=fake) as mock_run:
            verify_image("myimg:latest", "/k.pub", ["first@sha256:aaa", "second@sha256:bbb"])

        args = mock_run.call_args[0][0]
        assert args[-1] == "first@sha256:aaa"

    def test_empty_repo_digests_raises(self):
        with pytest.raises(ValueError, match="no repo digests"):
            verify_image("myimg:latest", "/k.pub", [])


# ---------------------------------------------------------------------------
# verify_image_keyless
# ---------------------------------------------------------------------------


class TestVerifyImageKeyless:
    def test_success(self):
        fake = subprocess.CompletedProcess(
            args=["cosign"], returncode=0, stdout="Verification OK", stderr=""
        )
        with patch("brainbox.cosign._cosign_run", return_value=fake) as mock_run:
            result = verify_image_keyless(
                "myimg:latest",
                "https://github.com/owner/repo/.*",
                "https://token.actions.githubusercontent.com",
                ["myimg@sha256:abc123"],
            )

        assert result.verified is True
        assert result.image_ref == "myimg@sha256:abc123"
        mock_run.assert_called_once_with(
            [
                "verify",
                "--certificate-identity-regexp",
                "https://github.com/owner/repo/.*",
                "--certificate-oidc-issuer",
                "https://token.actions.githubusercontent.com",
                "myimg@sha256:abc123",
            ]
        )

    def test_failure(self):
        fake = subprocess.CompletedProcess(
            args=["cosign"], returncode=1, stdout="", stderr="no matching sig"
        )
        with patch("brainbox.cosign._cosign_run", return_value=fake):
            result = verify_image_keyless(
                "myimg:latest",
                "https://github.com/owner/repo/.*",
                "https://token.actions.githubusercontent.com",
                ["myimg@sha256:abc123"],
            )

        assert result.verified is False
        assert result.stderr == "no matching sig"

    def test_uses_first_digest(self):
        fake = subprocess.CompletedProcess(args=["cosign"], returncode=0, stdout="ok", stderr="")
        with patch("brainbox.cosign._cosign_run", return_value=fake) as mock_run:
            verify_image_keyless(
                "myimg:latest",
                "https://github.com/owner/repo/.*",
                "https://token.actions.githubusercontent.com",
                ["first@sha256:aaa", "second@sha256:bbb"],
            )

        args = mock_run.call_args[0][0]
        assert args[-1] == "first@sha256:aaa"

    def test_empty_repo_digests_raises(self):
        with pytest.raises(ValueError, match="no repo digests"):
            verify_image_keyless(
                "myimg:latest",
                "https://github.com/owner/repo/.*",
                "https://token.actions.githubusercontent.com",
                [],
            )


# ---------------------------------------------------------------------------
# CosignSettings
# ---------------------------------------------------------------------------


class TestCosignSettings:
    def test_defaults(self):
        s = CosignSettings()
        assert s.mode == "warn"
        assert s.key == ""
        assert s.certificate_identity == ""
        assert s.oidc_issuer == ""

    def test_explicit_values(self):
        s = CosignSettings(mode="enforce", key="/path/to/key.pub")
        assert s.mode == "enforce"
        assert s.key == "/path/to/key.pub"

    def test_keyless_values(self):
        s = CosignSettings(
            mode="enforce",
            certificate_identity="https://github.com/owner/repo/.*",
            oidc_issuer="https://token.actions.githubusercontent.com",
        )
        assert s.certificate_identity == "https://github.com/owner/repo/.*"
        assert s.oidc_issuer == "https://token.actions.githubusercontent.com"

    def test_invalid_mode_rejected(self):
        with pytest.raises(Exception):
            CosignSettings(mode="invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Provision integration (async)
# ---------------------------------------------------------------------------


class TestProvisionCosignIntegration:
    """Integration tests that exercise _verify_cosign via the provision path."""

    @pytest.fixture()
    def mock_docker(self, monkeypatch, tmp_path):
        """Stub out Docker client and settings for provision tests."""
        config_dir = tmp_path / "developer"
        config_dir.mkdir()
        (config_dir / "sessions").mkdir()

        monkeypatch.setattr(settings, "config_dir", config_dir)
        monkeypatch.setattr(settings, "image", "test-image")

        # Mock Docker client
        mock_image = MagicMock()
        mock_image.attrs = {"RepoDigests": ["test-image@sha256:abc123"]}

        mock_container = MagicMock()
        mock_client = MagicMock()
        mock_client.images.get.return_value = mock_image
        mock_client.containers.get.side_effect = [
            # First call: check existing → not found
            type("NotFound", (Exception,), {})(),
        ]
        mock_client.containers.create.return_value = mock_container

        # Patch docker client at lifecycle level (used for cosign checks and backend)
        monkeypatch.setattr("brainbox.lifecycle._client", mock_client)
        monkeypatch.setattr("brainbox.backends.docker._client", mock_client)

        # Clear session state
        import brainbox.lifecycle as lc

        lc._sessions.clear()

        return mock_client, mock_image

    @pytest.mark.asyncio
    async def test_mode_off_skips(self, mock_docker, monkeypatch):
        monkeypatch.setattr(settings.cosign, "mode", "off")
        monkeypatch.setattr(settings.cosign, "key", "")

        from brainbox.lifecycle import provision

        with patch("brainbox.lifecycle.verify_image") as mock_verify:
            # Backend flow: images.get, containers.get (for old), containers.create
            mock_docker[0].images.get.return_value = mock_docker[1]
            mock_docker[0].containers.get.side_effect = NotFound("not found")

            ctx = await provision(session_name="test-off")
            mock_verify.assert_not_called()
            assert ctx.state.value == "configuring"

    @pytest.mark.asyncio
    async def test_mode_warn_no_key_continues(self, mock_docker, monkeypatch):
        monkeypatch.setattr(settings.cosign, "mode", "warn")
        monkeypatch.setattr(settings.cosign, "key", "")

        from brainbox.lifecycle import provision

        mock_docker[0].images.get.return_value = mock_docker[1]
        mock_docker[0].containers.get.side_effect = NotFound("not found")

        with patch("brainbox.lifecycle.verify_image") as mock_verify:
            ctx = await provision(session_name="test-warn-nokey")
            mock_verify.assert_not_called()
            assert ctx.state.value == "configuring"

    @pytest.mark.asyncio
    async def test_mode_enforce_no_key_raises(self, mock_docker, monkeypatch):
        monkeypatch.setattr(settings.cosign, "mode", "enforce")
        monkeypatch.setattr(settings.cosign, "key", "")
        monkeypatch.setattr(settings.cosign, "certificate_identity", "")
        monkeypatch.setattr(settings.cosign, "oidc_issuer", "")

        from brainbox.lifecycle import provision

        mock_docker[0].images.get.return_value = mock_docker[1]

        with pytest.raises(ValueError, match="requires either keyless config"):
            await provision(session_name="test-enforce-nokey")

    @pytest.mark.asyncio
    async def test_mode_warn_verification_failure_continues(
        self, mock_docker, monkeypatch, tmp_path
    ):
        key_file = tmp_path / "cosign.pub"
        key_file.write_text("fake-key")
        monkeypatch.setattr(settings.cosign, "mode", "warn")
        monkeypatch.setattr(settings.cosign, "key", str(key_file))

        mock_docker[0].images.get.return_value = mock_docker[1]
        mock_docker[0].containers.get.side_effect = NotFound("not found")

        failed_result = CosignResult(
            verified=False, image_ref="test-image@sha256:abc123", stdout="", stderr="no sig"
        )

        from brainbox.lifecycle import provision

        with patch("brainbox.lifecycle.verify_image", return_value=failed_result):
            ctx = await provision(session_name="test-warn-fail")
            assert ctx.state.value == "configuring"

    @pytest.mark.asyncio
    async def test_mode_enforce_verification_failure_raises(
        self, mock_docker, monkeypatch, tmp_path
    ):
        key_file = tmp_path / "cosign.pub"
        key_file.write_text("fake-key")
        monkeypatch.setattr(settings.cosign, "mode", "enforce")
        monkeypatch.setattr(settings.cosign, "key", str(key_file))

        mock_docker[0].images.get.return_value = mock_docker[1]

        failed_result = CosignResult(
            verified=False, image_ref="test-image@sha256:abc123", stdout="", stderr="no sig"
        )

        from brainbox.lifecycle import provision

        with patch("brainbox.lifecycle.verify_image", return_value=failed_result):
            with pytest.raises(CosignVerificationError, match="test-image@sha256:abc123"):
                await provision(session_name="test-enforce-fail")

    @pytest.mark.asyncio
    async def test_mode_enforce_missing_key_file_raises(self, mock_docker, monkeypatch):
        monkeypatch.setattr(settings.cosign, "mode", "enforce")
        monkeypatch.setattr(settings.cosign, "key", "/nonexistent/cosign.pub")

        mock_docker[0].images.get.return_value = mock_docker[1]

        from brainbox.lifecycle import provision

        with pytest.raises(FileNotFoundError, match="cosign.pub"):
            await provision(session_name="test-enforce-nofile")

    @pytest.mark.asyncio
    async def test_mode_enforce_local_image_raises(self, mock_docker, monkeypatch, tmp_path):
        key_file = tmp_path / "cosign.pub"
        key_file.write_text("fake-key")
        monkeypatch.setattr(settings.cosign, "mode", "enforce")
        monkeypatch.setattr(settings.cosign, "key", str(key_file))

        # Image with no repo digests (local-only)
        mock_docker[1].attrs = {"RepoDigests": []}
        mock_docker[0].images.get.return_value = mock_docker[1]

        from brainbox.lifecycle import provision

        with pytest.raises(ValueError, match="no repo digests"):
            await provision(session_name="test-enforce-local")

    @pytest.mark.asyncio
    async def test_keyless_mode_warn_success(self, mock_docker, monkeypatch):
        monkeypatch.setattr(settings.cosign, "mode", "warn")
        monkeypatch.setattr(settings.cosign, "key", "")
        monkeypatch.setattr(
            settings.cosign, "certificate_identity", "https://github.com/owner/repo/.*"
        )
        monkeypatch.setattr(
            settings.cosign, "oidc_issuer", "https://token.actions.githubusercontent.com"
        )

        mock_docker[0].images.get.return_value = mock_docker[1]
        mock_docker[0].containers.get.side_effect = NotFound("not found")

        ok_result = CosignResult(
            verified=True, image_ref="test-image@sha256:abc123", stdout="ok", stderr=""
        )

        from brainbox.lifecycle import provision

        with patch("brainbox.lifecycle.verify_image_keyless", return_value=ok_result) as mock_kl:
            ctx = await provision(session_name="test-keyless-warn-ok")
            mock_kl.assert_called_once()
            assert ctx.state.value == "configuring"

    @pytest.mark.asyncio
    async def test_keyless_mode_enforce_failure_raises(self, mock_docker, monkeypatch):
        monkeypatch.setattr(settings.cosign, "mode", "enforce")
        monkeypatch.setattr(settings.cosign, "key", "")
        monkeypatch.setattr(
            settings.cosign, "certificate_identity", "https://github.com/owner/repo/.*"
        )
        monkeypatch.setattr(
            settings.cosign, "oidc_issuer", "https://token.actions.githubusercontent.com"
        )

        mock_docker[0].images.get.return_value = mock_docker[1]

        failed_result = CosignResult(
            verified=False, image_ref="test-image@sha256:abc123", stdout="", stderr="no sig"
        )

        from brainbox.lifecycle import provision

        with patch("brainbox.lifecycle.verify_image_keyless", return_value=failed_result):
            with pytest.raises(CosignVerificationError, match="test-image@sha256:abc123"):
                await provision(session_name="test-keyless-enforce-fail")

    @pytest.mark.asyncio
    async def test_keyless_preferred_over_key(self, mock_docker, monkeypatch, tmp_path):
        key_file = tmp_path / "cosign.pub"
        key_file.write_text("fake-key")
        monkeypatch.setattr(settings.cosign, "mode", "warn")
        monkeypatch.setattr(settings.cosign, "key", str(key_file))
        monkeypatch.setattr(
            settings.cosign, "certificate_identity", "https://github.com/owner/repo/.*"
        )
        monkeypatch.setattr(
            settings.cosign, "oidc_issuer", "https://token.actions.githubusercontent.com"
        )

        mock_docker[0].images.get.return_value = mock_docker[1]
        mock_docker[0].containers.get.side_effect = NotFound("not found")

        ok_result = CosignResult(
            verified=True, image_ref="test-image@sha256:abc123", stdout="ok", stderr=""
        )

        from brainbox.lifecycle import provision

        with (
            patch("brainbox.lifecycle.verify_image_keyless", return_value=ok_result) as mock_kl,
            patch("brainbox.lifecycle.verify_image") as mock_key,
        ):
            ctx = await provision(session_name="test-keyless-preferred")
            mock_kl.assert_called_once()
            mock_key.assert_not_called()
            assert ctx.state.value == "configuring"
