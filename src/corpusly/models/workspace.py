from pydantic import BaseModel

class Workspace(BaseModel):
    workspace_id: str
    workspace_name: str

class WorkspaceRequest(BaseModel):
    workspace_name: str

class WorkspaceReponse(BaseModel):
    workspace: Workspace