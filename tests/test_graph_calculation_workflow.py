
from unittest.mock import patch
from app.agents.research_agent import ResearchPlan
from app.graph.workflow import research_graph
from app.validation import FALLBACK_ANSWER


def mock_plan(question):
    return ResearchPlan(
        company="Apple Inc.",
        metrics=["Revenue", "Net Income", "Net Profit Margin"],
        periods=["FY2026"],
        analysis_type="ratio_analysis",
        requires_calculation=True,
        search_requirements=["Apple FY2026 Revenue"],
    )

def mock_analysis(plan):
    return {
        "summary": "Net Profit Margin calculated successfully.",
        "calculations": [
            {
                "metric": "Net Profit Margin",
                "status": "calculated",
                "value": "27.6035",
                "unit": "%",
                "formula": "(Net Income / Revenue) × 100",
                "inputs": [],
                "errors": [],
            }
        ],
        "limitations": [],
    }


def test_calculation_path_runs_analysis_and_verification():
    verification = {
        "verified": True,
        "errors": [],
        "calculations": [
            {
                "metric": "Net Profit Margin",
                "verified": True,
                "errors": [],
            }
        ],
    }

    with (
        patch(
            "app.graph.nodes.create_research_plan",
            side_effect=mock_plan,
        ),
        patch(
            "app.graph.nodes.search_embeddings",
            return_value=[],
        ),
        patch(
            "app.graph.nodes.analyze_research_plan",
            side_effect=mock_analysis,
        ) as mock_analysis_node,
        patch(
            "app.graph.nodes.verify_analysis",
            return_value=verification,
        ) as mock_verification,
        patch(
            "app.graph.nodes.generate_answer",
        ) as mock_llm,
    ):
        result = research_graph.invoke({
            "question": "Calculate Apple's FY2026 net profit margin.",
            "limit": 3,
        })

    mock_analysis_node.assert_called_once()
    mock_verification.assert_called_once()
    mock_llm.assert_not_called()

    assert result["verification_result"] is True
    assert "27.6035%" in result["answer"]
    assert "independently verified" in result["answer"]


def test_calculation_path_rejects_failed_verification():
    verification = {
        "verified": False,
        "errors": [
            "Reported calculation does not match the verified result."
        ],
        "calculations": [],
    }

    with (
        patch(
            "app.graph.nodes.create_research_plan",
            side_effect=mock_plan,
        ),
        patch(
            "app.graph.nodes.search_embeddings",
            return_value=[],
        ),
        patch(
            "app.graph.nodes.analyze_research_plan",
            side_effect=mock_analysis,
        ),
        patch(
            "app.graph.nodes.verify_analysis",
            return_value=verification,
        ),
    ):
        result = research_graph.invoke({
            "question": "Calculate Apple's FY2026 net profit margin.",
            "limit": 3,
        })

    assert result["verification_result"] is False
    assert "couldn't provide a verified" in result["answer"]
    assert "27.6035%" not in result["answer"]


def test_calculation_path_does_not_require_qdrant_context():
    verification = {
        "verified": True,
        "errors": [],
        "calculations": [
            {
                "metric": "Net Profit Margin",
                "verified": True,
                "errors": [],
            }
        ],
    }

    with (
        patch(
            "app.graph.nodes.create_research_plan",
            side_effect=mock_plan,
        ),
        patch(
            "app.graph.nodes.search_embeddings",
            return_value=[],
        ),
        patch(
            "app.graph.nodes.analyze_research_plan",
            side_effect=mock_analysis,
        ),
        patch(
            "app.graph.nodes.verify_analysis",
            return_value=verification,
        ),
    ):
        result = research_graph.invoke({
            "question": "Calculate Apple's FY2026 net profit margin.",
            "limit": 3,
        })

    assert result["verification_result"] is True
    assert "independently verified" in result["answer"]
