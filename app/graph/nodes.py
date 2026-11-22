
from app.graph.state import ResearchState
from app.vector_store import search_embeddings
from app.llm import generate_answer

from app.validation import (
    has_matching_time_period,
    has_matching_metric,
    has_matching_metric_period,
    requires_metric_amount,
    has_matching_metric_category_amount,
    answer_numbers_match_context,
    answer_metric_numbers_match_context,
    answer_currency_matches_context,
    FALLBACK_ANSWER,
)
from app.agents.research_agent import create_research_plan


def research_node(state: ResearchState) -> dict:
    """
    Analyze the user's financial question and create
    a structured research plan.
    """

    question = state["question"]

    try:
        plan = create_research_plan(question)

        return {
            "research_plan": plan.model_dump(),
            "error": "",
        }

    except Exception as exc:
        return {
            "research_plan": {},
            "error": f"Research planning failed: {exc}",
            "answer": FALLBACK_ANSWER,
            "sources": [],
            "is_sufficient": False,
        }


def retrieve_node(state: ResearchState) -> dict:
    """
    Retrieve relevant financial document chunks from Qdrant
    using the Research Agent's search requirements.
    """

    question = state["question"]
    limit = state.get("limit", 3)

    research_plan = state.get("research_plan", {})

    # Use structured search requirements from Research Agent.
    search_queries = research_plan.get("search_requirements", [])

    # Fall back to the original question if requirements are missing.
    if not search_queries:
        search_queries = [question]

    # Remove empty and duplicate search queries.
    search_queries = list(
        dict.fromkeys(
            query.strip()
            for query in search_queries
            if isinstance(query, str) and query.strip()
        )
    )

    if not search_queries:
        search_queries = [question]

    # Collect results from all search queries.
    unique_results = {}

    for query in search_queries:
        results = search_embeddings(
            query=query,
            limit=limit,
            score_threshold=0.50,
        )

        for result in results:
            # Keep only one copy of each Qdrant chunk.
            result_id = str(result.id)

            existing_result = unique_results.get(result_id)

            if (
                existing_result is None
                or (result.score or 0) > (existing_result.score or 0)
            ):
                unique_results[result_id] = result

    # Rank all retrieved chunks by similarity score.
    ranked_results = sorted(
        unique_results.values(),
        key=lambda result: result.score or 0,
        reverse=True,
    )

    # Keep the highest-scoring chunks.
    ranked_results = ranked_results[:limit]

    retrieved_chunks = []
    context_parts = []
    sources = []

    for result in ranked_results:
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
    question = state["question"]
    context = state.get("context", "")

    if not context.strip():
        return {
            "is_sufficient": False,
            "answer": FALLBACK_ANSWER,
            "sources": [],
        }

    # 1. Check whether the requested reporting period exists.
    time_valid = has_matching_time_period(question, context)

    # 2. Check whether the requested financial metric exists.
    metric_valid = has_matching_metric(question, context)

    # 3. Check whether the metric belongs to the requested period.
    metric_period_valid = has_matching_metric_period(question, context)

    # 4. For amount-specific questions, check category-level evidence.
    category_amount_valid = (
        not requires_metric_amount(question)
        or has_matching_metric_category_amount(question, context)
    )

    is_sufficient = (
        time_valid
        and metric_valid
        and metric_period_valid
        and category_amount_valid
    )

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

        # Check whether the generated answer is supported.
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
