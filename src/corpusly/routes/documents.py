from fastapi import APIRouter, HTTPException
from corpusly.repositories.documents import documents
from corpusly.models.documents import DocumentResponse, DocumentPatch

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get('/{document_id}', response_model=DocumentResponse)
def fetch_document(document_id: int):
    if document_id not in documents:
        raise HTTPException(status_code=404, detail='Document doesnt exists')
    return { 'document': documents[document_id] }

@router.patch('/{document_id}', response_model=DocumentResponse)
def update_document(document_id: int, new_document: DocumentPatch):
    if document_id not in documents:
        raise HTTPException(status_code=404, detail='document doesnt exists')
    documents[document_id]['document_name'] = new_document.document_name
    documents[document_id]['status'] = new_document.status
    return { 'document': documents[document_id] }
