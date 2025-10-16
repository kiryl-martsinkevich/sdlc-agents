"""Orchestrator agent - coordinates all other agents."""

import asyncio
from typing import Any, Optional

from sdlc_agents.agents.base import Agent, AgentCapability
from sdlc_agents.integrations import ADOClient
from sdlc_agents.logging_config import logger


class OrchestratorAgent(Agent):
    """Main orchestrator that coordinates all specialized agents."""

    def __init__(self):
        """Initialize the orchestrator agent."""
        system_prompt = """You are the Orchestrator Agent for an automated SDLC system.

Your responsibilities:
1. Analyze incoming tasks and work items
2. Determine which components/repositories need changes
3. Delegate work to specialized agents (Requirements, Code, Build Monitor, Release)
4. Coordinate multi-repository changes
5. Track progress and ensure task completion
6. Handle errors and retry failed operations

When given a task:
- Break it down into subtasks
- Identify affected repositories
- Create an execution plan
- Assign work to the appropriate agents
- Monitor progress and handle issues

Be decisive, practical, and focused on delivering working software."""

        super().__init__(
            agent_id="orchestrator",
            name="Orchestrator Agent",
            capabilities=[AgentCapability.ORCHESTRATION, AgentCapability.ADO_INTEGRATION],
            system_prompt=system_prompt,
        )

        self.ado_client = ADOClient()
        self.active_agents: dict[str, Agent] = {}

    def register_agent(self, agent: Agent) -> None:
        """Register a specialized agent."""
        self.active_agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.name}")

    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Process a high-level task by coordinating specialized agents.

        Args:
            task: Task containing 'type' and relevant parameters

        Returns:
            Task result
        """
        task_type = task.get("type")

        await self.observe(f"Received task: {task_type}")
        await self.decide(f"Processing {task_type} task")

        try:
            if task_type == "implement_story":
                return await self._implement_story(task)
            elif task_type == "split_feature":
                return await self._split_feature(task)
            elif task_type == "create_release":
                return await self._create_release(task)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}
        except Exception as e:
            logger.error(f"Orchestrator task failed: {e}")
            await self.record_result(f"Task failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _implement_story(self, task: dict[str, Any]) -> dict[str, Any]:
        """Implement a story from ADO."""
        story_id = task.get("story_id")

        # Get story details from ADO
        work_item = self.ado_client.get_work_item(story_id)
        if not work_item:
            return {"success": False, "error": f"Story {story_id} not found"}

        # Ask LLM to analyze requirements and determine affected components
        analysis_prompt = f"""Analyze this story and determine implementation approach:

Title: {work_item['title']}
Description: {work_item['description']}
Acceptance Criteria: {work_item.get('acceptance_criteria', 'Not provided')}

Determine:
1. Which repositories/components need changes
2. Complexity estimate
3. Key implementation steps
4. Potential risks

Provide a structured implementation plan."""

        response = await self.think(analysis_prompt)
        await self.record_action(f"Analyzed story {story_id}: {response.content[:200]}")

        # Get requirements agent to create detailed tasks
        if "requirements" in self.active_agents:
            req_agent = self.active_agents["requirements"]
            req_result = await req_agent.process_task({
                "type": "analyze_requirements",
                "work_item": work_item,
            })

            # Delegate to code agents for each affected repository
            code_results = []
            for repo in req_result.get("affected_repos", []):
                agent_id = f"code_repo_{repo}"
                if agent_id in self.active_agents:
                    code_agent = self.active_agents[agent_id]
                    result = await code_agent.process_task({
                        "type": "implement",
                        "work_item": work_item,
                        "requirements": req_result.get("requirements"),
                    })
                    code_results.append(result)

            return {
                "success": True,
                "story_id": story_id,
                "analysis": response.content,
                "requirements": req_result,
                "code_results": code_results,
            }

        return {
            "success": True,
            "story_id": story_id,
            "analysis": response.content,
        }

    async def _split_feature(self, task: dict[str, Any]) -> dict[str, Any]:
        """Split a feature into stories."""
        feature_id = task.get("feature_id")
        story_count = task.get("story_count", 3)

        # Get feature details
        feature = self.ado_client.get_work_item(feature_id)
        if not feature:
            return {"success": False, "error": f"Feature {feature_id} not found"}

        # Ask LLM to suggest how to split the feature
        split_prompt = f"""Analyze this feature and suggest how to split it into {story_count} user stories:

Title: {feature['title']}
Description: {feature['description']}

Provide:
1. {story_count} user story titles
2. Description for each story
3. Suggested order of implementation
4. Dependencies between stories

Format as a structured list."""

        response = await self.think(split_prompt)

        # Create stories in ADO
        stories = self.ado_client.split_feature_into_stories(feature_id, story_count)

        # Update story descriptions based on LLM suggestions
        # (In a real implementation, parse the LLM response and update each story)

        return {
            "success": True,
            "feature_id": feature_id,
            "stories": stories,
            "suggestions": response.content,
        }

    async def _create_release(self, task: dict[str, Any]) -> dict[str, Any]:
        """Create a release for specified components."""
        components = task.get("components", [])
        source_branch = task.get("source_branch", "main")

        # Delegate to release manager
        if "release_manager" in self.active_agents:
            release_agent = self.active_agents["release_manager"]
            result = await release_agent.process_task({
                "type": "create_release",
                "components": components,
                "source_branch": source_branch,
            })
            return result

        return {
            "success": False,
            "error": "Release manager agent not available",
        }

    async def handle_message(self, message: str) -> str:
        """
        Handle a natural language message from the user.

        Args:
            message: User message

        Returns:
            Response string
        """
        # Parse user intent
        parse_prompt = f"""Parse this user request and extract task details:

Message: "{message}"

Identify:
1. Task type (implement_story, split_feature, create_release, or other)
2. Work item IDs if mentioned
3. Component names if mentioned
4. Any specific parameters

Respond with a structured JSON-like format."""

        response = await self.think(parse_prompt, temperature=0.3)

        # In a real implementation, parse the response and execute the task
        # For now, return the analysis

        return f"Understood your request:\n{response.content}\n\nI will process this task now."
