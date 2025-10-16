"""Azure DevOps integration client."""

from typing import Any, Optional

from azure.devops.connection import Connection
from azure.devops.v7_1.build import BuildClient
from azure.devops.v7_1.git import GitClient
from azure.devops.v7_1.work_item_tracking import WorkItemTrackingClient
from msrest.authentication import BasicAuthentication

from sdlc_agents.config import settings
from sdlc_agents.logging_config import logger


class ADOClient:
    """Client for interacting with Azure DevOps."""

    def __init__(self):
        """Initialize ADO client."""
        if not settings.ado_pat or not settings.ado_organization:
            raise ValueError("Azure DevOps configuration missing")

        credentials = BasicAuthentication("", settings.ado_pat)
        self.connection = Connection(
            base_url=f"{settings.ado_base_url}/{settings.ado_organization}",
            creds=credentials,
        )

        self.work_item_client: WorkItemTrackingClient = (
            self.connection.clients.get_work_item_tracking_client()
        )
        self.build_client: BuildClient = self.connection.clients.get_build_client()
        self.git_client: GitClient = self.connection.clients.get_git_client()

        logger.info(f"Connected to ADO: {settings.ado_organization}/{settings.ado_project}")

    def get_work_item(self, work_item_id: int) -> Optional[dict[str, Any]]:
        """
        Get work item details.

        Args:
            work_item_id: Work item ID

        Returns:
            Work item details or None if not found
        """
        try:
            work_item = self.work_item_client.get_work_item(
                id=work_item_id, expand="All"
            )

            if not work_item:
                return None

            return {
                "id": work_item.id,
                "type": work_item.fields.get("System.WorkItemType"),
                "title": work_item.fields.get("System.Title"),
                "description": work_item.fields.get("System.Description", ""),
                "state": work_item.fields.get("System.State"),
                "assigned_to": work_item.fields.get("System.AssignedTo", {}).get("displayName"),
                "tags": work_item.fields.get("System.Tags", ""),
                "acceptance_criteria": work_item.fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
                "fields": work_item.fields,
            }
        except Exception as e:
            logger.error(f"Failed to get work item {work_item_id}: {e}")
            return None

    def update_work_item(
        self, work_item_id: int, fields: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Update work item fields.

        Args:
            work_item_id: Work item ID
            fields: Fields to update

        Returns:
            Updated work item or None if failed
        """
        try:
            from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation

            document = []
            for field, value in fields.items():
                document.append(
                    JsonPatchOperation(
                        op="add",
                        path=f"/fields/{field}",
                        value=value,
                    )
                )

            work_item = self.work_item_client.update_work_item(
                document=document,
                id=work_item_id,
                project=settings.ado_project,
            )

            return self.get_work_item(work_item.id)
        except Exception as e:
            logger.error(f"Failed to update work item {work_item_id}: {e}")
            return None

    def create_work_item(
        self,
        work_item_type: str,
        title: str,
        description: str = "",
        **fields: Any,
    ) -> Optional[dict[str, Any]]:
        """
        Create a new work item.

        Args:
            work_item_type: Type (Story, Task, Bug, etc.)
            title: Work item title
            description: Description
            **fields: Additional fields

        Returns:
            Created work item or None if failed
        """
        try:
            from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation

            document = [
                JsonPatchOperation(
                    op="add",
                    path="/fields/System.Title",
                    value=title,
                ),
                JsonPatchOperation(
                    op="add",
                    path="/fields/System.Description",
                    value=description,
                ),
            ]

            for field, value in fields.items():
                document.append(
                    JsonPatchOperation(
                        op="add",
                        path=f"/fields/{field}",
                        value=value,
                    )
                )

            work_item = self.work_item_client.create_work_item(
                document=document,
                project=settings.ado_project,
                type=work_item_type,
            )

            return self.get_work_item(work_item.id)
        except Exception as e:
            logger.error(f"Failed to create work item: {e}")
            return None

    def split_feature_into_stories(
        self, feature_id: int, story_count: int = 3
    ) -> list[dict[str, Any]]:
        """
        Split a feature into multiple stories.

        Args:
            feature_id: Feature work item ID
            story_count: Number of stories to create

        Returns:
            List of created stories
        """
        feature = self.get_work_item(feature_id)
        if not feature:
            return []

        stories = []
        for i in range(story_count):
            story = self.create_work_item(
                work_item_type="User Story",
                title=f"{feature['title']} - Story {i + 1}",
                description=f"Part {i + 1} of {story_count} for feature {feature_id}",
            )
            if story:
                # Link to parent feature
                self.link_work_items(story["id"], feature_id, "Parent")
                stories.append(story)

        return stories

    def link_work_items(
        self, source_id: int, target_id: int, link_type: str = "Related"
    ) -> bool:
        """
        Create a link between work items.

        Args:
            source_id: Source work item ID
            target_id: Target work item ID
            link_type: Link type (Parent, Child, Related, etc.)

        Returns:
            True if successful
        """
        try:
            from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation

            document = [
                JsonPatchOperation(
                    op="add",
                    path="/relations/-",
                    value={
                        "rel": f"System.LinkTypes.Hierarchy-{link_type}",
                        "url": f"{settings.ado_base_url}/{settings.ado_organization}/_apis/wit/workItems/{target_id}",
                    },
                )
            ]

            self.work_item_client.update_work_item(
                document=document,
                id=source_id,
                project=settings.ado_project,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to link work items: {e}")
            return False

    def get_build(self, build_id: int) -> Optional[dict[str, Any]]:
        """
        Get build details.

        Args:
            build_id: Build ID

        Returns:
            Build details or None
        """
        try:
            build = self.build_client.get_build(
                project=settings.ado_project,
                build_id=build_id,
            )

            return {
                "id": build.id,
                "build_number": build.build_number,
                "status": build.status,
                "result": build.result,
                "source_branch": build.source_branch,
                "source_version": build.source_version,
                "definition": build.definition.name if build.definition else None,
                "queue_time": build.queue_time,
                "start_time": build.start_time,
                "finish_time": build.finish_time,
            }
        except Exception as e:
            logger.error(f"Failed to get build {build_id}: {e}")
            return None

    def queue_build(
        self, definition_name: str, branch: str = "main", **parameters: Any
    ) -> Optional[dict[str, Any]]:
        """
        Queue a new build.

        Args:
            definition_name: Build definition name
            branch: Source branch
            **parameters: Build parameters

        Returns:
            Queued build details or None
        """
        try:
            from azure.devops.v7_1.build.models import Build

            # Get definition
            definitions = self.build_client.get_definitions(
                project=settings.ado_project,
                name=definition_name,
            )

            if not definitions:
                logger.error(f"Build definition not found: {definition_name}")
                return None

            definition = definitions[0]

            build = Build(
                definition=definition,
                source_branch=f"refs/heads/{branch}",
                parameters=str(parameters) if parameters else None,
            )

            queued_build = self.build_client.queue_build(
                build=build,
                project=settings.ado_project,
            )

            return self.get_build(queued_build.id)
        except Exception as e:
            logger.error(f"Failed to queue build: {e}")
            return None

    def get_pull_request(
        self, repository_id: str, pull_request_id: int
    ) -> Optional[dict[str, Any]]:
        """
        Get pull request details.

        Args:
            repository_id: Repository ID
            pull_request_id: PR ID

        Returns:
            PR details or None
        """
        try:
            pr = self.git_client.get_pull_request(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                project=settings.ado_project,
            )

            return {
                "id": pr.pull_request_id,
                "title": pr.title,
                "description": pr.description,
                "status": pr.status,
                "source_branch": pr.source_ref_name,
                "target_branch": pr.target_ref_name,
                "created_by": pr.created_by.display_name if pr.created_by else None,
                "creation_date": pr.creation_date,
            }
        except Exception as e:
            logger.error(f"Failed to get PR {pull_request_id}: {e}")
            return None

    def create_pull_request(
        self,
        repository_id: str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str = "",
    ) -> Optional[dict[str, Any]]:
        """
        Create a pull request.

        Args:
            repository_id: Repository ID
            source_branch: Source branch
            target_branch: Target branch
            title: PR title
            description: PR description

        Returns:
            Created PR details or None
        """
        try:
            from azure.devops.v7_1.git.models import GitPullRequest

            pr = GitPullRequest(
                source_ref_name=f"refs/heads/{source_branch}",
                target_ref_name=f"refs/heads/{target_branch}",
                title=title,
                description=description,
            )

            created_pr = self.git_client.create_pull_request(
                git_pull_request_to_create=pr,
                repository_id=repository_id,
                project=settings.ado_project,
            )

            return self.get_pull_request(repository_id, created_pr.pull_request_id)
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return None
