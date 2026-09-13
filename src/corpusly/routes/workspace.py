from fastapi import APIRouter, HTTPException

from corpusly.dependencies import WorkspaceRepo
from corpusly.models.workspace import WorkspaceReponse, WorkspaceRequest

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, workspaces: WorkspaceRepo) -> WorkspaceReponse:
    workspace = workspaces.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return WorkspaceReponse(workspace=workspace)


@router.post("/")
def post_workspace(
    workspace: WorkspaceRequest, workspaces: WorkspaceRepo
) -> WorkspaceReponse:
    if workspaces.get_by_name(workspace.workspace_name) is not None:
        raise HTTPException(status_code=409, detail="Workspace already exists")
    return WorkspaceReponse(workspace=workspaces.create(workspace.workspace_name))
