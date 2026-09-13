from typing import Annotated

from fastapi import Depends

from corpusly.models.documents import Document
from corpusly.models.workspace import Workspace
from corpusly.repositories.documents import DocumentRepository
from corpusly.repositories.workspaces import WorkspaceRepository

# The composition root. These two dicts are the only storage in the system, and
# they are the only thing here that the Postgres stage deletes: the providers
# below become generators that yield a per-request Session.
_workspace_store: dict[str, Workspace] = {}
_document_store: dict[str, Document] = {}


def get_workspace_repository() -> WorkspaceRepository:
    return WorkspaceRepository(_workspace_store)


def get_document_repository() -> DocumentRepository:
    return DocumentRepository(_document_store)


WorkspaceRepo = Annotated[WorkspaceRepository, Depends(get_workspace_repository)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repository)]
