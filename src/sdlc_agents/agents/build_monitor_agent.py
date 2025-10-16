"""Build Monitor Agent - watches CI/CD pipelines and handles failures."""

import asyncio
from typing import Any, Optional

from sdlc_agents.agents.base import Agent, AgentCapability
from sdlc_agents.config import settings
from sdlc_agents.integrations import ADOClient
from sdlc_agents.logging_config import logger


class BuildMonitorAgent(Agent):
    """Agent that monitors builds and handles failures."""

    def __init__(self):
        """Initialize the build monitor agent."""
        system_prompt = """You are the Build Monitor Agent for an automated SDLC system.

Your responsibilities:
1. Monitor pull request builds in Azure DevOps
2. Detect intermittent failures vs. real issues
3. Automatically retry builds for intermittent failures
4. Analyze build failures and identify root causes
5. Request code agents to fix issues
6. Track build success rates and patterns

When analyzing build failures:
- Distinguish between compilation errors, test failures, and infrastructure issues
- Identify if failure is intermittent (network, timing) or persistent
- Extract relevant error messages and stack traces
- Suggest specific fixes to code agents
- Track failure patterns to predict issues

Be proactive in keeping builds green and identifying problematic patterns."""

        super().__init__(
            agent_id="build_monitor",
            name="Build Monitor Agent",
            capabilities=[
                AgentCapability.BUILD_MONITORING,
                AgentCapability.ADO_INTEGRATION,
            ],
            system_prompt=system_prompt,
        )

        self.ado_client = ADOClient()
        self.monitored_builds: dict[int, dict[str, Any]] = {}

    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Process a build monitoring task.

        Args:
            task: Task details

        Returns:
            Task result
        """
        task_type = task.get("type")

        if task_type == "monitor_pr_build":
            return await self._monitor_pr_build(task)
        elif task_type == "analyze_build_failure":
            return await self._analyze_build_failure(task)
        elif task_type == "retry_build":
            return await self._retry_build(task)
        else:
            return {"success": False, "error": f"Unknown task type: {task_type}"}

    async def _monitor_pr_build(self, task: dict[str, Any]) -> dict[str, Any]:
        """Monitor a pull request build."""
        pr_id = task.get("pr_id")
        build_definition = task.get("build_definition", "CI")

        await self.observe(f"Monitoring build for PR {pr_id}")

        # In a real implementation:
        # 1. Get PR details
        # 2. Find associated builds
        # 3. Watch build status
        # 4. Handle failures

        # Simulate monitoring
        build_id = task.get("build_id", 12345)

        # Track this build
        self.monitored_builds[build_id] = {
            "pr_id": pr_id,
            "status": "inProgress",
            "retry_count": 0,
        }

        # Wait for completion (in real implementation, poll periodically)
        await asyncio.sleep(1)

        # Check build status
        build = self.ado_client.get_build(build_id)

        if not build:
            return {"success": False, "error": f"Build {build_id} not found"}

        if build["result"] == "failed":
            # Analyze the failure
            analysis = await self._analyze_build_failure({"build_id": build_id})

            if analysis.get("is_intermittent"):
                # Retry the build
                return await self._retry_build({"build_id": build_id})
            else:
                # Request code agent to fix
                return {
                    "success": False,
                    "build_id": build_id,
                    "analysis": analysis,
                    "action_needed": "code_fix",
                }

        return {
            "success": True,
            "build_id": build_id,
            "result": build["result"],
        }

    async def _analyze_build_failure(self, task: dict[str, Any]) -> dict[str, Any]:
        """Analyze a build failure."""
        build_id = task.get("build_id")

        build = self.ado_client.get_build(build_id)
        if not build:
            return {"success": False, "error": "Build not found"}

        await self.observe(f"Analyzing build failure for build {build_id}")

        # Get build logs (in real implementation)
        build_logs = task.get("build_logs", "Build logs would be fetched here")

        # Analyze with LLM
        analysis_prompt = f"""Analyze this build failure and respond with a JSON object:

**Build ID:** {build_id}
**Build Number:** {build['build_number']}
**Status:** {build['status']}
**Result:** {build['result']}

**Logs Preview:**
{build_logs[:1000]}

Analyze the failure and respond ONLY with a JSON object in this exact format:
{{
  "failure_type": "compilation_error|test_failure|infrastructure_issue|intermittent_failure",
  "is_intermittent": true|false,
  "confidence": 0.0-1.0,
  "root_cause": "Brief description of the underlying issue",
  "affected_components": ["component1", "component2"],
  "recommended_action": "retry|fix_code|infrastructure_fix",
  "fix_suggestions": ["Specific suggestion 1", "Specific suggestion 2"],
  "reasoning": "Brief explanation of your analysis"
}}

Be specific and actionable. Focus on:
- Compilation errors, test failures, and infrastructure issues
- Network timeouts, race conditions, and flaky tests indicate intermittent failures
- Provide concrete fix suggestions when recommending code fixes"""

        response = await self.think(analysis_prompt, temperature=0.3)

        # Parse JSON response
        import json
        import re

        # Extract JSON from response (handle markdown code blocks)
        content = response.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)

        if json_match:
            try:
                analysis_result = json.loads(json_match.group())
                is_intermittent = analysis_result.get("is_intermittent", False)
                failure_type = analysis_result.get("failure_type", "unknown")
            except json.JSONDecodeError:
                # Fallback to keyword matching if JSON parsing fails
                logger.warning(f"Failed to parse JSON from LLM response for build {build_id}")
                is_intermittent = "intermittent" in content.lower() or "flaky" in content.lower()
                failure_type = "unknown"
                analysis_result = {"raw_response": content}
        else:
            # Fallback to keyword matching
            logger.warning(f"No JSON found in LLM response for build {build_id}")
            is_intermittent = "intermittent" in content.lower() or "flaky" in content.lower()
            failure_type = "unknown"
            analysis_result = {"raw_response": content}

        result = {
            "success": True,
            "build_id": build_id,
            "analysis": analysis_result,
            "is_intermittent": is_intermittent,
            "failure_type": failure_type,
        }

        await self.record_result(
            f"Analyzed build {build_id}: type={failure_type}, intermittent={is_intermittent}"
        )

        return result

    async def _retry_build(self, task: dict[str, Any]) -> dict[str, Any]:
        """Retry a build."""
        build_id = task.get("build_id")

        if build_id not in self.monitored_builds:
            return {"success": False, "error": "Build not being monitored"}

        build_info = self.monitored_builds[build_id]

        if build_info["retry_count"] >= settings.max_retries:
            await self.decide(f"Max retries reached for build {build_id}, escalating")
            return {
                "success": False,
                "error": "Max retries exceeded",
                "action_needed": "manual_intervention",
            }

        # Get original build
        original_build = self.ado_client.get_build(build_id)
        if not original_build:
            return {"success": False, "error": "Original build not found"}

        # Queue new build
        new_build = self.ado_client.queue_build(
            definition_name=original_build["definition"],
            branch=original_build["source_branch"].replace("refs/heads/", ""),
        )

        if not new_build:
            return {"success": False, "error": "Failed to queue retry build"}

        # Update tracking
        build_info["retry_count"] += 1
        self.monitored_builds[new_build["id"]] = build_info

        await self.record_action(
            f"Retried build {build_id} as {new_build['id']} (attempt {build_info['retry_count']})"
        )

        return {
            "success": True,
            "original_build_id": build_id,
            "new_build_id": new_build["id"],
            "retry_count": build_info["retry_count"],
        }

    def get_build_statistics(self) -> dict[str, Any]:
        """Get statistics about monitored builds."""
        total = len(self.monitored_builds)
        retries = sum(1 for b in self.monitored_builds.values() if b["retry_count"] > 0)

        return {
            "total_monitored": total,
            "builds_retried": retries,
            "active_monitors": sum(
                1 for b in self.monitored_builds.values() if b["status"] == "inProgress"
            ),
        }
