"""ClickHouse-based persistent memory for agents."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import clickhouse_connect

from sdlc_agents.config import settings
from sdlc_agents.logging_config import logger


@dataclass
class MemoryEntry:
    """A single memory entry."""

    agent_id: str
    timestamp: datetime
    memory_type: str  # conversation, decision, observation, action, result
    content: str
    metadata: dict[str, Any]
    session_id: Optional[str] = None


class ClickHouseMemory:
    """Persistent memory storage using ClickHouse."""

    def __init__(self):
        """Initialize ClickHouse memory client."""
        self.client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
        )
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create necessary tables if they don't exist."""
        # Create database if it doesn't exist
        self.client.command(
            f"CREATE DATABASE IF NOT EXISTS {settings.clickhouse_database}"
        )

        # Agent memory table
        self.client.command(f"""
            CREATE TABLE IF NOT EXISTS {settings.clickhouse_database}.agent_memory (
                agent_id String,
                timestamp DateTime64(3),
                memory_type LowCardinality(String),
                content String,
                metadata String,
                session_id Nullable(String),
                INDEX idx_agent_id agent_id TYPE bloom_filter(0.01) GRANULARITY 1,
                INDEX idx_session_id session_id TYPE bloom_filter(0.01) GRANULARITY 1
            ) ENGINE = MergeTree()
            ORDER BY (agent_id, timestamp)
            TTL timestamp + INTERVAL {settings.agent_memory_retention_days} DAY
            SETTINGS index_granularity = 8192
        """)

        # Agent actions table for tracking what agents did
        self.client.command(f"""
            CREATE TABLE IF NOT EXISTS {settings.clickhouse_database}.agent_actions (
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
            TTL timestamp + INTERVAL {settings.agent_memory_retention_days} DAY
        """)

        # Work item tracking
        self.client.command(f"""
            CREATE TABLE IF NOT EXISTS {settings.clickhouse_database}.work_items (
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
        """)

        logger.info("ClickHouse schema initialized")

    def store_memory(self, entry: MemoryEntry) -> None:
        """Store a memory entry."""
        self.client.insert(
            f"{settings.clickhouse_database}.agent_memory",
            [
                [
                    entry.agent_id,
                    entry.timestamp,
                    entry.memory_type,
                    entry.content,
                    json.dumps(entry.metadata),
                    entry.session_id,
                ]
            ],
            column_names=[
                "agent_id",
                "timestamp",
                "memory_type",
                "content",
                "metadata",
                "session_id",
            ],
        )

    def get_recent_memories(
        self,
        agent_id: str,
        limit: int = 100,
        memory_type: Optional[str] = None,
        session_id: Optional[str] = None,
        hours: int = 24,
    ) -> list[MemoryEntry]:
        """
        Retrieve recent memories for an agent.

        Args:
            agent_id: Agent identifier
            limit: Maximum number of entries
            memory_type: Filter by memory type
            session_id: Filter by session
            hours: Look back this many hours

        Returns:
            List of memory entries
        """
        query = f"""
            SELECT agent_id, timestamp, memory_type, content, metadata, session_id
            FROM {settings.clickhouse_database}.agent_memory
            WHERE agent_id = %(agent_id)s
              AND timestamp > now() - INTERVAL %(hours)s HOUR
        """

        params = {"agent_id": agent_id, "hours": hours}

        if memory_type:
            query += " AND memory_type = %(memory_type)s"
            params["memory_type"] = memory_type

        if session_id:
            query += " AND session_id = %(session_id)s"
            params["session_id"] = session_id

        query += " ORDER BY timestamp DESC LIMIT %(limit)s"
        params["limit"] = limit

        result = self.client.query(query, parameters=params)

        entries = []
        for row in result.result_rows:
            entries.append(
                MemoryEntry(
                    agent_id=row[0],
                    timestamp=row[1],
                    memory_type=row[2],
                    content=row[3],
                    metadata=json.loads(row[4]) if row[4] else {},
                    session_id=row[5],
                )
            )

        return entries

    def log_action(
        self,
        agent_id: str,
        action_type: str,
        target: str,
        parameters: dict[str, Any],
        result: Any,
        success: bool,
        duration_ms: int,
        session_id: Optional[str] = None,
    ) -> None:
        """Log an agent action."""
        self.client.insert(
            f"{settings.clickhouse_database}.agent_actions",
            [
                [
                    agent_id,
                    datetime.now(),
                    action_type,
                    target,
                    json.dumps(parameters),
                    json.dumps(result) if result else "",
                    success,
                    duration_ms,
                    session_id,
                ]
            ],
            column_names=[
                "agent_id",
                "timestamp",
                "action_type",
                "target",
                "parameters",
                "result",
                "success",
                "duration_ms",
                "session_id",
            ],
        )

    def get_agent_statistics(
        self, agent_id: str, hours: int = 24
    ) -> dict[str, Any]:
        """Get statistics about agent activity."""
        query = f"""
            SELECT
                action_type,
                count() as count,
                avg(duration_ms) as avg_duration,
                sum(success) as successful,
                sum(NOT success) as failed
            FROM {settings.clickhouse_database}.agent_actions
            WHERE agent_id = %(agent_id)s
              AND timestamp > now() - INTERVAL %(hours)s HOUR
            GROUP BY action_type
        """

        result = self.client.query(query, parameters={"agent_id": agent_id, "hours": hours})

        stats = {}
        for row in result.result_rows:
            stats[row[0]] = {
                "count": row[1],
                "avg_duration_ms": row[2],
                "successful": row[3],
                "failed": row[4],
            }

        return stats

    def store_work_item(
        self,
        work_item_id: str,
        item_type: str,
        title: str,
        description: str,
        state: str,
        assigned_agent: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Store or update a work item."""
        self.client.insert(
            f"{settings.clickhouse_database}.work_items",
            [
                [
                    work_item_id,
                    datetime.now(),
                    item_type,
                    title,
                    description,
                    state,
                    assigned_agent,
                    json.dumps(metadata or {}),
                ]
            ],
            column_names=[
                "work_item_id",
                "timestamp",
                "item_type",
                "title",
                "description",
                "state",
                "assigned_agent",
                "metadata",
            ],
        )

    def get_work_item(self, work_item_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a work item by ID."""
        query = f"""
            SELECT work_item_id, timestamp, item_type, title, description,
                   state, assigned_agent, metadata
            FROM {settings.clickhouse_database}.work_items
            WHERE work_item_id = %(work_item_id)s
            ORDER BY timestamp DESC
            LIMIT 1
        """

        result = self.client.query(query, parameters={"work_item_id": work_item_id})

        if not result.result_rows:
            return None

        row = result.result_rows[0]
        return {
            "work_item_id": row[0],
            "timestamp": row[1],
            "item_type": row[2],
            "title": row[3],
            "description": row[4],
            "state": row[5],
            "assigned_agent": row[6],
            "metadata": json.loads(row[7]) if row[7] else {},
        }

    def search_memories(
        self,
        agent_id: str,
        query: str,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """
        Search memories by content.

        Args:
            agent_id: Agent identifier
            query: Search query
            limit: Maximum results

        Returns:
            List of matching memory entries
        """
        sql = f"""
            SELECT agent_id, timestamp, memory_type, content, metadata, session_id
            FROM {settings.clickhouse_database}.agent_memory
            WHERE agent_id = %(agent_id)s
              AND positionCaseInsensitive(content, %(query)s) > 0
            ORDER BY timestamp DESC
            LIMIT %(limit)s
        """

        result = self.client.query(
            sql, parameters={"agent_id": agent_id, "query": query, "limit": limit}
        )

        entries = []
        for row in result.result_rows:
            entries.append(
                MemoryEntry(
                    agent_id=row[0],
                    timestamp=row[1],
                    memory_type=row[2],
                    content=row[3],
                    metadata=json.loads(row[4]) if row[4] else {},
                    session_id=row[5],
                )
            )

        return entries

    def close(self) -> None:
        """Close the ClickHouse connection."""
        if self.client:
            self.client.close()
