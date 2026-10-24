from fastapi import FastAPI, HTTPException
from app.schemas import DocumentCreate, DocumentUpdate, SearchRequest, AskRequest
from app.config import settings
from app.crud import delete_document
from app.crud import update_document
from app.crud import get_document
from app.crud import create_document_with_chunks
from app.vector_store import search_embeddings, sync_postgres_chunks_to_qdrant
from app.llm import generate_answer
import re
from datetime import date


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
              )


FALLBACK_ANSWER = (
    "I do not have enough information to answer this question."
)

MONTH_NAMES = (
    "january", "february", "march", "april",
    "may", "june", "july", "august",
    "september", "october", "november", "december",
)


def has_matching_time_period(question: str, context: str) -> bool:
    question_lower = question.lower()
    context_lower = context.lower()

    # Check explicitly requested years.
    question_years = set(
        re.findall(r"\b(?:19|20)\d{2}\b", question_lower)
    )
    context_years = set(
        re.findall(r"\b(?:19|20)\d{2}\b", context_lower)
    )

    if question_years and not question_years.issubset(context_years):
        return False

    # Check explicitly requested month names.
    requested_months = {
        month for month in MONTH_NAMES
        if re.search(rf"\b{month}\b", question_lower)
    }
    available_months = {
        month for month in MONTH_NAMES
        if re.search(rf"\b{month}\b", context_lower)
    }

    if requested_months and not requested_months.issubset(available_months):
        return False

    return True

def has_matching_metric(question: str, context: str) -> bool:
    question_lower = question.lower()
    context_lower = context.lower()

    metric_keywords = {
        "revenue": ("revenue", "sales", "turnover"),
        "net profit": ("net profit", "net income"),
        "gross profit": ("gross profit",),
        "operating profit": ("operating profit",),
        "profit": ("profit", "earnings"),
        "expenses": ("expenses", "expenditure", "costs"),
        "cash flow": ("cash flow",),
        "assets": ("assets",),
        "liabilities": ("liabilities",),
        "debt": ("debt",),
    }

    # Find the metric explicitly mentioned in the question.
    requested_metrics = [
        (metric, keywords)
        for metric, keywords in metric_keywords.items()
        if re.search(rf"\b{re.escape(metric)}\b", question_lower)
    ]

    # If no recognized metric is requested, do not block the question
    # based on this limited keyword list.
    if not requested_metrics:
        return True

    for metric, keywords in requested_metrics:
        # Require evidence for the requested metric itself.
        if not any(
            re.search(rf"\b{re.escape(keyword)}\b", context_lower)
            for keyword in keywords
        ):
            return False

    return True

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
        limit=request.limit,
        score_threshold=0.60,
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
        limit=request.limit,
        score_threshold=0.50,
    )

    if not results:
        return {
            "question": request.question,
            "answer": FALLBACK_ANSWER,
            "sources": [],
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
                "text": text,
            })

    context = "\n\n".join(context_parts)

    # Reject empty evidence, mismatched periods, or mismatched metrics.
    if (
        not context.strip()
        or not has_matching_time_period(
            request.question,
            context,
        )
        or not has_matching_metric(
            request.question,
            context,
        )
    ):
        return {
            "question": request.question,
            "answer": FALLBACK_ANSWER,
            "sources": [],
        }

    answer = generate_answer(
        question=request.question,
        context=context,
    )

    return {
        "question": request.question,
        "answer": answer,
        "sources": sources,
    }

