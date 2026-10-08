from fastapi import FastAPI, HTTPException
from app.schemas import DocumentCreate, DocumentUpdate
from app.config import settings
from app.crud import create_document
from app.crud import delete_document
from app.crud import update_document
from app.crud import get_document


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
              )


@app.get("/")
def root():
    return {
        "message": "LiveRAG API is running",
        "environment": settings.environment, 
        }

@app.post("/documents")
def create_document_api(documents : DocumentCreate):

    document = create_document(
        documents.title,
        documents.source,
        documents.content
        )

    return {
        "id" : document.id,
        "title" : documents.title,
        "source" : documents.source,
        "content" : documents.content
    }

@app.get("/documents/{document_id}")
def get_document_api(document_id:int):
    document = get_document(document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id" : document.id,
        "title" : document.title,
        "source" : document.source,
        "content" : document.content
    }



@app.put("/documents/{document_id}")
def document_update_api(documents : DocumentUpdate, document_id:int):

    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    document = update_document(
        document_id,
        documents.title,
        documents.source,
        documents.content
    )

    return {
        "id" : document.id,
        "title" : document.title,
        "source" : document.source,
        "content" : document.content
    }





@app.delete("/documents/{document_id}", status_code=204)
def document_delete_api(document_id:int):

    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    delete_document(document_id)

    
