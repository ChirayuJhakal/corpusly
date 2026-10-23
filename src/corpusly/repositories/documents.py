from typing import Any
from uuid import UUID

from psycopg import Connection

from corpusly.models.documents import Document


def _to_document(row: dict[str, Any]) -> Document:
    # psycopg returns uuid columns as uuid.UUID; the model (and the API) use str.
    # The column is document_status; every query aliases it back to the API's `status`.
    return Document(
        document_id=str(row["document_id"]),
        workspace_id=str(row["workspace_id"]),
        document_name=row["document_name"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class DocumentRepository:
    # conn comes from the pool, which sets row_factory=dict_row, so rows are dicts.
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def create(self, workspace_id: UUID, document_name: str) -> Document:
        row = self.conn.execute(
            "INSERT INTO documents (workspace_id, document_name) VALUES (%s, %s) "
            "RETURNING document_id, workspace_id, document_name, "
            "document_status AS status, created_at, updated_at;",
            (workspace_id, document_name),
        ).fetchone()
        return _to_document(row)

    def get(self, workspace_id: UUID, document_id: UUID) -> Document | None:
        # Tenant scoping is in the WHERE clause: another workspace's document is
        # simply not found, so the route returns 404.
        row = self.conn.execute(
            "SELECT document_id, workspace_id, document_name, "
            "document_status AS status, created_at, updated_at "
            "FROM documents WHERE workspace_id = %s AND document_id = %s;",
            (workspace_id, document_id),
        ).fetchone()
        return _to_document(row) if row is not None else None

    def list_for_workspace(
        self, workspace_id: UUID, limit: int, offset: int
    ) -> list[Document]:
        # document_id breaks ties: rows inserted in one transaction share created_at,
        # and without a total order LIMIT/OFFSET pages can skip or repeat rows.
        rows = self.conn.execute(
            "SELECT document_id, workspace_id, document_name, "
            "document_status AS status, created_at, updated_at "
            "FROM documents WHERE workspace_id = %s "
            "ORDER BY created_at, document_id LIMIT %s OFFSET %s;",
            (workspace_id, limit, offset),
        ).fetchall()
        return [_to_document(row) for row in rows]

    def update(
        self,
        workspace_id: UUID,
        document_id: UUID,
        *,
        document_name: str | None = None,
        status: str | None = None,
    ) -> Document | None:
        # One statement for a partial update: COALESCE keeps the current value when
        # the field was not sent (None). No row matched -> wrong id or other tenant.
        row = self.conn.execute(
            "UPDATE documents SET "
            "document_name = COALESCE(%s, document_name), "
            "document_status = COALESCE(%s::document_status_enum, document_status), "
            "updated_at = now() "
            "WHERE workspace_id = %s AND document_id = %s "
            "RETURNING document_id, workspace_id, document_name, "
            "document_status AS status, created_at, updated_at;",
            (document_name, status, workspace_id, document_id),
        ).fetchone()
        return _to_document(row) if row is not None else None
