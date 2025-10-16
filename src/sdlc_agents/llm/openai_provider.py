"""OpenAI and OpenAI-compatible LLM provider implementation."""

from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI

from sdlc_agents.llm.base import LLMMessage, LLMProvider, LLMResponse, MessageRole
from sdlc_agents.logging_config import logger


class OpenAIProvider(LLMProvider):
    """LLM provider for OpenAI and OpenAI-compatible APIs."""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name to use
            base_url: Optional base URL for OpenAI-compatible APIs
        """
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate response using OpenAI."""
        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role.value, "content": msg.content} for msg in messages
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else None,
                finish_reason=response.choices[0].finish_reason,
                raw_response=response.model_dump(),
            )
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream responses from OpenAI."""
        openai_messages = [
            {"role": msg.role.value, "content": msg.content} for msg in messages
        ]

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if OpenAI API is available."""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the OpenAI client."""
        await self.client.close()
