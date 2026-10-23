from uuid import UUID

from fastapi import APIRouter, HTTPException

from corpusly.dependencies import WorkspaceRepo
from corpusly.errors import WorkspaceNameTaken
from corpusly.models.workspace import WorkspaceReponse, WorkspaceRequest

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/{workspace_id}")
def get_workspace(workspace_id: UUID, workspaces: WorkspaceRepo) -> WorkspaceReponse:
    workspace = workspaces.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return WorkspaceReponse(workspace=workspace)


@router.post("/")
def post_workspace(
    workspace: WorkspaceRequest, workspaces: WorkspaceRepo
) -> WorkspaceReponse:
    try:
        created = workspaces.create(workspace.workspace_name)
    except WorkspaceNameTaken:
        raise HTTPException(status_code=409, detail="Workspace already exists") from None
    return WorkspaceReponse(workspace=created)
