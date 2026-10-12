from fastapi import APIRouter, HTTPException, Query

from corpusly.dependencies import DocumentRepo, WorkspaceRepo
from corpusly.models.documents import (
    DocumentPatch,
    DocumentRequest,
    DocumentResponse,
    DocumentsResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])


@router.get("/")
def fetch_documents_from_workspace(
    workspace_id: str,
    workspaces: WorkspaceRepo,
    documents: DocumentRepo,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentsResponse:
    if workspaces.get(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace doesnt exist")
    return DocumentsResponse(
        documents=documents.list_for_workspace(workspace_id, limit, offset)
    )


@router.post("/")
def add_document_into_workspace(
    workspace_id: str,
    document: DocumentRequest,
    workspaces: WorkspaceRepo,
    documents: DocumentRepo,
) -> DocumentResponse:
    if workspaces.get(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace doesnt exist")
    return DocumentResponse(
        document=documents.create(workspace_id, document.document_name)
    )


@router.get("/{document_id}")
def fetch_document(
    workspace_id: str, document_id: str, documents: DocumentRepo
) -> DocumentResponse:
    document = documents.get(workspace_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document doesnt exists")
    return DocumentResponse(document=document)


@router.patch("/{document_id}")
def update_document(
    workspace_id: str,
    document_id: str,
    new_document: DocumentPatch,
    documents: DocumentRepo,
) -> DocumentResponse:
    document = documents.update(
        workspace_id,
        document_id,
        document_name=new_document.document_name,
        document_status=new_document.document_status,
    )
    if document is None:
        raise HTTPException(status_code=404, detail="document doesnt exists")
    return DocumentResponse(document=document)
