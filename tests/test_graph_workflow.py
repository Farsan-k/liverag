
from types import SimpleNamespace
from unittest.mock import call, patch

from app.agents.research_agent import ResearchPlan
from app.graph.nodes import retrieve_node, validate_evidence_node
from app.graph.workflow import research_graph
from app.validation import FALLBACK_ANSWER


def make_result(
    text,
    chunk_id=101,
    score=0.85,
    document_id=55,
    chunk_index=0,
):
    """Create a mock Qdrant search result."""
    return SimpleNamespace(
        id=chunk_id,
        score=score,
        payload={
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": text,
        },
    )


def mock_research_plan(question):
    """Return a predictable research plan for graph tests."""
    return ResearchPlan(
        company="Test Company",
        metrics=["Revenue"],
        periods=["FY2025"],
        analysis_type="general_analysis",
        requires_calculation=False,
        search_requirements=[
            "Test Company FY2025 Revenue",
        ],
    )


# ---------------------------------------------------------
# GRAPH WORKFLOW TESTS
# ---------------------------------------------------------

def test_graph_rejects_wrong_fiscal_year():
    evidence = "Revenue was 500000 rupees in FY2025."

    with (
        patch(
            "app.graph.nodes.create_research_plan",
            side_effect=mock_research_plan,
        ),
        patch(
            "app.graph.nodes.search_embeddings",
            return_value=[make_result(evidence)],
        ),
        patch("app.graph.nodes.generate_answer") as mock_generate,
    ):
        result = research_graph.invoke({
            "question": "What was revenue in FY2099?",
            "limit": 3,
        })

    assert result["is_sufficient"] is False
    assert result["answer"] == FALLBACK_ANSWER
    assert result["sources"] == []

    mock_generate.assert_not_called()


def test_graph_generates_answer_for_matching_evidence():
    evidence = "Revenue was 500000 rupees in FY2025."
    expected_answer = "Revenue was 500000 rupees in FY2025."

    with (
        patch(
            "app.graph.nodes.create_research_plan",
            side_effect=mock_research_plan,
        ),
        patch(
            "app.graph.nodes.search_embeddings",
            return_value=[make_result(evidence)],
        ),
        patch(
            "app.graph.nodes.generate_answer",
            return_value=expected_answer,
        ) as mock_generate,
    ):
        result = research_graph.invoke({
            "question": "What was revenue in FY2025?",
            "limit": 3,
        })

    assert result["is_sufficient"] is True
    assert result["answer"] == expected_answer
    assert len(result["sources"]) == 1

    mock_generate.assert_called_once()


def test_graph_stops_when_research_planning_fails():
    with patch(
        "app.graph.nodes.create_research_plan",
        side_effect=RuntimeError("Ollama unavailable"),
    ):
        result = research_graph.invoke({
            "question": "What was Apple's revenue?",
            "limit": 3,
        })

    assert result["answer"] == FALLBACK_ANSWER
    assert result["sources"] == []
    assert "Research planning failed" in result["error"]


# ---------------------------------------------------------
# RETRIEVAL AGENT TESTS
# ---------------------------------------------------------

def test_retrieval_uses_research_search_requirements():
    search_requirements = [
        "Apple FY2024 Revenue",
        "Apple FY2025 Revenue",
    ]

    state = {
        "question": "Compare Apple's revenue.",
        "limit": 3,
        "research_plan": {
            "search_requirements": search_requirements,
        },
    }

    with patch(
        "app.graph.nodes.search_embeddings",
        return_value=[],
    ) as mock_search:

        result = retrieve_node(state)

    assert mock_search.call_count == 2

    assert mock_search.call_args_list == [
        call(
            query="Apple FY2024 Revenue",
            limit=3,
            score_threshold=0.50,
        ),
        call(
            query="Apple FY2025 Revenue",
            limit=3,
            score_threshold=0.50,
        ),
    ]

    assert result["retrieved_chunks"] == []
    assert result["context"] == ""
    assert result["sources"] == []


def test_retrieval_removes_duplicate_chunks():
    state = {
        "question": "Compare Apple's revenue.",
        "limit": 3,
        "research_plan": {
            "search_requirements": [
                "Apple FY2024 Revenue",
                "Apple FY2025 Revenue",
            ],
        },
    }

    first_result = make_result(
        text="Apple revenue was 100 billion USD.",
        chunk_id=101,
        score=0.75,
    )

    better_result = make_result(
        text="Apple revenue was 100 billion USD.",
        chunk_id=101,
        score=0.95,
    )

    second_chunk = make_result(
        text="Apple revenue was 120 billion USD.",
        chunk_id=102,
        score=0.85,
        chunk_index=1,
    )

    with patch(
        "app.graph.nodes.search_embeddings",
        side_effect=[
            [first_result, second_chunk],
            [better_result],
        ],
    ):

        result = retrieve_node(state)

    assert len(result["retrieved_chunks"]) == 2

    retrieved_ids = [
        chunk["chunk_id"]
        for chunk in result["retrieved_chunks"]
    ]

    assert retrieved_ids == [101, 102]

    # The duplicate must retain its highest score.
    assert result["retrieved_chunks"][0]["score"] == 0.95


def test_retrieval_falls_back_to_original_question():
    question = "What was Apple's revenue?"

    state = {
        "question": question,
        "limit": 3,
        "research_plan": {
            "search_requirements": [],
        },
    }

    with patch(
        "app.graph.nodes.search_embeddings",
        return_value=[],
    ) as mock_search:

        retrieve_node(state)

    mock_search.assert_called_once_with(
        query=question,
        limit=3,
        score_threshold=0.50,
    )


def test_retrieval_falls_back_when_research_plan_is_missing():
    question = "What was Microsoft's revenue?"

    state = {
        "question": question,
        "limit": 3,
    }

    with patch(
        "app.graph.nodes.search_embeddings",
        return_value=[],
    ) as mock_search:

        retrieve_node(state)

    mock_search.assert_called_once_with(
        query=question,
        limit=3,
        score_threshold=0.50,
    )


def test_retrieval_respects_limit_after_merging_results():
    state = {
        "question": "Compare Apple's revenue.",
        "limit": 2,
        "research_plan": {
            "search_requirements": [
                "Apple FY2024 Revenue",
                "Apple FY2025 Revenue",
            ],
        },
    }

    first_results = [
        make_result("Revenue was 100 billion.", chunk_id=101, score=0.70),
        make_result("Revenue was 110 billion.", chunk_id=102, score=0.90),
    ]

    second_results = [
        make_result("Revenue was 120 billion.", chunk_id=103, score=0.95),
        make_result("Revenue was 130 billion.", chunk_id=104, score=0.80),
    ]

    with patch(
        "app.graph.nodes.search_embeddings",
        side_effect=[
            first_results,
            second_results,
        ],
    ):

        result = retrieve_node(state)

    assert len(result["retrieved_chunks"]) == 2

    retrieved_ids = [
        chunk["chunk_id"]
        for chunk in result["retrieved_chunks"]
    ]

    # Only the two highest-scoring chunks should remain.
    assert retrieved_ids == [103, 102]

    assert result["retrieved_chunks"][0]["score"] == 0.95
    assert result["retrieved_chunks"][1]["score"] == 0.90




def test_validate_evidence_rejects_metric_from_wrong_period():
    state = {
        "question": "What was the net income in FY2025?",
        "context": (
            "Revenue was $500 billion in FY2025. "
            "Net income was $100 billion in FY2024."
        ),
        "sources": [],
    }

    result = validate_evidence_node(state)

    assert result["is_sufficient"] is False


def test_validate_evidence_rejects_missing_category_amount():
    state = {
        "question": "What was Apple's iPhone revenue amount?",
        "context": (
            "Apple revenue was $100 billion in FY2025. "
            "iPhone sales contributed to the company's growth."
        ),
        "sources": [],
    }

    result = validate_evidence_node(state)

    assert result["is_sufficient"] is False