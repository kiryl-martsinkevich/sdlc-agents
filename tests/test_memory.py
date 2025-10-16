"""Tests for memory system."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from sdlc_agents.memory.clickhouse_memory import ClickHouseMemory, MemoryEntry


@pytest.mark.unit
class TestMemoryEntry:
    """Tests for MemoryEntry."""

    def test_create_memory_entry(self):
        """Test creating a memory entry."""
        entry = MemoryEntry(
            agent_id="test-agent",
            timestamp=datetime.now(),
            memory_type="conversation",
            content="Test content",
            metadata={"key": "value"},
            session_id="session-123",
        )

        assert entry.agent_id == "test-agent"
        assert entry.memory_type == "conversation"
        assert entry.content == "Test content"
        assert entry.metadata == {"key": "value"}
        assert entry.session_id == "session-123"


@pytest.mark.unit
class TestClickHouseMemory:
    """Tests for ClickHouse memory."""

    @patch("clickhouse_connect.get_client")
    def test_initialize_schema(self, mock_get_client):
        """Test schema initialization."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        memory = ClickHouseMemory()

        # Verify database creation
        assert mock_client.command.called
        calls = [str(call) for call in mock_client.command.call_args_list]
        assert any("CREATE DATABASE" in str(call) for call in calls)
        assert any("CREATE TABLE" in str(call) for call in calls)

    @patch("clickhouse_connect.get_client")
    def test_store_memory(self, mock_get_client):
        """Test storing a memory entry."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        memory = ClickHouseMemory()

        entry = MemoryEntry(
            agent_id="test-agent",
            timestamp=datetime.now(),
            memory_type="observation",
            content="Test observation",
            metadata={"test": "data"},
        )

        memory.store_memory(entry)

        # Verify insert was called
        assert mock_client.insert.called
        call_args = mock_client.insert.call_args
        assert "agent_memory" in call_args[0][0]

    @patch("clickhouse_connect.get_client")
    def test_get_recent_memories(self, mock_get_client):
        """Test retrieving recent memories."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock query result
        mock_result = MagicMock()
        mock_result.result_rows = [
            (
                "test-agent",
                datetime.now(),
                "conversation",
                "Test content",
                '{"key": "value"}',
                "session-123",
            )
        ]
        mock_client.query.return_value = mock_result

        memory = ClickHouseMemory()
        memories = memory.get_recent_memories("test-agent", limit=10)

        assert len(memories) == 1
        assert memories[0].agent_id == "test-agent"
        assert memories[0].memory_type == "conversation"
        assert memories[0].content == "Test content"

    @patch("clickhouse_connect.get_client")
    def test_log_action(self, mock_get_client):
        """Test logging an action."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        memory = ClickHouseMemory()

        memory.log_action(
            agent_id="test-agent",
            action_type="code_generation",
            target="test.py",
            parameters={"language": "python"},
            result={"success": True},
            success=True,
            duration_ms=1500,
        )

        assert mock_client.insert.called
        call_args = mock_client.insert.call_args
        assert "agent_actions" in call_args[0][0]

    @patch("clickhouse_connect.get_client")
    def test_search_memories(self, mock_get_client):
        """Test searching memories."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = MagicMock()
        mock_result.result_rows = [
            (
                "test-agent",
                datetime.now(),
                "observation",
                "Test search result",
                "{}",
                None,
            )
        ]
        mock_client.query.return_value = mock_result

        memory = ClickHouseMemory()
        results = memory.search_memories("test-agent", "search", limit=50)

        assert len(results) == 1
        assert results[0].content == "Test search result"

    @patch("clickhouse_connect.get_client")
    def test_store_work_item(self, mock_get_client):
        """Test storing a work item."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        memory = ClickHouseMemory()

        memory.store_work_item(
            work_item_id="12345",
            item_type="User Story",
            title="Test Story",
            description="Test description",
            state="New",
            assigned_agent="test-agent",
            metadata={"priority": "high"},
        )

        assert mock_client.insert.called
        call_args = mock_client.insert.call_args
        assert "work_items" in call_args[0][0]
