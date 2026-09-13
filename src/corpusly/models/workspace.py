from datetime import datetime

from pydantic import BaseModel


class Workspace(BaseModel):
    """A stored workspace. Every field is required: if the repository ever hands
    up an object missing one, construction fails loudly instead of inventing it."""

    workspace_id: str
    workspace_name: str
    created_at: datetime
    updated_at: datetime


class WorkspaceRequest(BaseModel):
    workspace_name: str


class WorkspaceReponse(BaseModel):
    workspace: Workspace
