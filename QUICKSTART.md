# Quick Start Guide

Get started with the SDLC Multi-Agent System in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Poetry (Python package manager)
- Azure DevOps account with PAT

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd sdlc-agents

# Run automated setup
make setup
```

This will:
- Install Python dependencies
- Start ClickHouse and Ollama in Docker
- Pull the default LLM model (llama3.1:8b)
- Create a `.env` file from template

## Step 2: Configure

Edit the `.env` file with your details:

```bash
# Required: Azure DevOps credentials
ADO_ORGANIZATION=your-org-name
ADO_PROJECT=your-project-name
ADO_PAT=your-personal-access-token

# Optional: Use OpenAI instead of Ollama
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...
```

**Getting an ADO Personal Access Token:**
1. Go to https://dev.azure.com/[your-org]/_usersSettings/tokens
2. Click "New Token"
3. Grant these scopes: Code (Read, Write), Work Items (Read, Write), Build (Read, Execute)
4. Copy the token to your `.env` file

## Step 3: Verify Setup

```bash
# Check system configuration
make info

# Check Docker services
docker ps
```

You should see:
- `sdlc-clickhouse` running on port 8123
- `sdlc-ollama` running on port 11434

## Step 4: First Command

Try implementing a story:

```bash
poetry run sdlc-agent implement 12345 \
  -r backend:https://dev.azure.com/org/project/_git/backend
```

Replace `12345` with an actual story ID from your ADO project.

## Step 5: Interactive Mode

Start the interactive chat:

```bash
make run
```

Try these commands:
```
implement story 12345
split feature 456
create release for components backend, frontend from main
```

## Common Commands

```bash
# Start interactive chat
make run

# Implement a specific story
poetry run sdlc-agent implement <story-id> -r <repo-name>:<repo-url>

# Split a feature into stories
poetry run sdlc-agent split <feature-id> --count 5

# Create a release
poetry run sdlc-agent release backend frontend api --branch main

# Show system info
poetry run sdlc-agent info

# View logs
make docker-logs
```

## Repository Configuration

For projects with multiple repositories, create a repositories file:

```bash
cat > repos.txt << EOF
backend:https://dev.azure.com/org/project/_git/backend
frontend:https://dev.azure.com/org/project/_git/frontend
api:https://dev.azure.com/org/project/_git/api
EOF
```

Then use it:

```bash
poetry run sdlc-agent chat \
  -r backend:https://dev.azure.com/org/project/_git/backend \
  -r frontend:https://dev.azure.com/org/project/_git/frontend \
  -r api:https://dev.azure.com/org/project/_git/api
```

## Troubleshooting

### "ClickHouse connection refused"

```bash
# Check if ClickHouse is running
docker ps | grep clickhouse

# If not, start it
docker-compose up -d clickhouse

# Check logs
docker logs sdlc-clickhouse
```

### "Ollama connection refused"

```bash
# Check if Ollama is running
docker ps | grep ollama

# Start it
docker-compose up -d ollama

# Pull model if needed
docker exec sdlc-ollama ollama pull llama3.1:8b

# Verify
curl http://localhost:11434/api/tags
```

### "ADO authentication failed"

- Verify your PAT in `.env`
- Check PAT hasn't expired
- Ensure PAT has required scopes
- Test manually: `curl -u :<PAT> https://dev.azure.com/<org>/_apis/projects`

### "Maven build failed"

- Ensure Maven is installed: `mvn --version`
- Check `MAVEN_HOME` environment variable
- Verify Java version compatibility
- Try running Maven manually in the repository

## Next Steps

1. Read the full [README.md](README.md) for detailed documentation
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
3. Check [examples/basic_usage.py](examples/basic_usage.py) for code examples
4. Explore agent behaviors and customize as needed

## Getting Help

- Check logs: `tail -f sdlc_agents.log`
- View agent memory: Query ClickHouse at http://localhost:8123
- Enable debug logging: Set `LOG_LEVEL=DEBUG` in `.env`
- Review GitHub Issues: [link to issues]

## Demo Workflow

Here's a complete workflow to try:

1. **Get a story from ADO**:
   ```bash
   poetry run sdlc-agent implement 12345 \
     -r myapp:https://dev.azure.com/org/project/_git/myapp
   ```

2. **Agent will**:
   - Fetch story details from ADO
   - Analyze requirements using LLM
   - Clone/update the repository
   - Generate code changes
   - Run Maven tests
   - Create a feature branch
   - Commit changes
   - Create a pull request

3. **Monitor the build**:
   The Build Monitor Agent automatically watches the PR build and retries if needed

4. **Create a release**:
   ```bash
   poetry run sdlc-agent release myapp --branch main
   ```

   This will:
   - Verify builds are green
   - Create a release work item
   - Generate release notes
   - Create release branches

## Tips

- Use `ctrl+c` to exit interactive mode gracefully
- Agent memory persists across sessions in ClickHouse
- Each repository gets its own dedicated Code Agent
- Build Monitor automatically retries flaky tests (up to 3 times)
- Release Manager verifies all components before creating a release

Enjoy automating your SDLC! 🚀
