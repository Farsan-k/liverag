from fastapi import FastAPI, HTTPException
from app.schemas import DocumentCreate, DocumentUpdate, SearchRequest, AskRequest
from app.config import settings
from app.crud import delete_document
from app.crud import update_document
from app.crud import get_document
from app.crud import create_document_with_chunks
from app.crud import get_all_documents
from app.vector_store import search_embeddings, sync_postgres_chunks_to_qdrant
from app.llm import generate_answer
import re
from datetime import date
from decimal import Decimal, InvalidOperation


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

    question_years = set(
        re.findall(r"\b(?:19|20)\d{2}\b", question_lower)
    )
    context_years = set(
        re.findall(r"\b(?:19|20)\d{2}\b", context_lower)
    )

    if question_years and not question_years.issubset(context_years):
        return False

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

    requested_metrics = [
        (metric, keywords)
        for metric, keywords in metric_keywords.items()
        if re.search(rf"\b{re.escape(metric)}\b", question_lower)
    ]

    if not requested_metrics:
        return True

    for metric, keywords in requested_metrics:
        if not any(
            re.search(rf"\b{re.escape(keyword)}\b", context_lower)
            for keyword in keywords
        ):
            return False

    return True


FINANCIAL_SCALES = {
    "thousand": Decimal("1000"),
    "thousands": Decimal("1000"),
    "lakh": Decimal("100000"),
    "lakhs": Decimal("100000"),
    "lac": Decimal("100000"),
    "lacs": Decimal("100000"),
    "crore": Decimal("10000000"),
    "crores": Decimal("10000000"),
    "million": Decimal("1000000"),
    "millions": Decimal("1000000"),
    "billion": Decimal("1000000000"),
    "billions": Decimal("1000000000"),
}


def normalize_financial_number(
    number: str,
    scale: str | None = None,
    is_percentage: bool = False,
) -> str:
    """Normalize financial amounts to a comparable numeric value."""

    value = Decimal(number.replace(",", ""))

    if scale:
        value *= FINANCIAL_SCALES[scale.lower()]

    normalized = format(value.normalize(), "f")

    return f"{normalized}%" if is_percentage else normalized


def extract_normalized_numbers(
    text: str,
    exclude_years: bool = False,
) -> set[str]:
    """Extract normalized numbers, including financial unit conversions."""

    pattern = re.compile(
        r"(?<![\w.])"
        r"(?P<number>[+-]?\d[\d,]*(?:\.\d+)?)"
        r"(?:\s*(?P<scale>thousands?|lakhs?|lacs?|crores?|millions?|billions?))?"
        r"(?:\s*(?P<percentage>%|percent(?:age)?))?"
        r"(?!\w)",
        re.IGNORECASE,
    )

    numbers = set()

    for match in pattern.finditer(text):
        number = match.group("number")
        scale = match.group("scale")
        percentage = match.group("percentage")

        if exclude_years and not scale and re.fullmatch(
            r"(?:19|20)\d{2}", number
        ):
            continue

        try:
            numbers.add(
                normalize_financial_number(
                    number,
                    scale,
                    bool(percentage),
                )
            )
        except (InvalidOperation, ValueError):
            continue

    return numbers


def answer_numbers_match_context(answer: str, context: str) -> bool:
    """Reject numeric values that are not supported by the evidence."""

    answer_numbers = extract_normalized_numbers(answer)
    context_numbers = extract_normalized_numbers(context)

    return answer_numbers.issubset(context_numbers)


def answer_metric_numbers_match_context(
    question: str,
    answer: str,
    context: str,
) -> bool:
    """Verify numeric answers for every requested financial metric."""

    metric_keywords = {
        "revenue": ("sales", "turnover"),
        "net profit": ("net income",),
        "gross profit": (),
        "operating profit": (),
        "cash flow": (),
        "expenses": ("expenditure", "costs"),
        "assets": (),
        "liabilities": (),
        "debt": (),
    }

    question_lower = question.lower()

    requested_metrics = [
        metric
        for metric, aliases in metric_keywords.items()
        if any(
            re.search(rf"\b{re.escape(alias)}\b", question_lower)
            for alias in (metric, *aliases)
        )
    ]

    if not requested_metrics:
        return True

    def metric_numbers(
        text: str,
        aliases: tuple[str, ...],
    ) -> set[str]:
        numbers = set()

        for sentence in re.split(r"(?<=[.!?])\s+", text):
            clauses = re.split(
                r"\s+(?:and|while|whereas|but)\s+",
                sentence,
                flags=re.IGNORECASE,
            )

            for clause in clauses:
                clause_lower = clause.lower()

                if any(
                    re.search(
                        rf"\b{re.escape(alias)}\b",
                        clause_lower,
                    )
                    for alias in aliases
                ):
                    numbers.update(
                        extract_normalized_numbers(
                            clause,
                            exclude_years=True,
                        )
                    )

        return numbers

    for metric in requested_metrics:
        aliases = (metric, *metric_keywords[metric])

        answer_numbers = metric_numbers(answer, aliases)
        evidence_numbers = metric_numbers(context, aliases)

        if not answer_numbers:
            continue

        if not answer_numbers.issubset(evidence_numbers):
            return False

    return True


def answer_currency_matches_context(
    answer: str,
    context: str,
) -> bool:
    """Ensure currency and normalized amounts match the evidence."""

    number_pattern = r"[+-]?\d[\d,]*(?:\.\d+)?"

    currency_pattern = re.compile(
        rf"(?:(?P<prefix>₹|(?<!\w)INR\b|(?<!\w)USD\b|"
        rf"(?<!\w)US\s+dollars?\b|(?<!\w)Rs\.?|(?<!\w)\$)\s*)?"
        rf"(?P<number>{number_pattern})"
        rf"(?:\s*(?P<scale>thousands?|lakhs?|lacs?|crores?|millions?|billions?))?"
        rf"(?:\s*(?P<suffix>rupees?\b|INR\b|USD\b|"
        rf"US\s+dollars?\b|dollars?\b))?",
        re.IGNORECASE,
    )

    def extract_currency_claims(
        text: str,
    ) -> set[tuple[str, str]]:
        claims = set()

        for match in currency_pattern.finditer(text):
            prefix = match.group("prefix")
            suffix = match.group("suffix")

            if not prefix and not suffix:
                continue

            marker = (prefix or suffix).lower()

            if marker in {"₹", "inr", "rs", "rs.", "rupee", "rupees"}:
                currency = "INR"
            elif marker in {
                "$", "usd", "us dollar", "us dollars",
                "dollar", "dollars",
            }:
                currency = "USD"
            else:
                continue

            try:
                amount = normalize_financial_number(
                    match.group("number"),
                    match.group("scale"),
                )
            except (InvalidOperation, ValueError):
                continue

            claims.add((amount, currency))

        return claims

    answer_claims = extract_currency_claims(answer)
    context_claims = extract_currency_claims(context)

    return answer_claims.issubset(context_claims)


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

@app.get("/documents")
def get_all_documents_api():
    return get_all_documents()

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
            detail="Question cannot be empty",
        )

    if not 1 <= request.limit <= 5:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 5",
        )

    # Step 1: Retrieve relevant chunks
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

    # Step 2: Build context and source information
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

    # Step 3: Validate retrieved evidence
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

    # Step 4: Generate answer using LLM
    answer = generate_answer(
        question=request.question,
        context=context,
    )

    # Step 5: Validate generated answer
    if (
        not answer_numbers_match_context(answer, context)
        or not answer_metric_numbers_match_context(
            request.question,
            answer,
            context,
        )
        or not answer_currency_matches_context(
            answer,
            context,
        )
    ):
        return {
            "question": request.question,
            "answer": FALLBACK_ANSWER,
            "sources": [],
        }

    # Step 6: Return validated answer
    return {
        "question": request.question,
        "answer": answer,
        "sources": sources,
    }