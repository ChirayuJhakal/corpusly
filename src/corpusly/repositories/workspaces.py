from datetime import UTC, datetime
from uuid import uuid4

from corpusly.models.workspace import Workspace


class WorkspaceRepository:
    def __init__(self, store: dict[str, Workspace]) -> None:
        self._store = store

    def create(self, workspace_name: str) -> Workspace:
        now = datetime.now(UTC)
        workspace = Workspace(
            workspace_id=str(uuid4()),
            workspace_name=workspace_name,
            created_at=now,
            updated_at=now,
        )
        self._store[workspace.workspace_id] = workspace
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        workspace = self._store.get(workspace_id)
        return workspace.model_copy() if workspace is not None else None

    def get_by_name(self, workspace_name: str) -> Workspace | None:
        for workspace in self._store.values():
            if workspace.workspace_name == workspace_name:
                return workspace.model_copy()
        return None
