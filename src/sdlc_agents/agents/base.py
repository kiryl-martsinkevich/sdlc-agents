"""Base agent class with memory and LLM capabilities."""

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sdlc_agents.llm import LLMMessage, LLMProvider, LLMResponse, MessageRole, get_llm_provider
from sdlc_agents.logging_config import logger
from sdlc_agents.memory import ClickHouseMemory, MemoryEntry


class AgentCapability(str, Enum):
    """Capabilities that agents can have."""

    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    BUILD_MONITORING = "build_monitoring"
    TESTING = "testing"
    GIT_OPERATIONS = "git_operations"
    ADO_INTEGRATION = "ado_integration"
    RELEASE_MANAGEMENT = "release_management"
    ORCHESTRATION = "orchestration"


class Agent(ABC):
    """Base class for all agents in the system."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: list[AgentCapability],
        system_prompt: str,
        llm_provider: Optional[LLMProvider] = None,
        memory: Optional[ClickHouseMemory] = None,
    ):
        """
        Initialize an agent.

        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable name
            capabilities: List of agent capabilities
            system_prompt: System prompt defining agent behavior
            llm_provider: LLM provider (creates default if None)
            memory: Memory store (creates default if None)
        """
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities
        self.system_prompt = system_prompt
        self.llm = llm_provider or get_llm_provider()
        self.memory = memory or ClickHouseMemory()
        self.session_id = str(uuid.uuid4())

        logger.info(f"Initialized agent: {name} ({agent_id})")

    def _store_memory(
        self,
        memory_type: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Store a memory entry."""
        entry = MemoryEntry(
            agent_id=self.agent_id,
            timestamp=datetime.now(),
            memory_type=memory_type,
            content=content,
            metadata=metadata or {},
            session_id=self.session_id,
        )
        self.memory.store_memory(entry)

    def _log_action(
        self,
        action_type: str,
        target: str,
        parameters: dict[str, Any],
        result: Any,
        success: bool,
        duration_ms: int,
    ) -> None:
        """Log an agent action."""
        self.memory.log_action(
            agent_id=self.agent_id,
            action_type=action_type,
            target=target,
            parameters=parameters,
            result=result,
            success=success,
            duration_ms=duration_ms,
            session_id=self.session_id,
        )

    async def think(
        self,
        user_message: str,
        context: Optional[dict[str, Any]] = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Generate a response using the LLM.

        Args:
            user_message: User's input
            context: Additional context
            temperature: LLM temperature

        Returns:
            LLM response
        """
        start_time = time.time()

        # Build message history
        messages = [LLMMessage(role=MessageRole.SYSTEM, content=self.system_prompt)]

        # Add relevant memories
        recent_memories = self.memory.get_recent_memories(
            agent_id=self.agent_id,
            limit=10,
            session_id=self.session_id,
            hours=24,
        )

        if recent_memories:
            memory_context = "Recent context:\n" + "\n".join(
                [f"- {m.content[:200]}" for m in recent_memories[:5]]
            )
            messages.append(LLMMessage(role=MessageRole.SYSTEM, content=memory_context))

        # Add context if provided
        if context:
            context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            messages.append(
                LLMMessage(role=MessageRole.SYSTEM, content=f"Context:\n{context_str}")
            )

        # Add user message
        messages.append(LLMMessage(role=MessageRole.USER, content=user_message))

        try:
            response = await self.llm.generate(messages, temperature=temperature)

            duration_ms = int((time.time() - start_time) * 1000)

            # Store conversation in memory
            self._store_memory(
                memory_type="conversation",
                content=f"User: {user_message}\nAssistant: {response.content}",
                metadata={"tokens": response.tokens_used, "model": response.model},
            )

            self._log_action(
                action_type="think",
                target="llm",
                parameters={"message": user_message[:200]},
                result={"content": response.content[:200]},
                success=True,
                duration_ms=duration_ms,
            )

            return response
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Agent {self.name} think failed: {e}")

            self._log_action(
                action_type="think",
                target="llm",
                parameters={"message": user_message[:200]},
                result={"error": str(e)},
                success=False,
                duration_ms=duration_ms,
            )
            raise

    async def observe(self, observation: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """
        Record an observation.

        Args:
            observation: What was observed
            metadata: Additional metadata
        """
        self._store_memory(
            memory_type="observation",
            content=observation,
            metadata=metadata or {},
        )
        logger.debug(f"Agent {self.name} observed: {observation[:100]}")

    async def decide(self, decision: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """
        Record a decision.

        Args:
            decision: The decision made
            metadata: Additional metadata
        """
        self._store_memory(
            memory_type="decision",
            content=decision,
            metadata=metadata or {},
        )
        logger.info(f"Agent {self.name} decided: {decision[:100]}")

    async def record_action(
        self, action: str, metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Record an action taken.

        Args:
            action: Description of action
            metadata: Additional metadata
        """
        self._store_memory(
            memory_type="action",
            content=action,
            metadata=metadata or {},
        )
        logger.info(f"Agent {self.name} action: {action[:100]}")

    async def record_result(
        self, result: str, metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Record a result.

        Args:
            result: Description of result
            metadata: Additional metadata
        """
        self._store_memory(
            memory_type="result",
            content=result,
            metadata=metadata or {},
        )

    def get_statistics(self, hours: int = 24) -> dict[str, Any]:
        """Get agent activity statistics."""
        return self.memory.get_agent_statistics(self.agent_id, hours)

    def search_memories(self, query: str, limit: int = 50) -> list[MemoryEntry]:
        """Search agent's memories."""
        return self.memory.search_memories(self.agent_id, query, limit)

    @abstractmethod
    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Process a task assigned to this agent.

        Args:
            task: Task details

        Returns:
            Task result
        """
        pass

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if hasattr(self.llm, "close"):
            await self.llm.close()
