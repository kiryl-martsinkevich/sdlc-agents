"""Configuration management for SDLC agents."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    llm_provider: LLMProvider = Field(default=LLMProvider.OLLAMA)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1:8b")
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4")
    openai_base_url: str = Field(default="https://api.openai.com/v1")

    # ClickHouse Configuration
    clickhouse_host: str = Field(default="localhost")
    clickhouse_port: int = Field(default=8123)
    clickhouse_user: str = Field(default="default")
    clickhouse_password: str = Field(default="")
    clickhouse_database: str = Field(default="sdlc_agents")

    # Azure DevOps Configuration
    ado_organization: str = Field(default="")
    ado_project: str = Field(default="")
    ado_pat: str = Field(default="")
    ado_base_url: str = Field(default="https://dev.azure.com")

    # Git Configuration
    git_user_name: str = Field(default="SDLC Agent")
    git_user_email: str = Field(default="sdlc-agent@example.com")

    # Maven Configuration
    maven_home: Optional[Path] = Field(default=None)
    maven_opts: str = Field(default="-Xmx2g")

    # Agent Configuration
    max_retries: int = Field(default=3)
    build_timeout: int = Field(default=600)
    agent_memory_retention_days: int = Field(default=90)

    # Logging
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="sdlc_agents.log")

    # Workspace
    workspace_dir: Path = Field(default=Path("workspace"))
    repos_dir: Path = Field(default=Path("repos"))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
