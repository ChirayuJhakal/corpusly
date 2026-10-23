from typing import Any
from uuid import UUID

from psycopg import Connection, errors

from corpusly.errors import WorkspaceNameTaken
from corpusly.models.workspace import Workspace


def _to_workspace(row: dict[str, Any]) -> Workspace:
    # psycopg returns uuid columns as uuid.UUID; the model (and the API) use str.
    return Workspace(
        workspace_id=str(row["workspace_id"]),
        workspace_name=row["workspace_name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class WorkspaceRepository:
    # conn comes from the pool, which sets row_factory=dict_row, so rows are dicts.
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def create(self, workspace_name: str) -> Workspace:
        try:
            row = self.conn.execute(
                "INSERT INTO workspaces (workspace_name) VALUES (%s) "
                "RETURNING workspace_id, workspace_name, created_at, updated_at;",
                (workspace_name,),
            ).fetchone()
        except errors.UniqueViolation as exc:
            raise WorkspaceNameTaken(workspace_name) from exc
        return _to_workspace(row)

    def get(self, workspace_id: UUID) -> Workspace | None:
        row = self.conn.execute(
            "SELECT workspace_id, workspace_name, created_at, updated_at "
            "FROM workspaces WHERE workspace_id = %s;",
            (workspace_id,),
        ).fetchone()
        return _to_workspace(row) if row is not None else None

    def get_by_name(self, workspace_name: str) -> Workspace | None:
        row = self.conn.execute(
            "SELECT workspace_id, workspace_name, created_at, updated_at "
            "FROM workspaces WHERE workspace_name = %s;",
            (workspace_name,),
        ).fetchone()
        return _to_workspace(row) if row is not None else None
