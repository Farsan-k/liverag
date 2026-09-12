from fastapi import FastAPI
from app.schemas import DocumentCreate
from app.config import settings
from app.crud import create_document


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
