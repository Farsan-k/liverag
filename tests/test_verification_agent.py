
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
