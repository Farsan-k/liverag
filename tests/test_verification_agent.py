
from decimal import Decimal

from app.agents.verification_agent import verify_analysis


def make_input(
    metric,
    value,
    start="2025-09-28",
    end="2026-09-26",
):
    return {
        "company": "Apple Inc.",
        "metric": metric,
        "value": str(value),
        "unit": "USD",
        "currency": "USD",
        "period": {
            "label": f"{start} to {end}",
            "period_type": "duration",
            "start_date": start,
            "end_date": end,
            "instant_date": None,
        },
        "source": {
            "source_type": "sec_xbrl",
            "source_document_id": 4,
        },
        "evidence": {
            "text": "SEC financial fact",
            "original_label": metric,
            "extraction_method": "xbrl",
            "metadata": {},
        },
        "dimensions": {},
    }


def make_margin_analysis(value="27.60351186423687540984976004"):
    return {
        "calculations": [
            {
                "metric": "Net Profit Margin",
                "status": "calculated",
                "value": value,
                "unit": "%",
                "formula": "(Net Income / Revenue) × 100",
                "inputs": [
                    make_input("Net Income", "132175000000"),
                    make_input("Revenue", "478834000000"),
                ],
                "errors": [],
            }
        ]
    }


def make_growth_analysis(value="15.05979656911627951682161471"):
    return {
        "calculations": [
            {
                "metric": "Revenue Growth",
                "status": "calculated",
                "value": value,
                "unit": "%",
                "formula": (
                    "((Current Revenue - Previous Revenue) "
                    "/ Previous Revenue) × 100"
                ),
                "inputs": [
                    make_input(
                        "Revenue",
                        "478834000000",
                        "2025-09-28",
                        "2026-09-26",
                    ),
                    make_input(
                        "Revenue",
                        "416161000000",
                        "2024-09-29",
                        "2025-09-27",
                    ),
                ],
                "errors": [],
            }
        ]
    }





def make_quarterly_growth_analysis(
    current_period="Q3",
    previous_period="Q3",
    current_scope="standalone",
    previous_scope="standalone",
    incorrect_value=False,
):
    current = make_input(
        "Revenue",
        "109417000000",
        "2026-03-29",
        "2026-06-27",
    )

    previous = make_input(
        "Revenue",
        "94036000000",
        "2025-03-30",
        "2025-06-28",
    )

    current["period"].update({
        "fiscal_year": 2026,
        "fiscal_period": current_period,
        "period_scope": current_scope,
    })

    previous["period"].update({
        "fiscal_year": 2025,
        "fiscal_period": previous_period,
        "period_scope": previous_scope,
    })

    current_value = Decimal(current["value"])
    previous_value = Decimal(previous["value"])

    growth = (
        (current_value - previous_value) / previous_value
    ) * Decimal("100")

    return {
        "calculations": [
            {
                "metric": "Revenue Growth",
                "status": "calculated",
                "value": (
                    "99.99" if incorrect_value else str(growth)
                ),
                "unit": "%",
                "formula": (
                    "((Current Revenue - Previous Revenue) "
                    "/ Previous Revenue) × 100"
                ),
                "inputs": [current, previous],
                "errors": [],
            }
        ]
    }




def test_verifies_net_profit_margin():
    result = verify_analysis(make_margin_analysis())

    assert result["verified"] is True
    assert result["errors"] == []


def test_verifies_revenue_growth():
    result = verify_analysis(make_growth_analysis())

    assert result["verified"] is True
    assert result["errors"] == []


def test_rejects_incorrect_calculation_value():
    result = verify_analysis(
        make_margin_analysis(value="99.99")
    )

    assert result["verified"] is False
    assert any(
        "does not match" in error
        for error in result["errors"]
    )


def test_rejects_different_companies():
    analysis = make_margin_analysis()
    analysis["calculations"][0]["inputs"][1]["company"] = "Microsoft"

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_different_currencies():
    analysis = make_margin_analysis()
    analysis["calculations"][0]["inputs"][1]["currency"] = "INR"

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_different_reporting_periods():
    analysis = make_margin_analysis()
    analysis["calculations"][0]["inputs"][1]["period"]["end_date"] = (
        "2026-09-25"
    )

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_missing_provenance():
    analysis = make_margin_analysis()
    analysis["calculations"][0]["inputs"][0]["source"] = {}

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_segment_facts():
    analysis = make_margin_analysis()
    analysis["calculations"][0]["inputs"][0]["dimensions"] = {
        "ProductAxis": "iPhone"
    }

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_blocked_calculation():
    analysis = make_margin_analysis()
    analysis["calculations"][0]["status"] = "blocked"

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_non_consecutive_growth_periods():
    analysis = make_growth_analysis()
    analysis["calculations"][0]["inputs"][1]["period"]["end_date"] = (
        "2025-09-20"
    )

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_missing_calculations():
    result = verify_analysis({"calculations": []})

    assert result["verified"] is False
    assert result["errors"]




def test_verifies_quarterly_year_over_year_growth():
    analysis = make_quarterly_growth_analysis()

    result = verify_analysis(analysis)

    assert result["verified"] is True
    assert result["errors"] == []


def test_rejects_different_quarters():
    analysis = make_quarterly_growth_analysis(
        current_period="Q3",
        previous_period="Q2",
    )

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_different_quarter_scopes():
    analysis = make_quarterly_growth_analysis(
        current_scope="standalone",
        previous_scope="ytd",
    )

    result = verify_analysis(analysis)

    assert result["verified"] is False


def test_rejects_incorrect_quarterly_growth_value():
    analysis = make_quarterly_growth_analysis(
        incorrect_value=True,
    )

    result = verify_analysis(analysis)

    assert result["verified"] is False
    assert any(
        "does not match" in error
        for error in result["errors"]
    )
