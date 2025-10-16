"""Integration tests for end-to-end workflows."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sdlc_agents.agents.orchestrator import OrchestratorAgent
from sdlc_agents.agents.requirements_agent import RequirementsAgent
from sdlc_agents.agents.code_repo_agent import CodeRepositoryAgent
from sdlc_agents.agents.build_monitor_agent import BuildMonitorAgent
from sdlc_agents.agents.release_manager_agent import ReleaseManagerAgent


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_implement_story_workflow(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client, mock_git_repo
    ):
        """Test complete story implementation workflow."""
        # Setup orchestrator with all agents
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

        code_agent = CodeRepositoryAgent(
            agent_id="code-agent-backend",
            repo_name="backend-api",
            repo_url="https://test.com/backend.git",
            repo_path=mock_git_repo,
            build_definition="Backend-CI",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        build_monitor = BuildMonitorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        # Register agents
        orchestrator.register_agent(requirements_agent)
        orchestrator.register_agent(code_agent)
        orchestrator.register_agent(build_monitor)

        # Mock repository initialization
        with patch.object(code_agent, "initialize_repo", new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True

            # Mock Maven build
            with patch.object(
                code_agent, "_run_maven_build", new_callable=AsyncMock
            ) as mock_build:
                mock_build.return_value = {
                    "success": True,
                    "exit_code": 0,
                    "stdout": "BUILD SUCCESS",
                }

                # Mock Git operations
                with patch("git.Repo") as mock_repo:
                    mock_repo.return_value.active_branch.name = "main"
                    mock_repo.return_value.git.checkout = MagicMock()
                    mock_repo.return_value.git.add = MagicMock()
                    mock_repo.return_value.git.commit = MagicMock()
                    mock_repo.return_value.git.push = MagicMock()

                    # Execute workflow
                    response = await orchestrator.handle_message("implement story 12345")

                    # Verify workflow completed
                    assert "12345" in response
                    assert mock_clickhouse_memory.store_memory.called
                    assert mock_clickhouse_memory.log_action.called

    @pytest.mark.asyncio
    async def test_split_feature_workflow(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test feature splitting workflow."""
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

        # Mock feature work item
        mock_ado_client.get_work_item.return_value = {
            "id": 456,
            "type": "Feature",
            "title": "User Authentication System",
            "description": "Complete authentication system with login, logout, and session management",
            "state": "New",
        }

        # Mock story creation
        mock_ado_client.split_feature_into_stories.return_value = [
            {"id": 12346, "type": "User Story", "title": "Story 1"},
            {"id": 12347, "type": "User Story", "title": "Story 2"},
            {"id": 12348, "type": "User Story", "title": "Story 3"},
        ]

        # Execute workflow
        response = await orchestrator.handle_message("split feature 456 into 3 stories")

        # Verify workflow completed
        assert "456" in response
        assert mock_ado_client.split_feature_into_stories.called

    @pytest.mark.asyncio
    async def test_create_release_workflow(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test release creation workflow."""
        orchestrator = OrchestratorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        release_manager = ReleaseManagerAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        orchestrator.register_agent(release_manager)

        # Mock successful builds
        mock_ado_client.get_build.return_value = {
            "id": 1,
            "status": "completed",
            "result": "succeeded",
        }

        # Mock release work item creation
        mock_ado_client.create_work_item.return_value = {
            "id": 12350,
            "type": "Release",
            "title": "Release 1.0.0",
        }

        # Execute workflow
        response = await orchestrator.handle_message(
            "create a release for backend-api, frontend-web from main"
        )

        # Verify workflow completed
        assert "release" in response.lower()
        assert mock_ado_client.create_work_item.called

    @pytest.mark.asyncio
    async def test_build_failure_and_retry_workflow(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client
    ):
        """Test build failure detection and retry workflow."""
        build_monitor = BuildMonitorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        # First call: build failed
        mock_ado_client.get_build.side_effect = [
            {
                "id": 1,
                "status": "completed",
                "result": "failed",
                "logs": "Connection timeout",
            },
            {
                "id": 2,
                "status": "completed",
                "result": "succeeded",
            },
        ]

        # Mock LLM to classify as intermittent
        mock_llm_provider.generate = AsyncMock(
            return_value=MagicMock(content="INTERMITTENT: Network timeout")
        )

        # Mock retry build
        mock_ado_client.queue_build.return_value = {"id": 2, "status": "notStarted"}

        # Monitor first build
        task = {"type": "monitor_build", "build_id": 1, "pr_id": 100}
        result = await build_monitor.process_task(task)

        # Should detect failure
        assert result["build_result"] == "failed"

        # Analyze failure
        analysis_task = {
            "type": "analyze_failure",
            "build_id": 1,
            "build_logs": "Connection timeout",
        }
        analysis_result = await build_monitor.process_task(analysis_task)

        # Should classify as intermittent
        assert "intermittent" in analysis_result["failure_type"].lower()

        # Retry build
        retry_task = {
            "type": "retry_build",
            "definition_name": "Test-CI",
            "branch": "feature/test",
            "pr_id": 100,
        }
        retry_result = await build_monitor.process_task(retry_task)

        # Should successfully retry
        assert retry_result["status"] == "completed"
        assert "new_build_id" in retry_result

    @pytest.mark.asyncio
    async def test_multi_repo_implementation_workflow(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client, tmp_path
    ):
        """Test implementing changes across multiple repositories."""
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

        # Create multiple code agents for different repos
        backend_agent = CodeRepositoryAgent(
            agent_id="code-agent-backend",
            repo_name="backend-api",
            repo_url="https://test.com/backend.git",
            repo_path=tmp_path / "backend",
            build_definition="Backend-CI",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        frontend_agent = CodeRepositoryAgent(
            agent_id="code-agent-frontend",
            repo_name="frontend-web",
            repo_url="https://test.com/frontend.git",
            repo_path=tmp_path / "frontend",
            build_definition="Frontend-CI",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        # Register all agents
        orchestrator.register_agent(requirements_agent)
        orchestrator.register_agent(backend_agent)
        orchestrator.register_agent(frontend_agent)

        # Mock LLM to indicate both components affected
        mock_llm_provider.generate = AsyncMock(
            return_value=MagicMock(
                content="Affected components: backend-api, frontend-web\nComplexity: high"
            )
        )

        # Mock repository operations
        with patch("git.Repo.clone_from") as mock_clone:
            mock_clone.return_value = MagicMock()

            with patch("git.Repo") as mock_repo:
                mock_repo.return_value.active_branch.name = "main"

                # Execute workflow
                response = await orchestrator.handle_message("implement story 12345")

                # Verify both agents were involved
                assert mock_clickhouse_memory.log_action.call_count >= 2

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(
        self, mock_llm_provider, mock_clickhouse_memory, mock_ado_client, mock_git_repo
    ):
        """Test error handling and recovery mechanisms."""
        orchestrator = OrchestratorAgent(
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        code_agent = CodeRepositoryAgent(
            agent_id="code-agent-test",
            repo_name="test-repo",
            repo_url="https://test.com/test.git",
            repo_path=mock_git_repo,
            build_definition="Test-CI",
            llm_provider=mock_llm_provider,
            memory=mock_clickhouse_memory,
            ado_client=mock_ado_client,
        )

        orchestrator.register_agent(code_agent)

        # Simulate build failure
        with patch.object(code_agent, "_run_maven_build", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = {
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": "Test failures",
            }

            task = {
                "type": "implement_changes",
                "work_item_id": 12345,
                "requirements": "Add feature",
            }

            result = await code_agent.process_task(task)

            # Should handle failure gracefully
            assert result["status"] == "failed"
            assert "error" in result or "message" in result

            # Verify error was logged
            assert mock_clickhouse_memory.log_action.called
