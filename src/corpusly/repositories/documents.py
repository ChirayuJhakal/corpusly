from datetime import UTC, datetime
from uuid import uuid4

from corpusly.models.documents import Document


class DocumentRepository:
    def __init__(self, store: dict[str, Document]) -> None:
        self._store = store

    def create(self, workspace_id: str, document_name: str) -> Document:
        now = datetime.now(UTC)
        document = Document(
            document_id=str(uuid4()),
            workspace_id=workspace_id,
            document_name=document_name,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self._store[document.document_id] = document
        return document

    def get(self, workspace_id: str, document_id: str) -> Document | None:
        document = self._store.get(document_id)
        # A document owned by another workspace is indistinguishable from one
        # that does not exist. The caller turns None into a 404, never a 403.
        if document is None or document.workspace_id != workspace_id:
            return None
        return document.model_copy()

    def list_for_workspace(
        self, workspace_id: str, limit: int, offset: int
    ) -> list[Document]:
        matches = [
            document
            for document in self._store.values()
            if document.workspace_id == workspace_id
        ]
        # Pagination without a deterministic sort returns arbitrary pages.
        matches.sort(key=lambda document: (document.created_at, document.document_id))
        return [document.model_copy() for document in matches[offset : offset + limit]]

    def update(
        self,
        workspace_id: str,
        document_id: str,
        *,
        document_name: str | None = None,
        status: str | None = None,
    ) -> Document | None:
        existing = self._store.get(document_id)
        if existing is None or existing.workspace_id != workspace_id:
            return None

        # updated_at is owned by this layer. Callers never supply it.
        changes: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if document_name is not None:
            changes["document_name"] = document_name
        if status is not None:
            changes["status"] = status

        # Note: model_copy(update=...) does not re-validate. That matters the day
        # status becomes an enum.
        updated = existing.model_copy(update=changes)
        self._store[document_id] = updated
        return updated
