from types import SimpleNamespace
from unittest.mock import patch

from app.graph.workflow import research_graph
from app.validation import FALLBACK_ANSWER


def make_result(text):
    return SimpleNamespace(
        id=101,
        score=0.85,
        payload={
            "document_id": 55,
            "chunk_index": 0,
            "text": text,
        },
    )


def test_graph_rejects_wrong_fiscal_year():
    evidence = "Revenue was 500000 rupees in FY2025."

    with (
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