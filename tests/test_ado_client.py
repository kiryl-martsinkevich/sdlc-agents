"""Tests for Azure DevOps client."""

import pytest
from unittest.mock import MagicMock, patch

from sdlc_agents.integrations.ado_client import ADOClient


@pytest.mark.unit
class TestADOClient:
    """Tests for ADO client."""

    @patch("requests.get")
    def test_get_work_item(self, mock_get):
        """Test getting a work item."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "fields": {
                "System.WorkItemType": "User Story",
                "System.Title": "Test Story",
                "System.Description": "Test description",
                "System.State": "New",
                "System.AssignedTo": {"displayName": "Test User"},
                "System.Tags": "test",
            },
        }
        mock_get.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        work_item = client.get_work_item(12345)

        assert work_item is not None
        assert work_item["id"] == 12345
        assert work_item["type"] == "User Story"
        assert work_item["title"] == "Test Story"
        assert work_item["state"] == "New"

    @patch("requests.get")
    def test_get_nonexistent_work_item(self, mock_get):
        """Test getting a nonexistent work item."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        work_item = client.get_work_item(99999)

        assert work_item is None

    @patch("requests.post")
    def test_create_work_item(self, mock_post):
        """Test creating a work item."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12346,
            "fields": {
                "System.WorkItemType": "User Story",
                "System.Title": "New Story",
                "System.Description": "New description",
                "System.State": "New",
            },
        }
        mock_post.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        work_item = client.create_work_item(
            work_item_type="User Story",
            title="New Story",
            description="New description",
            assigned_to="test@example.com",
        )

        assert work_item is not None
        assert work_item["id"] == 12346
        assert work_item["title"] == "New Story"

    @patch("requests.get")
    def test_get_build(self, mock_get):
        """Test getting a build."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 1,
            "buildNumber": "20250101.1",
            "status": "completed",
            "result": "succeeded",
            "sourceBranch": "refs/heads/main",
            "sourceVersion": "abc123",
            "definition": {"name": "Test-CI"},
        }
        mock_get.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        build = client.get_build(1)

        assert build is not None
        assert build["id"] == 1
        assert build["build_number"] == "20250101.1"
        assert build["status"] == "completed"
        assert build["result"] == "succeeded"

    @patch("requests.post")
    def test_queue_build(self, mock_post):
        """Test queueing a build."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 2,
            "buildNumber": "20250101.2",
            "status": "notStarted",
        }
        mock_post.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        build = client.queue_build(
            definition_name="Test-CI", branch="refs/heads/feature/test"
        )

        assert build is not None
        assert build["id"] == 2
        assert build["status"] == "notStarted"

    @patch("requests.post")
    def test_create_pull_request(self, mock_post):
        """Test creating a pull request."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "pullRequestId": 100,
            "title": "Test PR",
            "description": "Test PR description",
            "status": "active",
            "sourceRefName": "refs/heads/feature/test",
            "targetRefName": "refs/heads/main",
        }
        mock_post.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        pr = client.create_pull_request(
            repository_id="test-repo-id",
            source_branch="feature/test",
            target_branch="main",
            title="Test PR",
            description="Test PR description",
        )

        assert pr is not None
        assert pr["id"] == 100
        assert pr["title"] == "Test PR"
        assert pr["status"] == "active"

    @patch("requests.get")
    @patch("requests.post")
    def test_split_feature_into_stories(self, mock_post, mock_get):
        """Test splitting a feature into stories."""
        # Mock get_work_item
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "id": 12345,
            "fields": {
                "System.WorkItemType": "Feature",
                "System.Title": "Test Feature",
                "System.Description": "Feature description",
                "System.State": "New",
            },
        }
        mock_get.return_value = mock_get_response

        # Mock create_work_item calls
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "id": 12346,
            "fields": {
                "System.WorkItemType": "User Story",
                "System.Title": "Story 1",
                "System.State": "New",
            },
        }
        mock_post.return_value = mock_post_response

        client = ADOClient("test-org", "test-project", "test-pat")
        stories = client.split_feature_into_stories(12345, 3)

        assert len(stories) == 3
        assert all(story["type"] == "User Story" for story in stories)

    @patch("requests.patch")
    def test_link_work_items(self, mock_patch):
        """Test linking work items."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 12345}
        mock_patch.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        result = client.link_work_items(
            source_id=12345, target_id=12346, link_type="Parent"
        )

        assert result is True
        assert mock_patch.called

    @patch("requests.patch")
    def test_update_work_item_state(self, mock_patch):
        """Test updating work item state."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "fields": {"System.State": "Active"},
        }
        mock_patch.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        result = client.update_work_item_state(12345, "Active")

        assert result is True

    @patch("requests.get")
    def test_get_repository_branches(self, mock_get):
        """Test getting repository branches."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"name": "refs/heads/main"},
                {"name": "refs/heads/develop"},
                {"name": "refs/heads/feature/test"},
            ]
        }
        mock_get.return_value = mock_response

        client = ADOClient("test-org", "test-project", "test-pat")
        branches = client.get_repository_branches("test-repo-id")

        assert len(branches) == 3
        assert "main" in branches
        assert "develop" in branches

    @patch("requests.get")
    def test_api_error_handling(self, mock_get):
        """Test API error handling."""
        mock_get.side_effect = Exception("Connection error")

        client = ADOClient("test-org", "test-project", "test-pat")
        work_item = client.get_work_item(12345)

        assert work_item is None
