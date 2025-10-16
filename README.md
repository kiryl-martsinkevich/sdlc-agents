# SDLC Multi-Agent System

A sophisticated multi-agent system for automating Software Development Lifecycle (SDLC) tasks with Azure DevOps integration. This system uses AI agents powered by LLMs (Ollama or OpenAI) to handle requirements analysis, code generation, build monitoring, and release management for Java/Maven projects.

## Features

- **Multi-Agent Architecture**: Specialized agents for different SDLC phases
- **Azure DevOps Integration**: Full integration with ADO work items, builds, and pull requests
- **Persistent Memory**: ClickHouse-based memory system for each agent
- **Flexible LLM Support**: Works with local Ollama or OpenAI-compatible APIs
- **Automated Code Changes**: Agents can modify code, run tests, and create PRs
- **Build Monitoring**: Automatic retry of intermittent failures and error analysis
- **Release Management**: Automated release branch creation and validation

## Architecture

### Agent Hierarchy

```
┌─────────────────────────┐
│  Orchestrator Agent     │  ← Main coordinator
└───────────┬─────────────┘
            │
      ┌─────┴─────────────────────┐
      │                           │
┌─────▼──────────┐    ┌──────────▼────────┐
│ Requirements   │    │ Build Monitor     │
│ Agent          │    │ Agent             │
└────────────────┘    └───────────────────┘
      │                           │
      │                           │
┌─────▼──────────┐    ┌──────────▼────────┐
│ Code Repository│    │ Release Manager   │
│ Agents (N)     │    │ Agent             │
└────────────────┘    └───────────────────┘
```

### Agents

1. **Orchestrator Agent**: Coordinates all other agents, parses user requests, and delegates tasks
2. **Requirements Agent**: Analyzes ADO work items, extracts requirements, identifies affected components
3. **Code Repository Agents**: One per repository, handles code changes, builds, tests, and PRs
4. **Build Monitor Agent**: Watches CI/CD pipelines, retries intermittent failures, analyzes errors
5. **Release Manager Agent**: Creates releases, generates release notes, manages release branches

## Installation

### Prerequisites

- Python 3.11+
- ClickHouse (local or remote instance)
- Ollama (if using local LLM) or OpenAI API key
- Azure DevOps account with Personal Access Token
- Git
- Maven (for Java projects)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd sdlc-agents
```

2. Install dependencies using Poetry:
```bash
# Install Poetry if you don't have it
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

3. Set up ClickHouse:
```bash
# Using Docker
docker run -d --name sdlc-clickhouse \
  -p 8123:8123 \
  -p 9000:9000 \
  clickhouse/clickhouse-server

# Or install locally following ClickHouse documentation
```

4. Set up Ollama (if using local LLM):
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1:8b
```

5. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Configuration

Edit `.env` file:

```bash
# LLM Configuration
LLM_PROVIDER=ollama  # or openai
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4

# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=sdlc_agents

# Azure DevOps
ADO_ORGANIZATION=your-org
ADO_PROJECT=your-project
ADO_PAT=your-personal-access-token

# Git
GIT_USER_NAME=SDLC Agent
GIT_USER_EMAIL=sdlc-agent@example.com
```

## Usage

### Interactive Chat Mode

Start an interactive chat session. The system will automatically load repositories from `repositories.yaml`:

```bash
# Load repositories from repositories.yaml
poetry run sdlc-agent chat

# Or specify repositories on command line (overrides config)
poetry run sdlc-agent chat \
  -r backend:https://dev.azure.com/org/project/_git/backend \
  -r frontend:https://dev.azure.com/org/project/_git/frontend

# Or use a custom config file
poetry run sdlc-agent chat --config path/to/repositories.yaml
```

Example interactions:
```
You: implement story 12345
You: split feature 456 into 5 stories
You: create release for components backend, frontend, api from main
```

### Command-Line Interface

#### List Configured Repositories

```bash
# List all repositories from repositories.yaml
poetry run sdlc-agent repos

# Validate configuration
poetry run sdlc-agent repo-validate

# Add a repository
poetry run sdlc-agent repo-add backend-api \
  https://dev.azure.com/org/project/_git/backend-api \
  --ado-id "12345..." \
  --build-def "Backend-CI" \
  --description "Main backend API"
```

#### Implement a Story

```bash
# Uses repositories from repositories.yaml
poetry run sdlc-agent implement 12345

# Or specify repositories
poetry run sdlc-agent implement 12345 \
  -r backend:https://dev.azure.com/org/project/_git/backend
```

This will:
1. Fetch story details from ADO
2. Analyze requirements
3. Generate code changes
4. Run Maven build and tests
5. Create a pull request

#### Split a Feature

```bash
poetry run sdlc-agent split 456 --count 5
```

This will:
1. Fetch feature details
2. Use LLM to suggest story breakdown
3. Create stories in ADO
4. Link them to the parent feature

#### Create a Release

```bash
poetry run sdlc-agent release backend frontend api --branch main
```

This will:
1. Verify all components have passing builds
2. Create a release work item
3. Generate release notes
4. Create release branches

#### Show System Info

```bash
poetry run sdlc-agent info
```

## Architecture Details

### Memory System

Each agent has persistent memory stored in ClickHouse with:

- **Conversation History**: All interactions with the LLM
- **Observations**: What the agent observes
- **Decisions**: What the agent decides to do
- **Actions**: Actions taken
- **Results**: Outcomes of actions

Tables:
- `agent_memory`: Conversation and context memory
- `agent_actions`: Detailed action logs with timing
- `work_items`: Cached work item data

Memory retention: 90 days (configurable)

### LLM Provider System

Abstracted LLM interface supporting:

- **Ollama**: Local open-source models (llama3.1, codellama, etc.)
- **OpenAI**: GPT-4, GPT-3.5-turbo, etc.
- **OpenAI-compatible APIs**: Any API following OpenAI format

Features:
- Async/await for non-blocking operations
- Streaming support
- Health checks
- Automatic retries

### Code Repository Agent Workflow

1. **Initialization**: Clone/update repository
2. **Requirement Analysis**: Understand what needs to be changed
3. **Code Generation**: Use LLM to generate code changes
4. **Build & Test**: Run Maven clean test
5. **Commit**: Create meaningful commit messages
6. **PR Creation**: Create pull request in ADO
7. **Monitoring**: Watch build status

### Build Monitor Agent Workflow

1. **Monitor PRs**: Watch pull request builds
2. **Detect Failures**: Identify failed builds
3. **Analyze**: Determine if intermittent or real issue
4. **Retry**: Automatically retry intermittent failures (up to 3 times)
5. **Escalate**: Request code fix for persistent failures

### Release Manager Workflow

1. **Verify Readiness**: Check all components have green builds
2. **Create Work Item**: Create release work item in ADO
3. **Generate Notes**: Create comprehensive release notes
4. **Create Branches**: Create release candidate branches
5. **Track**: Monitor release progress

## Advanced Usage

### Repository Configuration Features

The `repositories.yaml` file supports:

**Repository Properties:**
- `name`: Unique identifier
- `url`: Git repository URL
- `ado_repo_id`: Azure DevOps repository ID
- `build_definition`: Build pipeline name
- `description`: Human-readable description
- `enabled`: Enable/disable repository
- `maven_profiles`: Maven profiles to use
- `custom_build_command`: Override default Maven command
- `environment_vars`: Environment variables for builds

**Component Groups:**
Define groups of components for releases:

```yaml
component_groups:
  full_stack:
    - backend-api
    - frontend-web
    - shared-lib

  backend:
    - backend-api
    - shared-lib

  critical:
    - backend-api
```

Use component groups in release commands:

```bash
# Release an entire group
poetry run sdlc-agent release full_stack --branch main
```

### Custom Agent Prompts

Agents use system prompts that can be customized by editing the agent classes. Each agent's behavior is defined in its system prompt.

### Memory Queries

Access agent memory via ClickHouse:

```sql
-- Recent agent activity
SELECT agent_id, memory_type, content, timestamp
FROM sdlc_agents.agent_memory
WHERE timestamp > now() - INTERVAL 1 HOUR
ORDER BY timestamp DESC;

-- Agent performance
SELECT
    agent_id,
    action_type,
    count() as total,
    avg(duration_ms) as avg_duration,
    sum(success) as successful
FROM sdlc_agents.agent_actions
GROUP BY agent_id, action_type;
```

## Development

### Project Structure

```
sdlc-agents/
├── src/sdlc_agents/
│   ├── agents/              # Agent implementations
│   │   ├── base.py          # Base agent class
│   │   ├── orchestrator.py
│   │   ├── requirements_agent.py
│   │   ├── code_repo_agent.py
│   │   ├── build_monitor_agent.py
│   │   └── release_manager_agent.py
│   ├── llm/                 # LLM provider abstraction
│   │   ├── base.py
│   │   ├── ollama_provider.py
│   │   ├── openai_provider.py
│   │   └── factory.py
│   ├── memory/              # Memory system
│   │   └── clickhouse_memory.py
│   ├── integrations/        # External integrations
│   │   └── ado_client.py
│   ├── config.py            # Configuration management
│   ├── logging_config.py    # Logging setup
│   └── cli.py               # CLI interface
├── tests/                   # Test suite
├── pyproject.toml           # Poetry configuration
├── .env.example             # Environment template
└── README.md                # This file
```

### Running Tests

```bash
poetry run pytest
poetry run pytest --cov=sdlc_agents
```

### Code Quality

```bash
# Format code
poetry run black src/

# Lint
poetry run ruff check src/

# Type checking
poetry run mypy src/
```

## Troubleshooting

### ClickHouse Connection Issues

```bash
# Check if ClickHouse is running
curl http://localhost:8123/ping

# Check logs
docker logs sdlc-clickhouse
```

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check available models
ollama list
```

### ADO Authentication Issues

- Ensure PAT has required scopes: Code (Read, Write), Work Items (Read, Write), Build (Read, Execute)
- Check PAT expiration
- Verify organization and project names

### Maven Build Failures

- Ensure Maven is installed: `mvn --version`
- Check MAVEN_HOME environment variable
- Verify Java version compatibility

## Performance Tuning

### LLM Response Time

- Use smaller models for faster responses (llama3.1:8b vs llama3.1:70b)
- Adjust temperature (lower = faster, more deterministic)
- Use streaming for real-time feedback

### Memory Performance

- Adjust `AGENT_MEMORY_RETENTION_DAYS` to reduce database size
- Use ClickHouse partitioning for large deployments
- Consider SSD storage for ClickHouse data

### Build Timeouts

- Adjust `BUILD_TIMEOUT` for slower builds
- Use parallel Maven builds: `MAVEN_OPTS=-T 1C`

## Roadmap

- [ ] Support for additional version control systems (GitHub, GitLab)
- [ ] Integration with Jira
- [ ] Support for other build tools (Gradle, npm)
- [ ] Multi-language support (Python, TypeScript, Go)
- [ ] Web dashboard for monitoring agents
- [ ] Webhook support for real-time event processing
- [ ] Advanced code review capabilities
- [ ] Automated security scanning
- [ ] Performance regression detection

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: [link]
- Documentation: [link]
- Email: [your-email]
