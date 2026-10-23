from datetime import datetime

from pydantic import BaseModel
from typing import Literal


class Document(BaseModel):
    document_id: str
    workspace_id: str
    document_name: str
    status: Literal["pending", "processing", "ready", "failed"] 
    created_at: datetime
    updated_at: datetime


class DocumentRequest(BaseModel):
    document_name: str


class DocumentPatch(BaseModel):
    document_name: str | None = None
    status: Literal["pending", "processing", "ready", "failed"] | None = None


class DocumentsResponse(BaseModel):
    documents: list[Document]


class DocumentResponse(BaseModel):
    document: Document
