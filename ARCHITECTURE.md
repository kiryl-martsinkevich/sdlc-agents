# SDLC Multi-Agent System Architecture

## Overview

This document provides detailed architectural information about the SDLC Multi-Agent System, including design decisions, component interactions, and extension points.

## Core Principles

1. **Agent Autonomy**: Each agent is self-contained and can operate independently
2. **Persistent Memory**: All agents maintain long-term memory in ClickHouse
3. **LLM-Driven**: Decisions and actions are guided by Large Language Models
4. **Event-Driven**: Agents respond to events and coordinate via the orchestrator
5. **Observable**: All actions are logged and can be audited

## Component Architecture

### 1. Agent Base Class

**Location**: `src/sdlc_agents/agents/base.py`

The `Agent` base class provides:

- **Memory Management**: Store and retrieve memories (conversations, observations, decisions)
- **LLM Integration**: `think()` method for LLM-based reasoning
- **Action Tracking**: Log all actions with timing and success metrics
- **Session Management**: Group related activities in sessions

**Key Methods**:
- `think(message)`: Generate LLM response with context
- `observe(observation)`: Record an observation
- `decide(decision)`: Record a decision
- `record_action(action)`: Log an action
- `record_result(result)`: Log a result
- `process_task(task)`: Abstract method for task processing

**Memory Types**:
- `conversation`: User-agent interactions
- `observation`: What the agent observes
- `decision`: Decisions made
- `action`: Actions taken
- `result`: Outcomes

### 2. Orchestrator Agent

**Location**: `src/sdlc_agents/agents/orchestrator.py`

**Responsibilities**:
- Parse natural language requests
- Determine task type and parameters
- Delegate to specialized agents
- Coordinate multi-step workflows
- Handle errors and retries

**Workflow**:
```
User Message
    ↓
Parse Intent (LLM)
    ↓
Determine Task Type
    ↓
├─ implement_story → Requirements Agent → Code Agents
├─ split_feature → ADO Client + LLM
└─ create_release → Release Manager Agent
    ↓
Aggregate Results
    ↓
Return to User
```

**Extension Points**:
- Add new task types in `process_task()`
- Register new specialized agents via `register_agent()`

### 3. Requirements Agent

**Location**: `src/sdlc_agents/agents/requirements_agent.py`

**Responsibilities**:
- Fetch work items from ADO
- Analyze requirements using LLM
- Extract technical details
- Identify affected repositories
- Estimate complexity
- Generate test scenarios

**Analysis Workflow**:
```
Work Item (ADO)
    ↓
Extract Fields (Title, Description, Acceptance Criteria)
    ↓
LLM Analysis
    ↓
├─ Technical Requirements
├─ Affected Components
├─ Data Model Changes
├─ API Changes
├─ UI Changes
├─ Test Scenarios
└─ Ambiguities
    ↓
Store in Memory
    ↓
Return Structured Analysis
```

**Complexity Estimation**:
- Analyzes keywords and requirements
- Returns: Low, Medium, High, Very High
- Based on: Number of components, integrations, complexity indicators

### 4. Code Repository Agent

**Location**: `src/sdlc_agents/agents/code_repo_agent.py`

**Responsibilities**:
- Clone and manage Git repository
- Generate code changes using LLM
- Run Maven builds and tests
- Create commits with meaningful messages
- Create pull requests in ADO
- Fix build failures

**Implementation Workflow**:
```
Task (implement)
    ↓
Analyze Codebase Structure
    ↓
Generate Implementation Plan (LLM)
    ↓
Create Feature Branch
    ↓
Generate Code Changes (LLM)
    ↓
Apply Changes to Files
    ↓
Run Maven Build & Tests
    ↓
├─ Success → Commit & Push
└─ Failure → Analyze & Retry
    ↓
Create Pull Request
    ↓
Return PR Details
```

**Build Process**:
- Uses Maven with `clean test` target
- Timeout: Configurable (default 600s)
- Captures stdout/stderr for analysis
- Returns structured result with exit code

### 5. Build Monitor Agent

**Location**: `src/sdlc_agents/agents/build_monitor_agent.py`

**Responsibilities**:
- Monitor PR builds
- Detect failure types
- Distinguish intermittent vs persistent failures
- Automatically retry intermittent failures
- Request fixes for persistent failures

**Monitoring Workflow**:
```
PR Build Started
    ↓
Track Build Status
    ↓
Build Completed
    ↓
Result: Success → Done
Result: Failed
    ↓
Fetch Build Logs
    ↓
Analyze Failure (LLM)
    ↓
├─ Intermittent → Retry (max 3 times)
└─ Persistent → Request Code Fix
    ↓
Update Tracking
```

**Failure Classification**:
- **Intermittent**: Network issues, timing issues, flaky tests
- **Compilation Error**: Code syntax errors
- **Test Failure**: Failing unit/integration tests
- **Infrastructure**: Build server issues

**Retry Logic**:
- Max retries: 3 (configurable)
- Tracks retry count per build
- Queues new build with same parameters
- Escalates after max retries

### 6. Release Manager Agent

**Location**: `src/sdlc_agents/agents/release_manager_agent.py`

**Responsibilities**:
- Create release work items
- Verify release readiness
- Create release branches
- Generate release notes
- Coordinate multi-component releases

**Release Workflow**:
```
Release Request
    ↓
Verify Readiness (all components)
    ↓
├─ Not Ready → Return Issues
└─ Ready
    ↓
Generate Release Notes (LLM)
    ↓
Create Release Work Item (ADO)
    ↓
Create Release Branches (Git)
    ↓
Link Work Items
    ↓
Return Release Details
```

**Readiness Checks**:
- All builds passing
- All PRs merged
- All tests passing
- No critical bugs open

### 7. LLM Provider System

**Location**: `src/sdlc_agents/llm/`

**Design**:
- Abstract base class: `LLMProvider`
- Implementations: `OllamaProvider`, `OpenAIProvider`
- Factory: `get_llm_provider()`

**Features**:
- Async/await for non-blocking operations
- Streaming support for real-time responses
- Health checks
- Configurable temperature and max tokens
- Automatic retries on failure

**Message Format**:
```python
LLMMessage(role=MessageRole.SYSTEM, content="...")
LLMMessage(role=MessageRole.USER, content="...")
LLMMessage(role=MessageRole.ASSISTANT, content="...")
```

**Response Format**:
```python
LLMResponse(
    content="...",
    model="...",
    tokens_used=123,
    finish_reason="stop",
    raw_response={...}
)
```

### 8. Memory System

**Location**: `src/sdlc_agents/memory/clickhouse_memory.py`

**Schema**:

**agent_memory** table:
```sql
CREATE TABLE agent_memory (
    agent_id String,
    timestamp DateTime64(3),
    memory_type LowCardinality(String),
    content String,
    metadata String,
    session_id Nullable(String)
) ENGINE = MergeTree()
ORDER BY (agent_id, timestamp)
TTL timestamp + INTERVAL 90 DAY
```

**agent_actions** table:
```sql
CREATE TABLE agent_actions (
    agent_id String,
    timestamp DateTime64(3),
    action_type LowCardinality(String),
    target String,
    parameters String,
    result String,
    success Bool,
    duration_ms UInt32,
    session_id Nullable(String)
) ENGINE = MergeTree()
ORDER BY (agent_id, timestamp)
```

**work_items** table:
```sql
CREATE TABLE work_items (
    work_item_id String,
    timestamp DateTime64(3),
    item_type LowCardinality(String),
    title String,
    description String,
    state LowCardinality(String),
    assigned_agent Nullable(String),
    metadata String
) ENGINE = ReplacingMergeTree(timestamp)
ORDER BY work_item_id
```

**Memory Operations**:
- `store_memory()`: Store a memory entry
- `get_recent_memories()`: Retrieve recent memories (with filters)
- `search_memories()`: Full-text search in memories
- `log_action()`: Log an action with timing
- `get_agent_statistics()`: Get performance metrics

### 9. ADO Integration

**Location**: `src/sdlc_agents/integrations/ado_client.py`

**Features**:
- Work item CRUD operations
- Build monitoring and queuing
- Pull request management
- Work item linking
- Feature splitting

**Key Methods**:
- `get_work_item(id)`: Fetch work item details
- `update_work_item(id, fields)`: Update work item
- `create_work_item(type, title, ...)`: Create new work item
- `split_feature_into_stories(id, count)`: Split feature
- `get_build(id)`: Get build details
- `queue_build(definition, branch)`: Queue new build
- `create_pull_request(...)`: Create PR

### 10. CLI Interface

**Location**: `src/sdlc_agents/cli.py`

**Commands**:
- `chat`: Interactive chat mode
- `implement <story_id>`: Implement a story
- `split <feature_id>`: Split a feature
- `release <components>`: Create release
- `info`: Show configuration

**Chat Features**:
- Rich formatting with panels and markdown
- Command parsing (story IDs, feature IDs, components)
- Error handling with user-friendly messages
- Async/await for non-blocking operations

## Data Flow

### Story Implementation

```
User: "implement story 12345"
    ↓
CLI.process_message()
    ↓
Orchestrator.handle_message()
    ↓
Parse Intent (LLM)
    ↓
Orchestrator.process_task(implement_story)
    ↓
ADO.get_work_item(12345)
    ↓
Requirements Agent.analyze_requirements()
    ↓
LLM Analysis
    ↓
Store in Memory
    ↓
For each affected repo:
    Code Agent.implement_changes()
        ↓
    Analyze Codebase
        ↓
    Generate Code (LLM)
        ↓
    Create Branch
        ↓
    Apply Changes
        ↓
    Run Maven Build
        ↓
    Commit & Push
        ↓
    Create PR (ADO)
    ↓
Aggregate Results
    ↓
Return to User
```

### Build Monitoring

```
PR Created in ADO
    ↓
Build Triggered (External)
    ↓
Build Monitor.monitor_pr_build()
    ↓
Poll Build Status
    ↓
Build Failed
    ↓
Fetch Logs (ADO)
    ↓
Analyze Failure (LLM)
    ↓
Intermittent?
├─ Yes → Retry Build (max 3x)
└─ No → Notify Code Agent
    ↓
Code Agent.fix_build()
    ↓
Analyze Errors (LLM)
    ↓
Generate Fix
    ↓
Apply Fix
    ↓
Rebuild
```

## Extension Points

### Adding a New Agent

1. Create class inheriting from `Agent`
2. Define `system_prompt`
3. Specify `capabilities`
4. Implement `process_task()`
5. Register with orchestrator

Example:
```python
class MyCustomAgent(Agent):
    def __init__(self):
        super().__init__(
            agent_id="my_custom_agent",
            name="My Custom Agent",
            capabilities=[AgentCapability.CUSTOM],
            system_prompt="You are a custom agent...",
        )

    async def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        # Implement task processing
        pass
```

### Adding a New LLM Provider

1. Create class inheriting from `LLMProvider`
2. Implement `generate()`, `stream_generate()`, `health_check()`
3. Update `factory.py` to include new provider
4. Add configuration to `config.py`

### Adding a New CLI Command

1. Add `@cli.command()` decorated function
2. Define click options/arguments
3. Create `SDLCAgentSystem` instance
4. Call `system.process_message()` or agent methods
5. Format and display results

## Performance Considerations

### LLM Calls

- Agents make LLM calls for reasoning
- Each call adds latency (1-10s depending on model)
- Use caching when possible
- Consider smaller models for simple tasks

### ClickHouse Queries

- Memory queries are fast (<100ms typically)
- Index on `agent_id` and `timestamp`
- Use `LIMIT` to restrict result sets
- Regular cleanup via TTL

### Git Operations

- Repository cloning is slow (first time)
- Use shallow clones for large repos
- Keep repositories cached locally
- Pull incrementally

### Maven Builds

- Builds can take 1-10 minutes
- Run in background with timeout
- Cache dependencies locally
- Use parallel builds (`-T 1C`)

## Security Considerations

### Credentials

- Store ADO PAT in environment variable
- Never log or expose PAT in memory
- Use read-only tokens where possible
- Rotate tokens regularly

### Code Execution

- Agents can execute arbitrary Maven commands
- Validate input parameters
- Run in sandboxed environment if possible
- Limit file system access

### LLM Prompt Injection

- Agents use system prompts that could be attacked
- Validate user input
- Use separate user/system message roles
- Monitor for suspicious patterns

## Monitoring and Observability

### Metrics to Track

- Agent task success rate
- LLM response times
- Build success rate
- Memory usage (ClickHouse)
- API call counts (ADO, LLM)

### Logging

- All agents log to `sdlc_agents.log`
- Rich console output for CLI
- ClickHouse stores action logs
- Configure log level via `LOG_LEVEL`

### Debugging

Query agent memories:
```sql
SELECT * FROM agent_memory
WHERE agent_id = 'code_repo_backend'
ORDER BY timestamp DESC
LIMIT 100;
```

Query agent actions:
```sql
SELECT
    action_type,
    target,
    success,
    duration_ms
FROM agent_actions
WHERE agent_id = 'code_repo_backend'
  AND timestamp > now() - INTERVAL 1 HOUR;
```

## Future Enhancements

### Phase 2
- Multi-repository atomic commits
- Dependency conflict detection
- Advanced code review
- Security vulnerability scanning

### Phase 3
- Web dashboard for monitoring
- Webhook integration for real-time events
- Slack/Teams notifications
- Approval workflows

### Phase 4
- ML-based failure prediction
- Automated performance testing
- Canary deployments
- Rollback automation
