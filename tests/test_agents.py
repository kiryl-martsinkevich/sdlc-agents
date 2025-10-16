"""Tests for agent classes."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sdlc_agents.agents.base import Agent, AgentCapability
from sdlc_agents.agents.orchestrator import OrchestratorAgent
from sdlc_agents.agents.requirements_agent import RequirementsAgent
from sdlc_agents.agents.code_repo_agent import CodeRepositoryAgent
from sdlc_agents.agents.build_monitor_agent import BuildMonitorAgent
from sdlc_agents.agents.release_manager_agent import ReleaseManagerAgent


@pytest.mark.unit
class TestBaseAgent:
    """Tests for base Agent class."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_llm_provider, mock_clickhouse_memory):
        """Test agent initialization."""

        class TestAgent(Agent):
            async def process_task(self, task):
                return {"status": "completed"}

        agent = TestAgent(
            agent_id="test-agent",
            name="Test Agent",
            capabilities=[AgentCapability.CODE_ANALYSIS],
            system_prompt="You are a test agent",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
        )

        assert agent.agent_id == "test-agent"
        assert agent.name == "Test Agent"
        assert AgentCapability.CODE_ANALYSIS in agent.capabilities
        assert agent.llm is not None
        assert agent.memory is not None

    @pytest.mark.asyncio
    async def test_think(self, mock_llm_provider, mock_clickhouse_memory):
        """Test thinking process."""

        class TestAgent(Agent):
            async def process_task(self, task):
                return {"status": "completed"}

        agent = TestAgent(
            agent_id="test-agent",
            name="Test Agent",
            capabilities=[AgentCapability.CODE_ANALYSIS],
            system_prompt="You are a test agent",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
        )

        response = await agent.think("Hello, agent", context={"test": "data"})

        assert response.content.startswith("Mock response to:")
        assert mock_clickhouse_memory.store_memory.called

    @pytest.mark.asyncio
    async def test_observe(self, mock_llm_provider, mock_clickhouse_memory):
        """Test observation recording."""

        class TestAgent(Agent):
            async def process_task(self, task):
                return {"status": "completed"}

        agent = TestAgent(
            agent_id="test-agent",
            name="Test Agent",
            capabilities=[AgentCapability.CODE_ANALYSIS],
            system_prompt="You are a test agent",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
        )

        await agent.observe("Test observation", metadata={"key": "value"})

        assert mock_clickhouse_memory.store_memory.called

    @pytest.mark.asyncio
    async def test_decide(self, mock_llm_provider, mock_clickhouse_memory):
        """Test decision recording."""

        class TestAgent(Agent):
            async def process_task(self, task):
                return {"status": "completed"}

        agent = TestAgent(
            agent_id="test-agent",
            name="Test Agent",
            capabilities=[AgentCapability.CODE_ANALYSIS],
            system_prompt="You are a test agent",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
        )

        await agent.decide("Test decision", reasoning="Test reasoning")

        assert mock_clickhouse_memory.store_memory.called

    @pytest.mark.asyncio
    async def test_record_action(self, mock_llm_provider, mock_clickhouse_memory):
        """Test action recording."""

        class TestAgent(Agent):
            async def process_task(self, task):
                return {"status": "completed"}

        agent = TestAgent(
            agent_id="test-agent",
            name="Test Agent",
            capabilities=[AgentCapability.CODE_ANALYSIS],
            system_prompt="You are a test agent",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
        )

        await agent.record_action(
            action_type="test_action",
            target="test_target",
            result={"success": True},
            success=True,
            duration_ms=100,
        )

        assert mock_clickhouse_memory.log_action.called


@pytest.mark.unit
class TestOrchestratorAgent:
    """Tests for Orchestrator Agent."""

    @pytest.mark.asyncio
    async def test_register_agent(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test registering agents."""
        orchestrator = OrchestratorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        requirements_agent = RequirementsAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        orchestrator.register_agent(requirements_agent)

        assert requirements_agent.agent_id in orchestrator.active_agents

    @pytest.mark.asyncio
    async def test_handle_implement_story_message(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test handling implement story message."""
        orchestrator = OrchestratorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        with patch.object(orchestrator, "process_task", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "status": "completed",
                "work_item_id": 12345,
                "message": "Story implemented successfully",
            }

            response = await orchestrator.handle_message("implement story 12345")

            assert "12345" in response
            assert mock_process.called

    @pytest.mark.asyncio
    async def test_handle_split_feature_message(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test handling split feature message."""
        orchestrator = OrchestratorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        with patch.object(orchestrator, "process_task", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "status": "completed",
                "feature_id": 456,
                "stories": [12346, 12347, 12348],
            }

            response = await orchestrator.handle_message("split feature 456")

            assert "456" in response
            assert mock_process.called


@pytest.mark.unit
class TestRequirementsAgent:
    """Tests for Requirements Agent."""

    @pytest.mark.asyncio
    async def test_analyze_requirements(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client, sample_work_item
    ):
        """Test requirements analysis."""
        agent = RequirementsAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        task = {"type": "analyze_requirements", "work_item_id": 12345}

        result = await agent.process_task(task)

        assert result["status"] in ["completed", "failed"]
        assert "work_item_id" in result

    @pytest.mark.asyncio
    async def test_extract_affected_components(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test extracting affected components from requirements."""
        agent = RequirementsAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        # Mock LLM to return structured analysis
        mock_llm_provider.generate = AsyncMock(
            return_value=MagicMock(
                content="Affected components: backend-api, frontend-web\nComplexity: medium"
            )
        )

        task = {"type": "analyze_requirements", "work_item_id": 12345}

        result = await agent.process_task(task)

        # Should extract components from LLM response
        assert result["status"] in ["completed", "failed"]


@pytest.mark.unit
class TestCodeRepositoryAgent:
    """Tests for Code Repository Agent."""

    @pytest.mark.asyncio
    async def test_initialize_repo(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client, tmp_path
    ):
        """Test repository initialization."""
        repo_path = tmp_path / "test-repo"

        agent = CodeRepositoryAgent(
            agent_id="code-agent-test",
            repo_name="test-repo",
            repo_url="https://test.com/repo.git",
            repo_path=repo_path,
            build_definition="Test-CI",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        with patch("git.Repo.clone_from") as mock_clone:
            mock_clone.return_value = MagicMock()
            result = await agent.initialize_repo()

            assert result is True

    @pytest.mark.asyncio
    async def test_implement_changes(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client, mock_git_repo
    ):
        """Test implementing code changes."""
        agent = CodeRepositoryAgent(
            agent_id="code-agent-test",
            repo_name="test-repo",
            repo_url="https://test.com/repo.git",
            repo_path=mock_git_repo,
            build_definition="Test-CI",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        task = {
            "type": "implement_changes",
            "work_item_id": 12345,
            "requirements": "Add user authentication",
            "affected_files": ["src/main/java/Auth.java"],
        }

        with patch("git.Repo") as mock_repo:
            mock_repo.return_value.active_branch.name = "main"
            mock_repo.return_value.git.checkout = MagicMock()
            mock_repo.return_value.git.add = MagicMock()
            mock_repo.return_value.git.commit = MagicMock()
            mock_repo.return_value.git.push = MagicMock()

            with patch.object(agent, "_run_maven_build", new_callable=AsyncMock) as mock_build:
                mock_build.return_value = {
                    "success": True,
                    "exit_code": 0,
                    "stdout": "BUILD SUCCESS",
                }

                result = await agent.process_task(task)

                assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_maven_build_execution(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client, mock_git_repo
    ):
        """Test Maven build execution."""
        agent = CodeRepositoryAgent(
            agent_id="code-agent-test",
            repo_name="test-repo",
            repo_url="https://test.com/repo.git",
            repo_path=mock_git_repo,
            build_definition="Test-CI",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"BUILD SUCCESS", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await agent._run_maven_build()

            assert result["success"] is True
            assert result["exit_code"] == 0


@pytest.mark.unit
class TestBuildMonitorAgent:
    """Tests for Build Monitor Agent."""

    @pytest.mark.asyncio
    async def test_monitor_build_success(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test monitoring successful build."""
        agent = BuildMonitorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        task = {"type": "monitor_build", "build_id": 1, "pr_id": 100}

        # Mock successful build
        mock_ado_client.get_build.return_value = {
            "id": 1,
            "status": "completed",
            "result": "succeeded",
        }

        result = await agent.process_task(task)

        assert result["status"] == "completed"
        assert result["build_result"] == "succeeded"

    @pytest.mark.asyncio
    async def test_analyze_build_failure(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test analyzing build failure."""
        agent = BuildMonitorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        # Mock LLM to classify failure as intermittent
        mock_llm_provider.generate = AsyncMock(
            return_value=MagicMock(content="INTERMITTENT: Network timeout")
        )

        task = {
            "type": "analyze_failure",
            "build_id": 1,
            "build_logs": "Connection timeout...",
        }

        result = await agent.process_task(task)

        assert result["status"] == "completed"
        assert "failure_type" in result

    @pytest.mark.asyncio
    async def test_retry_build(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test retrying failed build."""
        agent = BuildMonitorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        task = {
            "type": "retry_build",
            "definition_name": "Test-CI",
            "branch": "feature/test",
            "pr_id": 100,
        }

        mock_ado_client.queue_build.return_value = {"id": 2, "status": "notStarted"}

        result = await agent.process_task(task)

        assert result["status"] == "completed"
        assert "new_build_id" in result


@pytest.mark.unit
class TestReleaseManagerAgent:
    """Tests for Release Manager Agent."""

    @pytest.mark.asyncio
    async def test_create_release(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test creating a release."""
        agent = ReleaseManagerAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        task = {
            "type": "create_release",
            "components": ["backend-api", "frontend-web"],
            "source_branch": "main",
            "version": "1.0.0",
        }

        # Mock release work item creation
        mock_ado_client.create_work_item.return_value = {
            "id": 12350,
            "type": "Release",
            "title": "Release 1.0.0",
        }

        result = await agent.process_task(task)

        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_verify_release_readiness(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test verifying release readiness."""
        agent = ReleaseManagerAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        task = {
            "type": "verify_readiness",
            "components": ["backend-api"],
            "branch": "main",
        }

        # Mock successful build
        mock_ado_client.get_build.return_value = {
            "id": 1,
            "status": "completed",
            "result": "succeeded",
        }

        result = await agent.process_task(task)

        assert result["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_generate_release_notes(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test generating release notes."""
        agent = ReleaseManagerAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        # Mock LLM to generate release notes
        mock_llm_provider.generate = AsyncMock(
            return_value=MagicMock(
                content="## Release 1.0.0\n\n- Feature 1\n- Feature 2\n- Bug fixes"
            )
        )

        task = {
            "type": "generate_notes",
            "stories": [12345, 12346, 12347],
            "version": "1.0.0",
        }

        result = await agent.process_task(task)

        assert result["status"] == "completed"
        assert "release_notes" in result
