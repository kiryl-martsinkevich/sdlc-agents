"""Requirements Agent - analyzes and interprets requirements from ADO."""

from typing import Any

from sdlc_agents.agents.base import Agent, AgentCapability
from sdlc_agents.integrations import ADOClient
from sdlc_agents.logging_config import logger


class RequirementsAgent(Agent):
    """Agent specialized in analyzing and interpreting requirements."""

    def __init__(self):
        """Initialize the requirements agent."""
        system_prompt = """You are the Requirements Agent for an automated SDLC system.

Your responsibilities:
1. Analyze work items (stories, features, bugs) from Azure DevOps
2. Extract technical requirements and acceptance criteria
3. Identify affected system components and repositories
4. Break down complex requirements into implementation tasks
5. Detect ambiguities and ask clarifying questions
6. Ensure requirements are testable and complete

When analyzing requirements:
- Focus on technical implementation details
- Identify data models, APIs, and UI changes needed
- Consider non-functional requirements (performance, security)
- Flag missing information or ambiguities
- Suggest test scenarios

Be thorough, ask questions, and ensure nothing is overlooked."""

        super().__init__(
            agent_id="requirements",
            name="Requirements Agent",
            capabilities=[
                AgentCapability.REQUIREMENTS_ANALYSIS,
                AgentCapability.ADO_INTEGRATION,
            ],
            system_prompt=system_prompt,
        )

        self.ado_client = ADOClient()

    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Process a requirements analysis task.

        Args:
            task: Task details

        Returns:
            Analysis result
        """
        task_type = task.get("type")

        if task_type == "analyze_requirements":
            return await self._analyze_requirements(task)
        elif task_type == "clarify_requirements":
            return await self._clarify_requirements(task)
        else:
            return {"success": False, "error": f"Unknown task type: {task_type}"}

    async def _analyze_requirements(self, task: dict[str, Any]) -> dict[str, Any]:
        """Analyze requirements from a work item."""
        work_item = task.get("work_item")

        await self.observe(f"Analyzing work item {work_item['id']}: {work_item['title']}")

        # Build detailed analysis prompt
        analysis_prompt = f"""Analyze these requirements in detail:

**Type:** {work_item['type']}
**Title:** {work_item['title']}
**Description:**
{work_item['description']}

**Acceptance Criteria:**
{work_item.get('acceptance_criteria', 'Not specified')}

**Tags:** {work_item.get('tags', 'None')}

Provide:
1. **Technical Requirements**: Specific implementation details needed
2. **Affected Components**: Which repositories/modules need changes
3. **Data Model Changes**: New or modified entities
4. **API Changes**: New or modified endpoints
5. **UI Changes**: Frontend modifications needed
6. **Test Scenarios**: How to verify the implementation
7. **Ambiguities**: Unclear points that need clarification
8. **Assumptions Made**: Explicitly list ALL assumptions you're making due to missing information
9. **Missing Information**: What critical details are not provided that should be clarified
10. **Risks**: Potential implementation challenges

**Critical Instructions:**
- For ANY missing information, explicitly list what assumptions you're making
- Do NOT make silent assumptions - document every assumption clearly
- If acceptance criteria are incomplete, specify exactly what's missing
- Highlight any edge cases not covered by the requirements

Be specific and actionable. When information is incomplete, explicitly state what clarifications are needed before implementation can proceed safely."""

        response = await self.think(analysis_prompt)

        # Parse the response to extract structured data
        # In a real implementation, use structured output or parse carefully
        requirements = {
            "work_item_id": work_item["id"],
            "title": work_item["title"],
            "analysis": response.content,
            "affected_repos": self._extract_affected_repos(response.content),
            "complexity": self._estimate_complexity(response.content),
        }

        await self.record_result(f"Analyzed requirements for {work_item['id']}")

        # Store in work item tracking
        self.memory.store_work_item(
            work_item_id=str(work_item["id"]),
            item_type=work_item["type"],
            title=work_item["title"],
            description=work_item["description"],
            state="Analyzed",
            metadata=requirements,
        )

        return {
            "success": True,
            "requirements": requirements,
        }

    async def _clarify_requirements(self, task: dict[str, Any]) -> dict[str, Any]:
        """Ask clarifying questions about requirements."""
        work_item = task.get("work_item")
        ambiguities = task.get("ambiguities", [])

        clarification_prompt = f"""Based on this work item, generate clarifying questions:

**Title:** {work_item['title']}
**Description:** {work_item['description']}

**Identified Ambiguities:**
{chr(10).join(f'- {a}' for a in ambiguities)}

Generate specific questions that would help resolve these ambiguities.
Focus on technical details needed for implementation."""

        response = await self.think(clarification_prompt)

        return {
            "success": True,
            "questions": response.content,
        }

    def _extract_affected_repos(self, analysis: str) -> list[str]:
        """
        Extract affected repositories from analysis text.

        Args:
            analysis: Analysis text

        Returns:
            List of repository names
        """
        # In a real implementation, use NER or structured extraction
        # For now, return placeholder
        repos = []

        # Simple keyword matching (improve this!)
        keywords = ["backend", "frontend", "api", "web", "mobile", "shared"]
        for keyword in keywords:
            if keyword.lower() in analysis.lower():
                repos.append(keyword)

        return repos if repos else ["main"]

    def _estimate_complexity(self, analysis: str) -> str:
        """
        Estimate implementation complexity.

        Args:
            analysis: Analysis text

        Returns:
            Complexity level (Low, Medium, High, Very High)
        """
        # Simple heuristic based on length and keywords
        complexity_indicators = [
            "complex",
            "difficult",
            "multiple",
            "integration",
            "migration",
            "refactor",
        ]

        indicator_count = sum(
            1 for indicator in complexity_indicators if indicator in analysis.lower()
        )

        if indicator_count >= 3:
            return "Very High"
        elif indicator_count >= 2:
            return "High"
        elif indicator_count >= 1:
            return "Medium"
        else:
            return "Low"
