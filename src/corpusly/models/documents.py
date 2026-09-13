from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum

class Status(Enum):
    PENDING = 1
    IN_PROGRESS = 2
    DONE = 3

class Document(BaseModel):
    document_id: str
    document_name: str
    workspace_id: str
    status: Status
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DocumentRequest(BaseModel):
    document_name: str

class DocumentsResponse(BaseModel):
    documents: list[Document]

class DocumentResponse(BaseModel):
    document: Document

class DocumentPatch(BaseModel):
    document_name: str
    status: Status
