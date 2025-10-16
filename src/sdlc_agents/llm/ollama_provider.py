"""Ollama LLM provider implementation."""

import asyncio
from typing import Any, AsyncIterator, Optional

import aiohttp

from sdlc_agents.llm.base import LLMMessage, LLMProvider, LLMResponse, MessageRole
from sdlc_agents.logging_config import logger


class OllamaProvider(LLMProvider):
    """LLM provider for Ollama."""

    def __init__(self, base_url: str, model: str):
        """
        Initialize Ollama provider.

        Args:
            base_url: Base URL for Ollama API
            model: Model name to use
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate response using Ollama."""
        session = await self._get_session()

        # Convert messages to Ollama format
        ollama_messages = [
            {"role": msg.role.value, "content": msg.content} for msg in messages
        ]

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Add any additional options
        if kwargs:
            payload["options"].update(kwargs)

        try:
            async with session.post(
                f"{self.base_url}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                data = await response.json()

                return LLMResponse(
                    content=data["message"]["content"],
                    model=data.get("model", self.model),
                    tokens_used=data.get("eval_count"),
                    finish_reason=data.get("done_reason"),
                    raw_response=data,
                )
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream responses from Ollama."""
        session = await self._get_session()

        ollama_messages = [
            {"role": msg.role.value, "content": msg.content} for msg in messages
        ]

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        if kwargs:
            payload["options"].update(kwargs)

        try:
            async with session.post(
                f"{self.base_url}/api/chat", json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.content:
                    if line:
                        import json

                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Ollama is available."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
