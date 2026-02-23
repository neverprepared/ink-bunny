"""Tests for Ollama LLM provider data model and configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

from brainbox.config import OllamaSettings, Settings
from brainbox.models import SessionContext, SessionState


# ---------------------------------------------------------------------------
# SessionContext defaults
# ---------------------------------------------------------------------------


class TestSessionContextLLMDefaults:
    def test_defaults_to_claude(self):
        ctx = SessionContext(
            session_name="test",
            container_name="dev-test",
            port=7681,
            created_at=0,
            ttl=3600,
        )
        assert ctx.llm_provider == "claude"
        assert ctx.llm_model is None
        assert ctx.ollama_host is None

    def test_ollama_fields(self):
        ctx = SessionContext(
            session_name="test",
            container_name="dev-test",
            port=7681,
            created_at=0,
            ttl=3600,
            llm_provider="ollama",
            llm_model="qwen3-coder",
            ollama_host="http://gpu-box:11434",
        )
        assert ctx.llm_provider == "ollama"
        assert ctx.llm_model == "qwen3-coder"
        assert ctx.ollama_host == "http://gpu-box:11434"


# ---------------------------------------------------------------------------
# OllamaSettings
# ---------------------------------------------------------------------------


class TestOllamaSettings:
    def test_defaults(self):
        s = OllamaSettings()
        assert s.host == "http://host.docker.internal:11434"
        assert s.model == "qwen3:8b"

    def test_env_override(self):
        with patch.dict(
            os.environ,
            {
                "CL_OLLAMA__HOST": "http://my-gpu:11434",
                "CL_OLLAMA__MODEL": "glm-4.7",
            },
        ):
            s = Settings()
            assert s.ollama.host == "http://my-gpu:11434"
            assert s.ollama.model == "glm-4.7"

    def test_settings_includes_ollama(self):
        s = Settings()
        assert hasattr(s, "ollama")
        assert isinstance(s.ollama, OllamaSettings)
