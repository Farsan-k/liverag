from fastapi import FastAPI, HTTPException
from app.schemas import DocumentCreate, DocumentUpdate, SearchRequest, AskRequest
from app.config import settings
from app.crud import delete_document
from app.crud import update_document
from app.crud import get_document
from app.crud import create_document_with_chunks
from app.vector_store import search_embeddings, sync_postgres_chunks_to_qdrant
from app.llm import generate_answer


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
def create_document_api(documents: DocumentCreate):
    result = create_document_with_chunks(
        documents.title,
        documents.source,
        documents.content
    )

    sync_postgres_chunks_to_qdrant()

    return result

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
def document_update_api(
    documents: DocumentUpdate,
    document_id: int
):
    document = get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    document = update_document(
        document_id,
        documents.title,
        documents.source,
        documents.content
    )

    sync_postgres_chunks_to_qdrant()

    return {
        "id": document["id"],
        "title": document["title"],
        "source": document["source"],
        "content": document["content"]
    }

    



@app.delete("/documents/{document_id}", status_code=204)
def document_delete_api(document_id: int):
    document = get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    delete_document(document_id)
    sync_postgres_chunks_to_qdrant()





@app.post("/search")
def search_api(request: SearchRequest):
    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    if not 1 <= request.limit <= 10:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 10"
        )

    results = search_embeddings(
        query=request.query,
        limit=request.limit
    )

    return {
        "query": request.query,
        "results": [
            {
                "chunk_id": result.id,
                "document_id": result.payload.get("document_id"),
                "text": result.payload.get("text", ""),
                "score": result.score
            }
            for result in results
        ]
    }



@app.post("/ask")
def ask_api(request: AskRequest):
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    if not 1 <= request.limit <= 5:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 5"
        )

    results = search_embeddings(
        query=request.question,
        limit=request.limit
    )

    if not results:
        return {
            "question": request.question,
            "answer": "I do not have enough information to answer this question.",
            "sources": []
        }

    context_parts = []
    sources = []

    for result in results:
        payload = result.payload or {}
        text = payload.get("text", "")

        if text:
            context_parts.append(text)

            sources.append({
                "document_id": payload.get("document_id"),
                "chunk_id": result.id,
                "score": result.score,
                "text": text
            })

    context = "\n\n".join(context_parts)

    answer = generate_answer(
        question=request.question,
        context=context
    )

    return {
        "question": request.question,
        "answer": answer,
        "sources": sources
    }

