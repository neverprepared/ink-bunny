"""Tests for Ollama LLM provider lifecycle integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docker.errors import NotFound

from brainbox.config import Settings, settings
from brainbox.models import SessionContext, SessionState


# ---------------------------------------------------------------------------
# configure() — Ollama env var injection
# ---------------------------------------------------------------------------


@pytest.fixture()
def ollama_ctx():
    """A SessionContext configured for Ollama."""
    return SessionContext(
        session_name="test-ollama",
        container_name="developer-test-ollama",
        port=7681,
        created_at=0,
        ttl=3600,
        llm_provider="ollama",
        llm_model="qwen3-coder",
        ollama_host=None,
    )


@pytest.fixture()
def claude_ctx():
    """A SessionContext configured for Claude (default)."""
    return SessionContext(
        session_name="test-claude",
        container_name="developer-test-claude",
        port=7682,
        created_at=0,
        ttl=3600,
    )


@pytest.fixture()
def mock_sessions(ollama_ctx, claude_ctx):
    """Patch lifecycle._sessions so _resolve() works."""
    sessions = {
        ollama_ctx.session_name: ollama_ctx,
        claude_ctx.session_name: claude_ctx,
    }
    with patch("brainbox.lifecycle._sessions", sessions):
        yield sessions


class TestConfigureOllama:
    @pytest.mark.asyncio
    async def test_injects_ollama_env_vars(self, ollama_ctx, mock_sessions):
        # Mock backend to avoid Docker dependency
        mock_backend = MagicMock()
        mock_backend.configure = AsyncMock(side_effect=lambda ctx, **kwargs: ctx)

        with (
            patch("brainbox.secrets.resolve_secrets", return_value={}),
            patch("brainbox.secrets.has_op_integration", return_value=False),
            patch("brainbox.backends.create_backend", return_value=mock_backend),
        ):
            from brainbox.lifecycle import configure

            ctx = await configure(ollama_ctx)

        assert ctx.secrets["ANTHROPIC_AUTH_TOKEN"] == "ollama"
        assert ctx.secrets["ANTHROPIC_API_KEY"] == ""
        assert ctx.secrets["ANTHROPIC_BASE_URL"] == settings.ollama.host
        assert ctx.secrets["CLAUDE_MODEL"] == "qwen3-coder"

    @pytest.mark.asyncio
    async def test_uses_default_url_when_not_specified(self, ollama_ctx, mock_sessions):
        ollama_ctx.ollama_host = None
        mock_backend = MagicMock()
        mock_backend.configure = AsyncMock(side_effect=lambda ctx, **kwargs: ctx)

        with (
            patch("brainbox.secrets.resolve_secrets", return_value={}),
            patch("brainbox.secrets.has_op_integration", return_value=False),
            patch("brainbox.backends.create_backend", return_value=mock_backend),
        ):
            from brainbox.lifecycle import configure

            ctx = await configure(ollama_ctx)

        assert ctx.secrets["ANTHROPIC_BASE_URL"] == "http://host.docker.internal:11434"

    @pytest.mark.asyncio
    async def test_uses_custom_url_when_specified(self, ollama_ctx, mock_sessions):
        ollama_ctx.ollama_host = "http://gpu-box:11434"
        mock_backend = MagicMock()
        mock_backend.configure = AsyncMock(side_effect=lambda ctx, **kwargs: ctx)

        with (
            patch("brainbox.secrets.resolve_secrets", return_value={}),
            patch("brainbox.secrets.has_op_integration", return_value=False),
            patch("brainbox.backends.create_backend", return_value=mock_backend),
        ):
            from brainbox.lifecycle import configure

            ctx = await configure(ollama_ctx)

        assert ctx.secrets["ANTHROPIC_BASE_URL"] == "http://gpu-box:11434"

    @pytest.mark.asyncio
    async def test_uses_default_model_when_not_specified(self, mock_sessions):
        ctx = SessionContext(
            session_name="test-ollama",
            container_name="developer-test-ollama",
            port=7681,
            created_at=0,
            ttl=3600,
            llm_provider="ollama",
            llm_model=None,
        )
        mock_sessions["test-ollama"] = ctx
        mock_backend = MagicMock()
        mock_backend.configure = AsyncMock(side_effect=lambda ctx, **kwargs: ctx)

        with (
            patch("brainbox.secrets.resolve_secrets", return_value={}),
            patch("brainbox.secrets.has_op_integration", return_value=False),
            patch("brainbox.backends.create_backend", return_value=mock_backend),
        ):
            from brainbox.lifecycle import configure

            ctx = await configure(ctx)

        assert ctx.secrets["CLAUDE_MODEL"] == settings.ollama.model

    @pytest.mark.asyncio
    async def test_preserves_secrets_for_claude(self, claude_ctx, mock_sessions):
        base_secrets = {"ANTHROPIC_API_KEY": "sk-real-key", "GH_TOKEN": "ghp_abc"}
        mock_backend = MagicMock()
        mock_backend.configure = AsyncMock(side_effect=lambda ctx, **kwargs: ctx)

        with (
            patch("brainbox.secrets.resolve_secrets", return_value=dict(base_secrets)),
            patch("brainbox.secrets.has_op_integration", return_value=False),
            patch("brainbox.backends.create_backend", return_value=mock_backend),
        ):
            from brainbox.lifecycle import configure

            ctx = await configure(claude_ctx)

        assert ctx.secrets["ANTHROPIC_API_KEY"] == "sk-real-key"
        assert ctx.secrets["GH_TOKEN"] == "ghp_abc"
        assert "ANTHROPIC_AUTH_TOKEN" not in ctx.secrets
        assert "ANTHROPIC_BASE_URL" not in ctx.secrets
        assert "CLAUDE_MODEL" not in ctx.secrets


# ---------------------------------------------------------------------------
# provision() — Docker labels
# ---------------------------------------------------------------------------


class TestProvisionLabels:
    @pytest.mark.asyncio
    async def test_labels_include_llm_provider(self):
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
        ):
            from brainbox.lifecycle import provision

            ctx = await provision(
                session_name="label-test",
                llm_provider="ollama",
                llm_model="glm-4.7",
            )

        create_call = mock_client.containers.create.call_args
        labels = create_call[1]["labels"]
        assert labels["brainbox.llm_provider"] == "ollama"
        assert labels["brainbox.llm_model"] == "glm-4.7"

    @pytest.mark.asyncio
    async def test_labels_default_to_claude(self):
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
        ):
            from brainbox.lifecycle import provision

            ctx = await provision(session_name="label-test-claude")

        create_call = mock_client.containers.create.call_args
        labels = create_call[1]["labels"]
        assert labels["brainbox.llm_provider"] == "claude"
        assert labels["brainbox.llm_model"] == ""
