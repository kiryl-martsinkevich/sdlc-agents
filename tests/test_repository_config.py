"""Tests for repository configuration."""

from pathlib import Path

import pytest
import yaml

from sdlc_agents.repository_config import (
    ComponentGroup,
    RepositoriesConfiguration,
    RepositoryConfig,
    RepositoryConfigManager,
)


@pytest.mark.unit
class TestRepositoryConfig:
    """Tests for RepositoryConfig model."""

    def test_create_repository_config(self):
        """Test creating a repository config."""
        config = RepositoryConfig(
            name="test-repo",
            url="https://github.com/test/repo",
            ado_repo_id="test-id",
            build_definition="Test-CI",
            description="Test repository",
            enabled=True,
        )

        assert config.name == "test-repo"
        assert config.url == "https://github.com/test/repo"
        assert config.ado_repo_id == "test-id"
        assert config.enabled is True

    def test_repository_config_defaults(self):
        """Test default values."""
        config = RepositoryConfig(name="test", url="https://test.com")

        assert config.enabled is True
        assert config.description == ""
        assert config.maven_profiles == []
        assert config.environment_vars == {}


@pytest.mark.unit
class TestRepositoriesConfiguration:
    """Tests for RepositoriesConfiguration."""

    def test_create_configuration(self):
        """Test creating a configuration."""
        config = RepositoriesConfiguration(
            repositories=[
                RepositoryConfig(name="repo1", url="https://test1.com"),
                RepositoryConfig(name="repo2", url="https://test2.com"),
            ],
            component_groups={"group1": ["repo1", "repo2"]},
        )

        assert len(config.repositories) == 2
        assert "group1" in config.component_groups
        assert config.component_groups["group1"] == ["repo1", "repo2"]


@pytest.mark.unit
class TestRepositoryConfigManager:
    """Tests for RepositoryConfigManager."""

    def test_load_configuration(self, sample_repository_config):
        """Test loading configuration from file."""
        manager = RepositoryConfigManager(sample_repository_config)
        config = manager.load()

        assert len(config.repositories) == 3
        assert config.repositories[0].name == "test-backend"
        assert config.repositories[1].name == "test-frontend"
        assert "full_stack" in config.component_groups

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from nonexistent file."""
        manager = RepositoryConfigManager(tmp_path / "nonexistent.yaml")
        config = manager.load()

        # Should return empty configuration
        assert len(config.repositories) == 0

    def test_get_enabled_repositories(self, sample_repository_config):
        """Test getting only enabled repositories."""
        manager = RepositoryConfigManager(sample_repository_config)
        manager.load()

        enabled = manager.get_enabled_repositories()

        assert len(enabled) == 2
        assert all(repo.enabled for repo in enabled)
        assert "disabled-repo" not in [repo.name for repo in enabled]

    def test_get_repository(self, sample_repository_config):
        """Test getting a specific repository."""
        manager = RepositoryConfigManager(sample_repository_config)
        manager.load()

        repo = manager.get_repository("test-backend")

        assert repo is not None
        assert repo.name == "test-backend"
        assert repo.url == "https://dev.azure.com/test/project/_git/backend"

    def test_get_nonexistent_repository(self, sample_repository_config):
        """Test getting a nonexistent repository."""
        manager = RepositoryConfigManager(sample_repository_config)
        manager.load()

        repo = manager.get_repository("nonexistent")

        assert repo is None

    def test_get_component_group(self, sample_repository_config):
        """Test getting a component group."""
        manager = RepositoryConfigManager(sample_repository_config)
        manager.load()

        group = manager.get_component_group("full_stack")

        assert len(group) == 2
        assert "test-backend" in group
        assert "test-frontend" in group

    def test_get_nonexistent_component_group(self, sample_repository_config):
        """Test getting a nonexistent component group."""
        manager = RepositoryConfigManager(sample_repository_config)
        manager.load()

        group = manager.get_component_group("nonexistent")

        assert group == []

    def test_add_repository(self, tmp_path):
        """Test adding a repository."""
        config_path = tmp_path / "repos.yaml"
        manager = RepositoryConfigManager(config_path)
        manager.load()

        repo = manager.add_repository(
            name="new-repo",
            url="https://test.com/new-repo",
            ado_repo_id="new-id",
            build_definition="New-CI",
            description="New repository",
        )

        assert repo.name == "new-repo"
        assert len(manager.config.repositories) == 1

    def test_save_configuration(self, tmp_path):
        """Test saving configuration."""
        config_path = tmp_path / "repos.yaml"
        manager = RepositoryConfigManager(config_path)
        manager.load()

        manager.add_repository(
            name="test-repo", url="https://test.com", description="Test"
        )

        manager.save()

        # Verify file was created and is valid YAML
        assert config_path.exists()
        with open(config_path) as f:
            data = yaml.safe_load(f)
        assert "repositories" in data
        assert len(data["repositories"]) == 1

    def test_validate_configuration(self, sample_repository_config):
        """Test validating configuration."""
        manager = RepositoryConfigManager(sample_repository_config)
        manager.load()

        errors = manager.validate()

        # Should have no errors
        assert len(errors) == 0

    def test_validate_duplicate_names(self, tmp_path):
        """Test validation catches duplicate names."""
        config_content = """
repositories:
  - name: duplicate
    url: https://test1.com
  - name: duplicate
    url: https://test2.com
"""
        config_path = tmp_path / "repos.yaml"
        config_path.write_text(config_content)

        manager = RepositoryConfigManager(config_path)
        manager.load()

        errors = manager.validate()

        assert len(errors) > 0
        assert any("duplicate" in error.lower() for error in errors)

    def test_validate_invalid_url(self, tmp_path):
        """Test validation catches invalid URLs."""
        config_content = """
repositories:
  - name: test
    url: invalid-url
"""
        config_path = tmp_path / "repos.yaml"
        config_path.write_text(config_content)

        manager = RepositoryConfigManager(config_path)
        manager.load()

        errors = manager.validate()

        assert len(errors) > 0
        assert any("invalid url" in error.lower() for error in errors)

    def test_validate_invalid_component_group(self, tmp_path):
        """Test validation catches invalid component group references."""
        config_content = """
repositories:
  - name: repo1
    url: https://test.com

component_groups:
  group1:
    - repo1
    - nonexistent
"""
        config_path = tmp_path / "repos.yaml"
        config_path.write_text(config_content)

        manager = RepositoryConfigManager(config_path)
        manager.load()

        errors = manager.validate()

        assert len(errors) > 0
        assert any("nonexistent" in error for error in errors)
