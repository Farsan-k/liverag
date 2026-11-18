
from app.graph.state import ResearchState
from app.vector_store import search_embeddings
from app.llm import generate_answer

from app.validation import (
    has_matching_time_period,
    has_matching_metric,
    answer_numbers_match_context,
    answer_metric_numbers_match_context,
    answer_currency_matches_context,
    FALLBACK_ANSWER,
)

def retrieve_node(state: ResearchState) -> dict:
    """
    Retrieve relevant financial document chunks from Qdrant.
    """

    question = state["question"]
    limit = state.get("limit", 3)

    results = search_embeddings(
        query=question,
        limit=limit,
        score_threshold=0.50,
    )

    retrieved_chunks = []
    context_parts = []
    sources = []

    for result in results:
        payload = result.payload or {}
        text = payload.get("text", "")

        if not text:
            continue

        chunk = {
            "chunk_id": result.id,
            "document_id": payload.get("document_id"),
            "chunk_index": payload.get("chunk_index"),
            "text": text,
            "score": result.score,
        }

        retrieved_chunks.append(chunk)
        context_parts.append(text)

        sources.append({
            "document_id": payload.get("document_id"),
            "chunk_id": result.id,
            "score": result.score,
            "text": text,
        })

    context = "\n\n".join(context_parts)

    return {
        "retrieved_chunks": retrieved_chunks,
        "context": context,
        "sources": sources,
        "is_sufficient": False,
        "answer": "",
        "error": "",
    }




def validate_evidence_node(state: ResearchState) -> dict:
    """
    Validate retrieved financial evidence before answer generation.
    """

    question = state["question"]
    context = state["context"]

    if not context.strip():
        return {
            "is_sufficient": False,
            "answer": FALLBACK_ANSWER,
            "sources": [],
        }

    time_valid = has_matching_time_period(
        question,
        context,
    )

    metric_valid = has_matching_metric(
        question,
        context,
    )

    is_sufficient = time_valid and metric_valid

    if not is_sufficient:
        return {
            "is_sufficient": False,
            "answer": FALLBACK_ANSWER,
            "sources": [],
        }

    return {
        "is_sufficient": True,
        "answer": "",
    }



def generate_answer_node(state: ResearchState) -> dict:
    """
    Generate an answer and validate its financial claims.
    """

    question = state["question"]
    context = state["context"]

    try:
        answer = generate_answer(
            question=question,
            context=context,
        )

        # Check whether the generated answer is supported
        numbers_valid = answer_numbers_match_context(
            answer,
            context,
        )

        metrics_valid = answer_metric_numbers_match_context(
            question,
            answer,
            context,
        )

        currency_valid = answer_currency_matches_context(
            answer,
            context,
        )

        if not (
            numbers_valid
            and metrics_valid
            and currency_valid
        ):
            return {
                "answer": FALLBACK_ANSWER,
                "sources": [],
                "error": "Generated answer failed evidence validation.",
            }

        if answer == FALLBACK_ANSWER:
            return {
                "answer": FALLBACK_ANSWER,
                "sources": [],
                "error": "",
            }

        return {
            "answer": answer,
            "error": "",
        }

    except Exception as exc:
        return {
            "answer": FALLBACK_ANSWER,
            "sources": [],
            "error": f"Answer generation failed: {exc}",
        }
