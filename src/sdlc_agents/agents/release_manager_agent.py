"""Release Manager Agent - handles release creation and management."""

from typing import Any, Optional

from sdlc_agents.agents.base import Agent, AgentCapability
from sdlc_agents.integrations import ADOClient
from sdlc_agents.logging_config import logger


class ReleaseManagerAgent(Agent):
    """Agent responsible for creating and managing releases."""

    def __init__(self):
        """Initialize the release manager agent."""
        system_prompt = """You are the Release Manager Agent for an automated SDLC system.

Your responsibilities:
1. Create release work items in Azure DevOps
2. Create release candidate branches from integration branches
3. Ensure all builds are green before release
4. Coordinate multi-component releases
5. Generate release notes
6. Track release readiness

When creating a release:
- Verify all components have passing builds
- Create release branches with proper naming
- Generate comprehensive release notes
- Link all included work items
- Ensure dependencies are compatible
- Document breaking changes

Be thorough, cautious, and ensure release quality."""

        super().__init__(
            agent_id="release_manager",
            name="Release Manager Agent",
            capabilities=[
                AgentCapability.RELEASE_MANAGEMENT,
                AgentCapability.ADO_INTEGRATION,
                AgentCapability.GIT_OPERATIONS,
            ],
            system_prompt=system_prompt,
        )

        self.ado_client = ADOClient()

    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Process a release management task.

        Args:
            task: Task details

        Returns:
            Task result
        """
        task_type = task.get("type")

        if task_type == "create_release":
            return await self._create_release(task)
        elif task_type == "verify_release_readiness":
            return await self._verify_release_readiness(task)
        elif task_type == "generate_release_notes":
            return await self._generate_release_notes(task)
        else:
            return {"success": False, "error": f"Unknown task type: {task_type}"}

    async def _create_release(self, task: dict[str, Any]) -> dict[str, Any]:
        """Create a new release."""
        components = task.get("components", [])
        source_branch = task.get("source_branch", "main")
        release_name = task.get("release_name")

        if not release_name:
            # Generate release name
            from datetime import datetime
            release_name = f"Release-{datetime.now().strftime('%Y.%m.%d')}"

        await self.observe(f"Creating release: {release_name}")

        # Verify readiness
        readiness = await self._verify_release_readiness({
            "components": components,
            "source_branch": source_branch,
        })

        if not readiness.get("ready"):
            return {
                "success": False,
                "error": "Components not ready for release",
                "readiness": readiness,
            }

        # Create release work item
        release_notes = await self._generate_release_notes({
            "components": components,
            "source_branch": source_branch,
        })

        release_work_item = self.ado_client.create_work_item(
            work_item_type="Release",
            title=release_name,
            description=release_notes.get("notes", ""),
            **{
                "Microsoft.VSTS.Common.Priority": 1,
                "System.Tags": "automated-release",
            },
        )

        if not release_work_item:
            return {"success": False, "error": "Failed to create release work item"}

        # Create release branches for each component
        release_branches = []
        for component in components:
            branch_name = f"release/{release_name}/{component}"
            # In real implementation, create branch via Git
            release_branches.append({
                "component": component,
                "branch": branch_name,
            })

        await self.record_result(
            f"Created release {release_name} with {len(components)} components"
        )

        return {
            "success": True,
            "release_name": release_name,
            "work_item": release_work_item,
            "branches": release_branches,
            "release_notes": release_notes,
        }

    async def _verify_release_readiness(self, task: dict[str, Any]) -> dict[str, Any]:
        """Verify that components are ready for release."""
        components = task.get("components", [])
        source_branch = task.get("source_branch", "main")

        await self.observe(f"Verifying release readiness for {len(components)} components")

        readiness_checks = []

        for component in components:
            # In real implementation:
            # 1. Check if builds are passing
            # 2. Check if all PRs are merged
            # 3. Check if tests are passing
            # 4. Check for open critical bugs

            # Simulate checks
            component_ready = True
            issues = []

            # Check builds (simulated)
            build_status = "succeeded"  # Would call ADO API
            if build_status != "succeeded":
                component_ready = False
                issues.append(f"Build not passing: {build_status}")

            readiness_checks.append({
                "component": component,
                "ready": component_ready,
                "issues": issues,
            })

        all_ready = all(check["ready"] for check in readiness_checks)

        result = {
            "ready": all_ready,
            "checks": readiness_checks,
        }

        if all_ready:
            await self.decide("All components ready for release")
        else:
            await self.decide("Release not ready, issues found")

        return result

    async def _generate_release_notes(self, task: dict[str, Any]) -> dict[str, Any]:
        """Generate release notes."""
        components = task.get("components", [])
        source_branch = task.get("source_branch", "main")

        await self.observe(f"Generating release notes for {len(components)} components")

        # In real implementation:
        # 1. Get all merged PRs since last release
        # 2. Get all closed work items
        # 3. Categorize changes (features, bugs, breaking changes)

        # Use LLM to generate notes
        from datetime import datetime
        release_date = datetime.now().strftime('%Y-%m-%d')

        notes_prompt = f"""Generate release notes in the following EXACT markdown format:

# Release Notes

**Release Date**: {release_date}
**Components**: {', '.join(components)}
**Source Branch**: {source_branch}

## 🎉 New Features
- [Feature name](work-item-link): Brief description of what was added
- [Another feature](work-item-link): Brief description

## 🐛 Bug Fixes
- [Bug name](work-item-link): Brief description of what was fixed
- [Another bug](work-item-link): Brief description

## 🔧 Improvements
- [Improvement](work-item-link): Brief description of enhancement
- [Another improvement](work-item-link): Brief description

## ⚠️ Breaking Changes
- [Breaking change](work-item-link): Description and migration guide
- If no breaking changes, write "None"

## 📝 Known Issues
- [Issue description]: Workaround if available
- If no known issues, write "None"

## 📦 Deployment Notes
- Any special deployment steps or configuration changes required
- If none, write "Standard deployment process"

**IMPORTANT**:
- Use the exact format above with proper markdown headings and emoji
- Each item should be a bullet point starting with a dash (-)
- Include work item links in square brackets when applicable
- Keep descriptions brief (1-2 sentences maximum)
- If a section has no items, write "None" instead of omitting the section

In a real scenario, we would provide:
- List of merged PRs since last release
- Closed work items with details
- Full commit history
- Test coverage changes

For this demonstration, generate sample items that follow the format above."""

        response = await self.think(notes_prompt)

        await self.record_result("Generated release notes")

        return {
            "success": True,
            "notes": response.content,
        }
