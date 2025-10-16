"""Basic usage examples for SDLC agents."""

import asyncio

from sdlc_agents.agents.orchestrator import OrchestratorAgent
from sdlc_agents.agents.requirements_agent import RequirementsAgent
from sdlc_agents.agents.code_repo_agent import CodeRepositoryAgent


async def example_implement_story():
    """Example: Implement a story from Azure DevOps."""
    # Initialize orchestrator
    orchestrator = OrchestratorAgent()

    # Initialize and register specialized agents
    req_agent = RequirementsAgent()
    orchestrator.register_agent(req_agent)

    # Initialize code repository agent
    code_agent = CodeRepositoryAgent(
        repo_name="my-backend",
        repo_url="https://dev.azure.com/org/project/_git/backend",
    )
    await code_agent.initialize_repo()
    orchestrator.register_agent(code_agent)

    # Process a story
    result = await orchestrator.process_task({
        "type": "implement_story",
        "story_id": 12345,
    })

    print(f"Result: {result}")

    # Cleanup
    await orchestrator.cleanup()


async def example_split_feature():
    """Example: Split a feature into stories."""
    orchestrator = OrchestratorAgent()

    result = await orchestrator.process_task({
        "type": "split_feature",
        "feature_id": 456,
        "story_count": 5,
    })

    print(f"Result: {result}")

    await orchestrator.cleanup()


async def example_create_release():
    """Example: Create a release."""
    orchestrator = OrchestratorAgent()

    # Register release manager
    from sdlc_agents.agents.release_manager_agent import ReleaseManagerAgent
    release_manager = ReleaseManagerAgent()
    orchestrator.register_agent(release_manager)

    result = await orchestrator.process_task({
        "type": "create_release",
        "components": ["backend", "frontend", "api"],
        "source_branch": "main",
    })

    print(f"Result: {result}")

    await orchestrator.cleanup()


async def example_interactive():
    """Example: Interactive usage."""
    orchestrator = OrchestratorAgent()

    # Register agents
    req_agent = RequirementsAgent()
    orchestrator.register_agent(req_agent)

    # Process natural language messages
    messages = [
        "implement story 12345",
        "split feature 456 into 5 stories",
        "create release for components backend, frontend from main",
    ]

    for message in messages:
        print(f"\nUser: {message}")
        response = await orchestrator.handle_message(message)
        print(f"Agent: {response}")

    await orchestrator.cleanup()


if __name__ == "__main__":
    # Run an example
    asyncio.run(example_implement_story())
