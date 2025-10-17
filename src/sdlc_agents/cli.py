"""Command-line interface for SDLC agents."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from sdlc_agents.agents.build_monitor_agent import BuildMonitorAgent
from sdlc_agents.agents.code_repo_agent import CodeRepositoryAgent
from sdlc_agents.agents.orchestrator import OrchestratorAgent
from sdlc_agents.agents.release_manager_agent import ReleaseManagerAgent
from sdlc_agents.agents.requirements_agent import RequirementsAgent
from sdlc_agents.config import settings
from sdlc_agents.logging_config import logger
from sdlc_agents.repository_config import RepositoryConfigManager, repo_config_manager

console = Console()


class SDLCAgentSystem:
    """Main system coordinating all agents."""

    def __init__(self):
        """Initialize the agent system."""
        self.orchestrator: Optional[OrchestratorAgent] = None
        self.requirements_agent: Optional[RequirementsAgent] = None
        self.build_monitor: Optional[BuildMonitorAgent] = None
        self.release_manager: Optional[ReleaseManagerAgent] = None
        self.code_agents: dict[str, CodeRepositoryAgent] = {}

    async def initialize(self, repos: Optional[list[dict[str, str]]] = None) -> None:
        """
        Initialize all agents.

        Args:
            repos: Optional list of repositories with 'name' and 'url'.
                   If None, loads from repositories.yaml
        """
        console.print("[bold blue]Initializing SDLC Agent System...[/bold blue]")

        # Create orchestrator
        self.orchestrator = OrchestratorAgent()

        # Create specialized agents
        self.requirements_agent = RequirementsAgent()
        self.build_monitor = BuildMonitorAgent()
        self.release_manager = ReleaseManagerAgent()

        # Register with orchestrator
        self.orchestrator.register_agent(self.requirements_agent)
        self.orchestrator.register_agent(self.build_monitor)
        self.orchestrator.register_agent(self.release_manager)

        # Load repositories from config or use provided list
        repo_list = repos if repos is not None else self._load_repos_from_config()

        # Create code agents for each repository
        for repo in repo_list:
            # Extract local_path if provided
            local_path = None
            if "local_path" in repo and repo["local_path"]:
                local_path = Path(repo["local_path"]).expanduser()

            code_agent = CodeRepositoryAgent(
                repo_name=repo["name"],
                repo_url=repo["url"],
                repo_path=local_path,
            )
            await code_agent.initialize_repo()
            self.code_agents[repo["name"]] = code_agent
            self.orchestrator.register_agent(code_agent)

        console.print("[bold green]System initialized![/bold green]")
        console.print(f"Active agents: {len(self.orchestrator.active_agents)}")
        console.print(f"Repositories: {len(self.code_agents)}")

    def _load_repos_from_config(self) -> list[dict[str, str]]:
        """Load repositories from repositories.yaml file."""
        try:
            config = repo_config_manager.load()
            enabled_repos = repo_config_manager.get_enabled_repositories()

            if not enabled_repos:
                console.print(
                    "[yellow]No repositories configured. "
                    "Add repositories to repositories.yaml or use -r flag[/yellow]"
                )
                return []

            repo_list = []
            for repo in enabled_repos:
                repo_dict = {"name": repo.name, "url": repo.url}
                if repo.local_path:
                    repo_dict["local_path"] = repo.local_path
                repo_list.append(repo_dict)

            console.print(f"[green]Loaded {len(repo_list)} repositories from config[/green]")
            return repo_list
        except Exception as e:
            logger.error(f"Failed to load repository config: {e}")
            console.print(f"[yellow]Could not load repositories.yaml: {e}[/yellow]")
            return []

    async def process_message(self, message: str) -> str:
        """
        Process a user message.

        Args:
            message: User input

        Returns:
            System response
        """
        if not self.orchestrator:
            return "System not initialized"

        # Parse message intent
        message_lower = message.lower()

        # Handle specific command patterns
        if "implement story" in message_lower or "implement work item" in message_lower:
            # Extract work item ID
            import re
            match = re.search(r'\d+', message)
            if match:
                story_id = int(match.group())
                result = await self.orchestrator.process_task({
                    "type": "implement_story",
                    "story_id": story_id,
                })
                return self._format_result(result)

        elif "split feature" in message_lower:
            # Extract feature ID
            import re
            match = re.search(r'\d+', message)
            if match:
                feature_id = int(match.group())
                result = await self.orchestrator.process_task({
                    "type": "split_feature",
                    "feature_id": feature_id,
                })
                return self._format_result(result)

        elif "create release" in message_lower or "create a release" in message_lower:
            # Extract component names
            # Simple parsing - in real impl, use better NLP
            components = []
            for word in message.split():
                if word.endswith(','):
                    components.append(word[:-1])
                elif word not in ["create", "release", "for", "a", "and", "from", "components"]:
                    components.append(word)

            if components:
                result = await self.orchestrator.process_task({
                    "type": "create_release",
                    "components": components,
                })
                return self._format_result(result)

        # Otherwise, let orchestrator handle it
        response = await self.orchestrator.handle_message(message)
        return response

    def _format_result(self, result: dict) -> str:
        """Format a task result for display."""
        if result.get("success"):
            return f"✓ Task completed successfully\n\nDetails:\n{result}"
        else:
            return f"✗ Task failed: {result.get('error', 'Unknown error')}\n\nDetails:\n{result}"

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.orchestrator:
            await self.orchestrator.cleanup()

        for agent in self.code_agents.values():
            await agent.cleanup()


async def interactive_chat(system: SDLCAgentSystem) -> None:
    """Run interactive chat loop."""
    console.print(Panel.fit(
        "[bold]SDLC Multi-Agent System[/bold]\n\n"
        "Commands:\n"
        "  • implement story <id> - Implement a story from ADO\n"
        "  • split feature <id> - Split a feature into stories\n"
        "  • create release for components <a>, <b>, <c> from <branch>\n"
        "  • help - Show this help\n"
        "  • exit - Exit the system\n",
        title="Welcome",
        border_style="blue",
    ))

    while True:
        try:
            message = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if not message.strip():
                continue

            if message.lower() in ["exit", "quit", "q"]:
                console.print("[yellow]Goodbye![/yellow]")
                break

            if message.lower() in ["help", "h"]:
                console.print(Panel.fit(
                    "Available commands:\n"
                    "  • implement story <id>\n"
                    "  • split feature <id>\n"
                    "  • create release for components <a>, <b>, <c>\n"
                    "  • exit\n",
                    border_style="blue",
                ))
                continue

            # Process message
            console.print("\n[bold yellow]Agent:[/bold yellow] Processing...")

            response = await system.process_message(message)

            console.print(Panel(
                Markdown(response),
                title="Response",
                border_style="green",
            ))

        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            console.print(f"[red]Error: {e}[/red]")


@click.group()
def cli():
    """SDLC Multi-Agent System CLI."""
    pass


@cli.command()
@click.option(
    "--repos",
    "-r",
    multiple=True,
    help="Repository in format 'name:url' (overrides repositories.yaml)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to repositories.yaml file",
)
def chat(repos, config):
    """Start interactive chat with the agent system."""
    # Parse repository configurations from command line
    repo_configs = []
    for repo in repos:
        if ":" in repo:
            name, url = repo.split(":", 1)
            repo_configs.append({"name": name, "url": url})

    # Load from config file if no command-line repos provided
    if not repo_configs and config:
        repo_config_manager.config_path = Path(config)

    async def run():
        system = SDLCAgentSystem()
        try:
            # Pass None to load from config, or explicit list to override
            await system.initialize(repo_configs if repo_configs else None)
            await interactive_chat(system)
        finally:
            await system.cleanup()

    asyncio.run(run())


@cli.command()
@click.argument("story_id", type=int)
@click.option(
    "--repos",
    "-r",
    multiple=True,
    help="Repository in format 'name:url'",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to repositories.yaml file",
)
def implement(story_id, repos, config):
    """Implement a story from Azure DevOps."""
    repo_configs = []
    for repo in repos:
        if ":" in repo:
            name, url = repo.split(":", 1)
            repo_configs.append({"name": name, "url": url})

    if config:
        repo_config_manager.config_path = Path(config)

    async def run():
        system = SDLCAgentSystem()
        try:
            await system.initialize(repo_configs if repo_configs else None)

            console.print(f"[bold]Implementing story {story_id}...[/bold]")

            response = await system.process_message(f"implement story {story_id}")

            console.print(Panel(
                Markdown(response),
                title="Result",
                border_style="green",
            ))
        finally:
            await system.cleanup()

    asyncio.run(run())


@cli.command()
@click.argument("feature_id", type=int)
@click.option("--count", "-c", default=3, help="Number of stories to create")
def split(feature_id, count):
    """Split a feature into stories."""
    async def run():
        system = SDLCAgentSystem()
        try:
            await system.initialize([])

            console.print(f"[bold]Splitting feature {feature_id} into {count} stories...[/bold]")

            response = await system.process_message(
                f"split feature {feature_id} into {count} stories"
            )

            console.print(Panel(
                Markdown(response),
                title="Result",
                border_style="green",
            ))
        finally:
            await system.cleanup()

    asyncio.run(run())


@cli.command()
@click.argument("components", nargs=-1)
@click.option("--branch", "-b", default="main", help="Source branch")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to repositories.yaml file",
)
def release(components, branch, config):
    """Create a release for specified components."""
    if not components:
        console.print("[red]Error: Specify at least one component[/red]")
        return

    if config:
        repo_config_manager.config_path = Path(config)

    async def run():
        system = SDLCAgentSystem()
        try:
            await system.initialize([])

            components_str = ", ".join(components)
            console.print(f"[bold]Creating release for components: {components_str}[/bold]")

            response = await system.process_message(
                f"create release for components {components_str} from {branch}"
            )

            console.print(Panel(
                Markdown(response),
                title="Result",
                border_style="green",
            ))
        finally:
            await system.cleanup()

    asyncio.run(run())


@cli.command()
def info():
    """Show system configuration."""
    console.print(Panel.fit(
        f"[bold]SDLC Agent System Configuration[/bold]\n\n"
        f"LLM Provider: {settings.llm_provider.value}\n"
        f"Ollama URL: {settings.ollama_base_url}\n"
        f"Ollama Model: {settings.ollama_model}\n"
        f"OpenAI Model: {settings.openai_model}\n"
        f"ClickHouse: {settings.clickhouse_host}:{settings.clickhouse_port}\n"
        f"ADO Organization: {settings.ado_organization}\n"
        f"ADO Project: {settings.ado_project}\n"
        f"Workspace: {settings.workspace_dir}\n"
        f"Repos: {settings.repos_dir}\n",
        border_style="blue",
    ))


@cli.command(name="repos")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to repositories.yaml file",
)
def list_repos(config):
    """List configured repositories."""
    if config:
        repo_config_manager.config_path = Path(config)

    try:
        config_obj = repo_config_manager.load()

        if not config_obj.repositories:
            console.print("[yellow]No repositories configured[/yellow]")
            console.print("Create repositories.yaml from repositories.yaml.example")
            return

        # Create table
        table = Table(title="Configured Repositories")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Local Path", style="yellow")
        table.add_column("Build Definition")
        table.add_column("Description")

        for repo in config_obj.repositories:
            status = "✓ Enabled" if repo.enabled else "✗ Disabled"
            local_path_display = repo.local_path if repo.local_path else "-"
            table.add_row(
                repo.name,
                status,
                local_path_display,
                repo.build_definition or "-",
                repo.description or "-",
            )

        console.print(table)

        # Show component groups
        if config_obj.component_groups:
            console.print("\n[bold]Component Groups:[/bold]")
            for group, repos in config_obj.component_groups.items():
                console.print(f"  • {group}: {', '.join(repos)}")

    except Exception as e:
        console.print(f"[red]Error loading repositories: {e}[/red]")


@cli.command(name="repo-add")
@click.argument("name")
@click.argument("url")
@click.option("--ado-id", help="Azure DevOps repository ID")
@click.option("--build-def", help="Build definition name")
@click.option("--description", "-d", default="", help="Repository description")
@click.option("--local-path", "-l", help="Local filesystem path where repository is checked out")
@click.option(
    "--config",
    "-c",
    type=click.Path(),
    help="Path to repositories.yaml file",
)
def add_repo(name, url, ado_id, build_def, description, local_path, config):
    """Add a repository to configuration."""
    if config:
        repo_config_manager.config_path = Path(config)

    try:
        repo = repo_config_manager.add_repository(
            name=name,
            url=url,
            ado_repo_id=ado_id,
            build_definition=build_def,
            description=description,
        )

        # Set local_path if provided
        if local_path:
            repo.local_path = local_path

        repo_config_manager.save()

        console.print(f"[green]Added repository: {repo.name}[/green]")
        if local_path:
            console.print(f"[green]  Local path: {local_path}[/green]")

    except Exception as e:
        console.print(f"[red]Error adding repository: {e}[/red]")


@cli.command(name="repo-validate")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to repositories.yaml file",
)
def validate_repos(config):
    """Validate repository configuration."""
    if config:
        repo_config_manager.config_path = Path(config)

    try:
        repo_config_manager.load()
        errors = repo_config_manager.validate()

        if not errors:
            console.print("[green]✓ Configuration is valid[/green]")
        else:
            console.print("[red]✗ Configuration has errors:[/red]")
            for error in errors:
                console.print(f"  • {error}")

    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")


def main():
    """Main entry point."""
    try:
        cli()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
