
import pytest

from app.agents.research_agent import (
    ResearchPlan,
    create_research_plan,
    normalize_research_plan,
)


def test_research_plan_schema():
    plan = ResearchPlan(
        company="Apple",
        metrics=["Revenue"],
        periods=["FY2024", "FY2025"],
        analysis_type="growth_analysis",
        requires_calculation=True,
        search_requirements=[
            "Apple FY2024 Revenue",
            "Apple FY2025 Revenue",
        ],
    )

    assert plan.company == "Apple"
    assert plan.analysis_type == "growth_analysis"
    assert plan.requires_calculation is True


def test_research_plan_rejects_invalid_analysis_type():
    with pytest.raises(ValueError):
        ResearchPlan(
            analysis_type="invalid_type",
        )


def test_empty_question_is_rejected():
    with pytest.raises(ValueError):
        create_research_plan("")



def test_search_requirements_are_generated_when_missing(monkeypatch):
    from app.agents import research_agent

    fake_content = ResearchPlan(
        company="Apple",
        metrics=["Revenue"],
        periods=["FY2024", "FY2025"],
        analysis_type="growth_analysis",
        requires_calculation=True,
        search_requirements=[],
    ).model_dump_json()

    fake_response = {
        "message": {
            "content": fake_content
        }
    }

    monkeypatch.setattr(
        research_agent.ollama,
        "chat",
        lambda **kwargs: fake_response,
    )

    plan = create_research_plan(
        "Compare Apple's revenue growth between FY2024 and FY2025."
    )

    assert plan.search_requirements == [
        "Apple FY2024 Revenue",
        "Apple FY2025 Revenue",
    ]




def test_normalize_extracts_tesla_cash_flow_periods():
    plan = ResearchPlan(
        company="Tesla",
        metrics=[],
        periods=[],
        analysis_type="trend_analysis",
        requires_calculation=False,
        search_requirements=[],
    )

    result = normalize_research_plan(
        "Analyze Tesla's operating cash flow trend between FY2023 and FY2025.",
        plan,
    )

    assert result.metrics == ["Operating Cash Flow"]
    assert result.periods == ["FY2023", "FY2024", "FY2025"]
    assert result.analysis_type == "cash_flow_analysis"
    assert result.requires_calculation is True


def test_normalize_does_not_invent_reporting_periods():
    plan = ResearchPlan(
        company="Apple",
        metrics=["Revenue"],
        periods=["All Time"],
        analysis_type="trend_analysis",
    )

    result = normalize_research_plan(
        "What was Apple's revenue?",
        plan,
    )

    assert result.periods == []
    assert result.search_requirements == ["Apple Revenue"]


def test_normalize_generates_combined_search_requirement():
    plan = ResearchPlan(
        company="Apple",
        metrics=["Revenue"],
        periods=[],
        search_requirements=["Apple", "Revenue"],
    )

    result = normalize_research_plan(
        "What was Apple's revenue?",
        plan,
    )

    assert result.search_requirements == ["Apple Revenue"]


def test_normalize_classifies_profit_margin():
    plan = ResearchPlan(
        company="Microsoft",
        metrics=["Net Profit Margin"],
        periods=["FY2025"],
        analysis_type="trend_analysis",
    )

    result = normalize_research_plan(
        "Calculate Microsoft's net profit margin for FY2025.",
        plan,
    )

    assert result.analysis_type == "ratio_analysis"
    assert result.requires_calculation is True
