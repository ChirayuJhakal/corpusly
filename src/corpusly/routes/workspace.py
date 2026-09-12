from fastapi import APIRouter, HTTPException
from corpusly.repositories.workspaces import workspaces
from corpusly.repositories.documents import workspaces_and_documents, documents
from corpusly.models.workspace import WorkspaceRequest, WorkspaceReponse
from corpusly.models.documents import DocumentsResponse, DocumentRequest, DocumentResponse, DocumentPatch
import uuid

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.get('/{workspace_id}', response_model=WorkspaceReponse)
def get_workspace(workspace_id: str):
    if workspace_id in workspaces:
        return { 'workspace': workspaces[workspace_id] }
    else :
        raise HTTPException(status_code=404, detail='workspace not found')

@router.post('/')
def post_workspace(workspace: WorkspaceRequest):
    for _, value in workspaces.items():
        if value['workspace_name'] == workspace.workspace_name:
            raise HTTPException(status_code=409, detail='Workspace already exists')
    workspace_id = str(uuid.uuid4())
    workspaces[workspace_id] = { "workspace_id": workspace_id, "workspace_name": workspace.workspace_name }
    workspaces_and_documents[workspace_id] = []
    return { 'workspace': workspaces[workspace_id] }

@router.get('/{workspace_id}/documents', response_model=DocumentsResponse)
def fetch_document_from_workspace(workspace_id: int):
    if workspace_id not in workspaces:
        raise HTTPException(status_code=404, detail='workspace doesnt exist')
    documents_for_workspace = []
    for doc in workspaces_and_documents[workspace_id]:
        documents_for_workspace.push(documents.get(doc))
    return { 'documents': documents_for_workspace }

@router.post('/{workspace_id}/documents')
def add_document_into_workspace(workspace_id: int, document: DocumentRequest):
    if workspace_id not in workspaces:
        raise HTTPException(status_code=404, detail='workspace doesnt exist')
    document_id = str(uuid.uuid4())
    workspaces_and_documents[workspace_id].push(document_id)
    documents[document_id] = { 'document_id': document_id, 'document_name': document.document_name, 'status': 'recieved' }
    return { 'message': 'document added', 'document': documents[document_id] }