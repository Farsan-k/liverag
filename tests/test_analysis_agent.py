
from unittest.mock import patch

from app.agents.analysis_agent import analyze_research_plan
from app.agents.research_agent import ResearchPlan


def test_net_profit_margin_calculation():
    plan = ResearchPlan(
        company="Apple Inc.",
        metrics=["Net Profit Margin", "Revenue", "Net Income"],
        periods=["FY2026"],
        analysis_type="ratio_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert len(result["calculations"]) == 1

    calculation = result["calculations"][0]

    assert calculation["metric"] == "Net Profit Margin"
    assert calculation["status"] == "calculated"
    assert calculation["value"] is not None
    assert calculation["unit"] == "%"
    assert len(calculation["inputs"]) == 2


def test_revenue_growth_calculation():
    plan = ResearchPlan(
        company="Apple Inc.",
        metrics=["Revenue"],
        periods=["FY2025", "FY2026"],
        analysis_type="growth_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert len(result["calculations"]) == 1

    calculation = result["calculations"][0]

    assert calculation["metric"] == "Revenue Growth"
    assert calculation["status"] == "calculated"
    assert calculation["value"] is not None
    assert len(calculation["inputs"]) == 2


def test_missing_company_is_blocked():
    plan = ResearchPlan(
        metrics=["Revenue"],
        analysis_type="growth_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert result["calculations"] == []
    assert result["limitations"]


def test_unsupported_calculation_is_blocked():
    plan = ResearchPlan(
        company="Apple Inc.",
        metrics=["EBITDA"],
        analysis_type="growth_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert result["calculations"] == []
    assert result["limitations"]


def test_missing_reporting_period_is_blocked():
    plan = ResearchPlan(
        company="Company That Does Not Exist",
        metrics=["Revenue"],
        periods=["FY2026"],
        analysis_type="growth_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert result["calculations"] == []
    assert result["limitations"]


def test_descriptive_plan_skips_calculation():
    plan = ResearchPlan(
        company="Apple Inc.",
        metrics=["Revenue"],
        analysis_type="summary",
        requires_calculation=False,
    )

    result = analyze_research_plan(plan)

    assert result["calculations"] == []
    assert "does not require" in result["summary"]


def test_quarterly_net_profit_margin_standalone():
    plan = ResearchPlan(
        company="Apple Inc.",
        metrics=["Net Profit Margin", "Revenue", "Net Income"],
        periods=["Q3 FY2026"],
        period_scope="standalone",
        analysis_type="ratio_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert len(result["calculations"]) == 1

    calculation = result["calculations"][0]

    assert calculation["metric"] == "Net Profit Margin"
    assert calculation["status"] == "calculated"
    assert calculation["value"] is not None
    assert calculation["unit"] == "%"
    assert len(calculation["inputs"]) == 2


def test_quarterly_net_profit_margin_ytd():
    plan = ResearchPlan(
        company="Apple Inc.",
        metrics=["Net Profit Margin", "Revenue", "Net Income"],
        periods=["Q3 FY2026"],
        period_scope="ytd",
        analysis_type="ratio_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert len(result["calculations"]) == 1

    calculation = result["calculations"][0]

    assert calculation["metric"] == "Net Profit Margin"
    assert calculation["status"] == "calculated"
    assert calculation["value"] is not None
    assert len(calculation["inputs"]) == 2


def test_quarterly_revenue_growth_standalone():
    plan = ResearchPlan(
        company="Apple Inc.",
        metrics=["Revenue"],
        periods=["Q3 FY2025", "Q3 FY2026"],
        period_scope="standalone",
        analysis_type="growth_analysis",
        requires_calculation=True,
    )

    result = analyze_research_plan(plan)

    assert len(result["calculations"]) == 1

    calculation = result["calculations"][0]

    print("\nQUARTERLY REVENUE GROWTH RESULT:", result)

    assert calculation["metric"] == "Revenue Growth"
    assert calculation["status"] == "calculated"
    assert calculation["value"] is not None
    assert len(calculation["inputs"]) == 2
