from pydantic import BaseModel

class Document(BaseModel):
    document_id: str
    document_name: str
    status: str

class DocumentRequest(BaseModel):
    document_name: str

class DocumentsResponse(BaseModel):
    documents: list[Document]

class DocumentResponse(BaseModel):
    document: Document

class DocumentPatch(BaseModel):
    document_name: str
    status: str
