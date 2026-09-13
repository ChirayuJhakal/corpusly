from pydantic import BaseModel, Field
from datetime import datetime, timezone

class Workspace(BaseModel):
    workspace_id: str
    workspace_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WorkspaceRequest(BaseModel):
    workspace_name: str

class WorkspaceReponse(BaseModel):
    workspace: Workspace
