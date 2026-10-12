from datetime import datetime

from pydantic import BaseModel


class Document(BaseModel):
    document_id: str
    workspace_id: str
    document_name: str
    document_status: str
    created_at: datetime
    updated_at: datetime


class DocumentRequest(BaseModel):
    document_name: str


class DocumentPatch(BaseModel):
    document_name: str | None = None
    document_status: str | None = None


class DocumentsResponse(BaseModel):
    documents: list[Document]


class DocumentResponse(BaseModel):
    document: Document
