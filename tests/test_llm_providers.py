"""Tests for LLM providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sdlc_agents.llm.base import LLMMessage, LLMResponse, MessageRole
from sdlc_agents.llm.ollama_provider import OllamaProvider
from sdlc_agents.llm.openai_provider import OpenAIProvider
from sdlc_agents.llm.factory import get_llm_provider


@pytest.mark.unit
class TestOllamaProvider:
    """Tests for Ollama provider."""

    @pytest.mark.asyncio
    async def test_generate(self):
        """Test generating a response."""
        provider = OllamaProvider("http://localhost:11434", "test-model")

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant"),
            LLMMessage(role=MessageRole.USER, content="Hello"),
        ]

        # Mock the HTTP request
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "message": {"content": "Hello! How can I help you?"},
                    "model": "test-model",
                    "eval_count": 50,
                    "done_reason": "stop",
                }
            )
            mock_post.return_value.__aenter__.return_value = mock_response

            response = await provider.generate(messages)

            assert response.content == "Hello! How can I help you?"
            assert response.model == "test-model"
            assert response.tokens_used == 50
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        provider = OllamaProvider("http://localhost:11434", "test-model")

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        provider = OllamaProvider("http://localhost:11434", "test-model")

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            result = await provider.health_check()
            assert result is False


@pytest.mark.unit
class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    @pytest.mark.asyncio
    async def test_generate(self):
        """Test generating a response."""
        provider = OpenAIProvider("test-api-key", "gpt-4", "https://api.openai.com/v1")

        messages = [
            LLMMessage(role=MessageRole.USER, content="Hello"),
        ]

        # Mock OpenAI client
        with patch.object(provider.client.chat.completions, "create") as mock_create:
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(
                    message=MagicMock(content="Hello! How can I assist you?"),
                    finish_reason="stop",
                )
            ]
            mock_response.model = "gpt-4"
            mock_response.usage = MagicMock(total_tokens=75)
            mock_response.model_dump = MagicMock(return_value={})
            mock_create.return_value = mock_response

            response = await provider.generate(messages)

            assert response.content == "Hello! How can I assist you?"
            assert response.model == "gpt-4"
            assert response.tokens_used == 75

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        provider = OpenAIProvider("test-api-key", "gpt-4")

        with patch.object(provider.client.models, "list") as mock_list:
            mock_list.return_value = []

            result = await provider.health_check()
            assert result is True


@pytest.mark.unit
class TestLLMFactory:
    """Tests for LLM factory."""

    def test_get_ollama_provider(self, monkeypatch):
        """Test getting Ollama provider."""
        from sdlc_agents.config import settings

        monkeypatch.setattr(settings, "llm_provider", "ollama")

        provider = get_llm_provider()
        assert isinstance(provider, OllamaProvider)

    def test_get_openai_provider(self, monkeypatch):
        """Test getting OpenAI provider."""
        from sdlc_agents.config import settings

        monkeypatch.setattr(settings, "llm_provider", "openai")
        monkeypatch.setattr(settings, "openai_api_key", "test-key")

        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)

    def test_missing_openai_key(self, monkeypatch):
        """Test error when OpenAI key is missing."""
        from sdlc_agents.config import settings

        monkeypatch.setattr(settings, "llm_provider", "openai")
        monkeypatch.setattr(settings, "openai_api_key", None)

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            get_llm_provider()
