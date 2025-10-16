"""Factory for creating LLM providers."""

from sdlc_agents.config import LLMProvider as LLMProviderType
from sdlc_agents.config import settings
from sdlc_agents.llm.base import LLMProvider
from sdlc_agents.llm.ollama_provider import OllamaProvider
from sdlc_agents.llm.openai_provider import OpenAIProvider


def get_llm_provider() -> LLMProvider:
    """
    Create an LLM provider based on configuration.

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider type is unsupported
    """
    if settings.llm_provider == LLMProviderType.OLLAMA:
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    elif settings.llm_provider == LLMProviderType.OPENAI:
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
