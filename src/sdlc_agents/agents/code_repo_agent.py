"""Code Repository Agent - manages code changes for a specific repository."""

import asyncio
import subprocess
from pathlib import Path
from typing import Any, Optional

from git import Repo

from sdlc_agents.agents.base import Agent, AgentCapability
from sdlc_agents.config import settings
from sdlc_agents.integrations import ADOClient
from sdlc_agents.logging_config import logger


class CodeRepositoryAgent(Agent):
    """Agent responsible for a specific code repository."""

    def __init__(self, repo_name: str, repo_url: str, repo_path: Optional[Path] = None):
        """
        Initialize code repository agent.

        Args:
            repo_name: Repository name
            repo_url: Git repository URL
            repo_path: Local path to repository
        """
        system_prompt = f"""You are a Code Repository Agent for the '{repo_name}' repository.

Your responsibilities:
1. Understand the repository structure and codebase
2. Generate code changes based on requirements
3. Run Maven builds and tests locally
4. Commit changes with meaningful messages
5. Create pull requests in Azure DevOps
6. Fix build and test failures

Technology stack:
- Language: Java
- Build tool: Maven
- Version control: Git

When implementing changes:
- Follow existing code style and patterns
- Write unit tests for new functionality
- Ensure all tests pass before committing
- Use meaningful commit messages
- Create clear PR descriptions

You are an expert Java developer with strong Maven and testing skills."""

        super().__init__(
            agent_id=f"code_repo_{repo_name}",
            name=f"Code Agent ({repo_name})",
            capabilities=[
                AgentCapability.CODE_GENERATION,
                AgentCapability.CODE_REVIEW,
                AgentCapability.TESTING,
                AgentCapability.GIT_OPERATIONS,
            ],
            system_prompt=system_prompt,
        )

        self.repo_name = repo_name
        self.repo_url = repo_url
        self.repo_path = repo_path or settings.repos_dir / repo_name
        self.repo: Optional[Repo] = None
        self.ado_client = ADOClient()

    async def initialize_repo(self) -> bool:
        """
        Initialize or open the repository.

        If repo_path was provided during initialization (from local_path config),
        it will use that existing checkout. Otherwise, it will clone to the default location.
        """
        try:
            if self.repo_path.exists():
                # Repository exists (either provided local_path or previously cloned)
                self.repo = Repo(self.repo_path)
                await self.observe(f"Opened existing repository at {self.repo_path}")

                # Only pull if this wasn't explicitly configured as a local path
                # (to avoid interfering with developer's local work)
                # Check if repo_path was explicitly set (not default)
                is_explicit_local = self.repo_path != (settings.repos_dir / self.repo_name)

                if not is_explicit_local:
                    # This is a managed clone, safe to pull
                    origin = self.repo.remotes.origin
                    origin.pull()
                    logger.info(f"Pulled latest changes for {self.repo_name}")
                else:
                    # This is a local checkout configured in repositories.yaml
                    logger.info(
                        f"Using local repository at {self.repo_path} "
                        "(not pulling to preserve local changes)"
                    )
            else:
                # Clone repository to default location
                await self.observe(f"Cloning repository from {self.repo_url}")
                self.repo = Repo.clone_from(self.repo_url, self.repo_path)
                logger.info(f"Cloned repository to {self.repo_path}")

            # Configure git
            with self.repo.config_writer() as config:
                config.set_value("user", "name", settings.git_user_name)
                config.set_value("user", "email", settings.git_user_email)

            return True
        except Exception as e:
            logger.error(f"Failed to initialize repository {self.repo_name}: {e}")
            return False

    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Process a code implementation task.

        Args:
            task: Task details

        Returns:
            Task result
        """
        task_type = task.get("type")

        if not self.repo:
            if not await self.initialize_repo():
                return {"success": False, "error": "Failed to initialize repository"}

        if task_type == "implement":
            return await self._implement_changes(task)
        elif task_type == "fix_build":
            return await self._fix_build(task)
        else:
            return {"success": False, "error": f"Unknown task type: {task_type}"}

    async def _implement_changes(self, task: dict[str, Any]) -> dict[str, Any]:
        """Implement code changes for a work item."""
        work_item = task.get("work_item")
        requirements = task.get("requirements", {})

        await self.observe(f"Implementing changes for work item {work_item['id']}")

        # Analyze codebase structure
        structure = await self._analyze_codebase()

        # Generate implementation plan
        impl_prompt = f"""Create an implementation plan for this work item:

**Work Item:** {work_item['title']}
**Description:** {work_item['description']}
**Requirements:** {requirements.get('analysis', 'See description')}

**Repository Structure:**
{structure}

Provide:
1. Files to create or modify
2. Specific code changes needed
3. Test cases to add
4. Maven dependencies if needed

**Important Guidelines:**
- If you identify conflicting requirements, explicitly flag them and suggest resolution approaches
- For any missing or ambiguous information, list the assumptions you're making
- If requirements are incomplete, specify what clarifications are needed before implementation
- Highlight any potential risks or edge cases that aren't addressed in requirements

Be specific with file paths and code snippets. If you encounter conflicts or ambiguities,
do NOT proceed with assumptions - clearly state the issues and ask for clarification."""

        response = await self.think(impl_prompt)

        # Create feature branch
        branch_name = f"feature/{work_item['id']}-{work_item['title'][:30].replace(' ', '-').lower()}"
        await self._create_branch(branch_name)

        # In a real implementation:
        # 1. Parse the LLM response to extract file changes
        # 2. Generate actual code using LLM
        # 3. Write files
        # 4. Run build and tests
        # 5. Commit if successful
        # 6. Create PR

        # For now, simulate the process
        await self.record_action(f"Created branch {branch_name}")
        await self.record_action(f"Implementation plan: {response.content[:200]}")

        # Run Maven build
        build_result = await self._run_maven_build()

        if build_result["success"]:
            # Commit changes
            await self._commit_changes(
                f"Implement {work_item['title']}\n\nWork item: {work_item['id']}"
            )

            # Create PR
            pr_result = await self._create_pull_request(
                branch_name=branch_name,
                target_branch="main",
                title=f"[{work_item['id']}] {work_item['title']}",
                description=f"Implements work item {work_item['id']}\n\n{response.content[:500]}",
            )

            return {
                "success": True,
                "branch": branch_name,
                "build": build_result,
                "pull_request": pr_result,
            }
        else:
            return {
                "success": False,
                "branch": branch_name,
                "build": build_result,
                "error": "Build failed",
            }

    async def _fix_build(self, task: dict[str, Any]) -> dict[str, Any]:
        """Fix build failures."""
        build_errors = task.get("build_errors", [])

        await self.observe(f"Fixing build errors: {len(build_errors)} errors")

        fix_prompt = f"""Analyze these build errors and suggest fixes:

**Errors:**
{chr(10).join(build_errors[:10])}

**Repository:** {self.repo_name}

Provide:
1. Root cause of each error
2. Specific code changes to fix
3. Files to modify

Focus on compilation errors, test failures, and dependency issues."""

        response = await self.think(fix_prompt)

        await self.record_action(f"Build fix plan: {response.content[:200]}")

        # In a real implementation, apply the fixes and rebuild
        build_result = await self._run_maven_build()

        return {
            "success": build_result["success"],
            "fix_plan": response.content,
            "build": build_result,
        }

    async def _analyze_codebase(self) -> str:
        """Analyze repository structure."""
        if not self.repo_path.exists():
            return "Repository not initialized"

        # Find key files
        structure = []
        structure.append(f"Repository: {self.repo_name}")
        structure.append(f"Path: {self.repo_path}")

        # Find pom.xml
        pom_files = list(self.repo_path.rglob("pom.xml"))
        if pom_files:
            structure.append(f"\nMaven projects: {len(pom_files)}")

        # Find source directories
        src_dirs = list(self.repo_path.rglob("src/main/java"))
        if src_dirs:
            structure.append(f"Source directories: {len(src_dirs)}")

        # Find test directories
        test_dirs = list(self.repo_path.rglob("src/test/java"))
        if test_dirs:
            structure.append(f"Test directories: {len(test_dirs)}")

        return "\n".join(structure)

    async def _create_branch(self, branch_name: str) -> None:
        """Create a new Git branch."""
        if not self.repo:
            raise RuntimeError("Repository not initialized")

        # Ensure we're on main and up to date
        main_branch = self.repo.heads.main
        main_branch.checkout()
        self.repo.remotes.origin.pull()

        # Create new branch
        new_branch = self.repo.create_head(branch_name)
        new_branch.checkout()

        logger.info(f"Created and checked out branch: {branch_name}")

    async def _run_maven_build(self) -> dict[str, Any]:
        """Run Maven build and tests."""
        await self.observe("Running Maven build with tests")

        try:
            # Run mvn clean test
            process = await asyncio.create_subprocess_exec(
                "mvn",
                "clean",
                "test",
                cwd=self.repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=settings.build_timeout
            )

            success = process.returncode == 0

            result = {
                "success": success,
                "exit_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }

            if success:
                await self.record_result("Maven build successful")
            else:
                await self.record_result(f"Maven build failed: exit code {process.returncode}")

            return result
        except asyncio.TimeoutError:
            logger.error("Maven build timed out")
            return {
                "success": False,
                "error": "Build timed out",
            }
        except Exception as e:
            logger.error(f"Maven build failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _commit_changes(self, message: str) -> None:
        """Commit all changes."""
        if not self.repo:
            raise RuntimeError("Repository not initialized")

        # Add all changes
        self.repo.git.add(A=True)

        # Commit
        self.repo.index.commit(message)

        logger.info(f"Committed changes: {message[:50]}")
        await self.record_action(f"Committed: {message}")

    async def _create_pull_request(
        self,
        branch_name: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> Optional[dict[str, Any]]:
        """Create a pull request in ADO."""
        if not self.repo:
            return None

        # Push branch to remote
        origin = self.repo.remotes.origin
        origin.push(branch_name)

        logger.info(f"Pushed branch {branch_name} to remote")

        # Create PR using ADO client
        # Note: Need repository ID from ADO
        # In a real implementation, map repo_name to ADO repository ID

        pr = self.ado_client.create_pull_request(
            repository_id=self.repo_name,  # Should be actual ADO repo ID
            source_branch=branch_name,
            target_branch=target_branch,
            title=title,
            description=description,
        )

        if pr:
            await self.record_result(f"Created PR: {pr['id']}")

        return pr
