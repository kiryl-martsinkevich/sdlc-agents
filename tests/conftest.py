"""Pytest configuration and fixtures."""

import asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch

from sdlc_agents.config import Settings
from sdlc_agents.llm.base import LLMMessage, LLMProvider, LLMResponse, MessageRole
from sdlc_agents.memory.clickhouse_memory import ClickHouseMemory


@pytest.fixture
def mock_settings(tmp_path: Path, monkeypatch: MonkeyPatch) -> Settings:
    """Create mock settings for testing."""
    workspace = tmp_path / "workspace"
    repos = tmp_path / "repos"
    workspace.mkdir()
    repos.mkdir()

    settings = Settings(
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="test-model",
        clickhouse_host="localhost",
        clickhouse_port=8123,
        clickhouse_database="test_sdlc_agents",
        ado_organization="test-org",
        ado_project="test-project",
        ado_pat="test-pat",
        workspace_dir=workspace,
        repos_dir=repos,
    )

    # Patch the global settings
    monkeypatch.setattr("sdlc_agents.config.settings", settings)

    return settings


@pytest.fixture
def mock_llm_provider() -> LLMProvider:
    """Create a mock LLM provider."""

    class MockLLMProvider(LLMProvider):
        async def generate(
            self, messages, temperature=0.7, max_tokens=None, **kwargs
        ) -> LLMResponse:
            # Simple mock response based on last message
            last_message = messages[-1].content if messages else ""
            response_content = f"Mock response to: {last_message[:50]}"

            return LLMResponse(
                content=response_content,
                model="mock-model",
                tokens_used=100,
                finish_reason="stop",
            )

        async def stream_generate(
            self, messages, temperature=0.7, max_tokens=None, **kwargs
        ):
            yield "Mock "
            yield "streaming "
            yield "response"

        async def health_check(self) -> bool:
            return True

    return MockLLMProvider()


@pytest.fixture
def mock_clickhouse_memory(monkeypatch: MonkeyPatch) -> MagicMock:
    """Create a mock ClickHouse memory."""
    mock_client = MagicMock()
    mock_memory = MagicMock(spec=ClickHouseMemory)
    mock_memory.client = mock_client
    mock_memory.store_memory = MagicMock()
    mock_memory.get_recent_memories = MagicMock(return_value=[])
    mock_memory.log_action = MagicMock()
    mock_memory.get_agent_statistics = MagicMock(return_value={})
    mock_memory.store_work_item = MagicMock()
    mock_memory.get_work_item = MagicMock(return_value=None)
    mock_memory.search_memories = MagicMock(return_value=[])

    return mock_memory


@pytest.fixture
def mock_ado_client() -> MagicMock:
    """Create a mock Azure DevOps client."""
    mock_client = MagicMock()

    # Mock work item
    mock_client.get_work_item.return_value = {
        "id": 12345,
        "type": "User Story",
        "title": "Test Story",
        "description": "Test description",
        "state": "New",
        "assigned_to": "Test User",
        "tags": "test",
        "acceptance_criteria": "Should work correctly",
        "fields": {},
    }

    mock_client.create_work_item.return_value = {
        "id": 12346,
        "type": "User Story",
        "title": "Created Story",
        "description": "Created",
        "state": "New",
    }

    # Mock build
    mock_client.get_build.return_value = {
        "id": 1,
        "build_number": "20250101.1",
        "status": "completed",
        "result": "succeeded",
        "source_branch": "refs/heads/main",
        "source_version": "abc123",
        "definition": "Test-CI",
    }

    mock_client.queue_build.return_value = {
        "id": 2,
        "build_number": "20250101.2",
        "status": "notStarted",
    }

    # Mock PR
    mock_client.create_pull_request.return_value = {
        "id": 100,
        "title": "Test PR",
        "description": "Test PR description",
        "status": "active",
        "source_branch": "feature/test",
        "target_branch": "main",
    }

    return mock_client


@pytest.fixture
def sample_work_item() -> dict:
    """Sample work item for testing."""
    return {
        "id": 12345,
        "type": "User Story",
        "title": "Implement user authentication",
        "description": "As a user, I want to log in with my credentials",
        "state": "New",
        "assigned_to": "Test User",
        "tags": "authentication,security",
        "acceptance_criteria": "User can log in and log out successfully",
        "fields": {
            "System.WorkItemType": "User Story",
            "System.Title": "Implement user authentication",
            "System.State": "New",
        },
    }


@pytest.fixture
def sample_repository_config(tmp_path: Path) -> Path:
    """Create a sample repository configuration file."""
    config_content = """
repositories:
  - name: test-backend
    url: https://dev.azure.com/test/project/_git/backend
    ado_repo_id: "test-repo-id"
    build_definition: "Backend-CI"
    description: "Test backend repository"
    enabled: true

  - name: test-frontend
    url: https://dev.azure.com/test/project/_git/frontend
    ado_repo_id: "test-frontend-id"
    build_definition: "Frontend-CI"
    description: "Test frontend repository"
    enabled: true

  - name: disabled-repo
    url: https://dev.azure.com/test/project/_git/disabled
    enabled: false

component_groups:
  full_stack:
    - test-backend
    - test-frontend
  backend:
    - test-backend
"""
    config_path = tmp_path / "repositories.yaml"
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
async def mock_git_repo(tmp_path: Path) -> Path:
    """Create a mock git repository."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Create basic Maven structure
    (repo_path / "pom.xml").write_text("""
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>test-app</artifactId>
    <version>1.0.0</version>
</project>
""")

    src_main = repo_path / "src" / "main" / "java"
    src_main.mkdir(parents=True)
    (src_main / "Main.java").write_text("public class Main {}")

    src_test = repo_path / "src" / "test" / "java"
    src_test.mkdir(parents=True)
    (src_test / "MainTest.java").write_text("public class MainTest {}")

    return repo_path


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
