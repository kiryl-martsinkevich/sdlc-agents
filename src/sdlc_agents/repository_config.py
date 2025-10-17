"""Repository configuration management."""

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from sdlc_agents.config import settings
from sdlc_agents.logging_config import logger


class RepositoryConfig(BaseModel):
    """Configuration for a single repository."""

    name: str = Field(description="Repository name/identifier")
    url: str = Field(description="Git repository URL")
    local_path: Optional[str] = Field(
        default=None,
        description="Local filesystem path where repository is checked out. "
                    "If not provided, agents will use the repository URL for operations."
    )
    ado_repo_id: Optional[str] = Field(default=None, description="Azure DevOps repository ID")
    build_definition: Optional[str] = Field(
        default=None, description="Build definition name in ADO"
    )
    description: str = Field(default="", description="Repository description")
    enabled: bool = Field(default=True, description="Whether this repository is active")
    maven_profiles: list[str] = Field(
        default_factory=list, description="Maven profiles to use"
    )
    custom_build_command: Optional[str] = Field(
        default=None, description="Custom build command (overrides Maven)"
    )
    environment_vars: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for builds"
    )


class ComponentGroup(BaseModel):
    """A group of components for releases."""

    name: str
    repositories: list[str]


class RepositoriesConfiguration(BaseModel):
    """Complete repository configuration."""

    repositories: list[RepositoryConfig] = Field(default_factory=list)
    component_groups: dict[str, list[str]] = Field(default_factory=dict)


class RepositoryConfigManager:
    """Manager for repository configurations."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize repository config manager.

        Args:
            config_path: Path to repositories.yaml file
        """
        self.config_path = config_path or Path("repositories.yaml")
        self.config: Optional[RepositoriesConfiguration] = None

    def load(self) -> RepositoriesConfiguration:
        """
        Load repository configuration from YAML file.

        Returns:
            Repository configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if not self.config_path.exists():
            logger.warning(f"Repository config not found at {self.config_path}")
            # Return empty configuration
            self.config = RepositoriesConfiguration()
            return self.config

        try:
            with open(self.config_path) as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning("Repository config file is empty")
                self.config = RepositoriesConfiguration()
                return self.config

            self.config = RepositoriesConfiguration(**data)
            logger.info(
                f"Loaded {len(self.config.repositories)} repositories from {self.config_path}"
            )

            return self.config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in repository config: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load repository config: {e}")

    def get_enabled_repositories(self) -> list[RepositoryConfig]:
        """
        Get all enabled repositories.

        Returns:
            List of enabled repository configurations
        """
        if not self.config:
            self.load()

        return [repo for repo in self.config.repositories if repo.enabled]

    def get_repository(self, name: str) -> Optional[RepositoryConfig]:
        """
        Get a specific repository by name.

        Args:
            name: Repository name

        Returns:
            Repository configuration or None
        """
        if not self.config:
            self.load()

        for repo in self.config.repositories:
            if repo.name == name:
                return repo

        return None

    def get_component_group(self, group_name: str) -> list[str]:
        """
        Get repositories in a component group.

        Args:
            group_name: Component group name

        Returns:
            List of repository names
        """
        if not self.config:
            self.load()

        return self.config.component_groups.get(group_name, [])

    def get_all_component_groups(self) -> dict[str, list[str]]:
        """
        Get all component groups.

        Returns:
            Dictionary of group names to repository lists
        """
        if not self.config:
            self.load()

        return self.config.component_groups

    def add_repository(
        self,
        name: str,
        url: str,
        ado_repo_id: Optional[str] = None,
        build_definition: Optional[str] = None,
        description: str = "",
    ) -> RepositoryConfig:
        """
        Add a new repository to configuration.

        Args:
            name: Repository name
            url: Git URL
            ado_repo_id: ADO repository ID
            build_definition: Build definition name
            description: Description

        Returns:
            Created repository configuration
        """
        if not self.config:
            self.load()

        repo = RepositoryConfig(
            name=name,
            url=url,
            ado_repo_id=ado_repo_id,
            build_definition=build_definition,
            description=description,
        )

        self.config.repositories.append(repo)
        return repo

    def save(self) -> None:
        """Save current configuration to YAML file."""
        if not self.config:
            raise ValueError("No configuration to save")

        data = self.config.model_dump(exclude_none=True)

        with open(self.config_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Saved repository configuration to {self.config_path}")

    def validate(self) -> list[str]:
        """
        Validate repository configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        if not self.config:
            self.load()

        errors = []

        # Check for duplicate names
        names = [repo.name for repo in self.config.repositories]
        duplicates = [name for name in names if names.count(name) > 1]
        if duplicates:
            errors.append(f"Duplicate repository names: {set(duplicates)}")

        # Check for invalid URLs
        for repo in self.config.repositories:
            if not repo.url.startswith(("http://", "https://", "git@")):
                errors.append(f"Invalid URL for repository {repo.name}: {repo.url}")

        # Check local paths exist if provided
        for repo in self.config.repositories:
            if repo.local_path:
                local_path = Path(repo.local_path).expanduser()
                if not local_path.exists():
                    errors.append(
                        f"Local path for repository {repo.name} does not exist: {repo.local_path}"
                    )
                elif not local_path.is_dir():
                    errors.append(
                        f"Local path for repository {repo.name} is not a directory: {repo.local_path}"
                    )
                # Check if it's a git repository
                elif not (local_path / ".git").exists():
                    logger.warning(
                        f"Local path for repository {repo.name} does not appear to be a git repository: {repo.local_path}"
                    )

        # Check component groups reference valid repositories
        for group_name, repos in self.config.component_groups.items():
            for repo_name in repos:
                if repo_name not in names:
                    errors.append(
                        f"Component group '{group_name}' references "
                        f"unknown repository: {repo_name}"
                    )

        return errors

    def create_example_config(self, path: Optional[Path] = None) -> None:
        """
        Create an example configuration file.

        Args:
            path: Path to save example config
        """
        example_path = path or Path("repositories.yaml.example")

        example_config = RepositoriesConfiguration(
            repositories=[
                RepositoryConfig(
                    name="backend-api",
                    url="https://dev.azure.com/org/project/_git/backend-api",
                    ado_repo_id="12345678-1234-1234-1234-123456789abc",
                    build_definition="Backend-CI",
                    description="Main backend API service",
                ),
                RepositoryConfig(
                    name="frontend-web",
                    url="https://dev.azure.com/org/project/_git/frontend-web",
                    ado_repo_id="87654321-4321-4321-4321-cba987654321",
                    build_definition="Frontend-CI",
                    description="React frontend application",
                ),
            ],
            component_groups={
                "full_stack": ["backend-api", "frontend-web"],
                "backend": ["backend-api"],
            },
        )

        # Save using the manager
        temp_manager = RepositoryConfigManager(example_path)
        temp_manager.config = example_config
        temp_manager.save()

        logger.info(f"Created example configuration at {example_path}")


# Global repository config manager
repo_config_manager = RepositoryConfigManager()
