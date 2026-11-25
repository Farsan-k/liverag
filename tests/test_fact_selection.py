
from datetime import date
from decimal import Decimal

import pytest

from app.analysis.fact_selection import (
    FactSelectionRequest,
    select_financial_fact,
)
from app.analysis.schemas import (
    FinancialEvidence,
    FinancialMetric,
    ReportingPeriod,
    SourceProvenance,
)


REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"



def make_metric(
    value: str,
    dimensions: dict | None = None,
    fact_id: str = "fact-1",
    fiscal_year: int | None = None,
    fiscal_period: str | None = None,
    period_scope: str = "unknown",
    start_date: date = date(2024, 9, 29),
    end_date: date = date(2025, 9, 27),
) -> FinancialMetric:
    return FinancialMetric(
        company="Apple",
        metric=REVENUE,
        value=Decimal(value),
        unit="iso4217:USD",
        currency="USD",
        period=ReportingPeriod(
            label="Financial reporting period",
            period_type="duration",
            start_date=start_date,
            end_date=end_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            period_scope=period_scope,
        ),
        source=SourceProvenance(
            source_type="sec_xbrl",
            filename="aapl-20250927.html",
            fact_id=fact_id,
            context_ref="c-1",
        ),
        evidence=FinancialEvidence(
            text=f"Revenue: {value}",
            original_label=REVENUE,
            extraction_method="sec_xbrl",
        ),
        dimensions=dimensions or {},
        confidence=1.0,
    )



def test_select_consolidated_revenue():
    consolidated = make_metric("416161000000")
    product = make_metric(
        "307003000000",
        {"srt:ProductOrServiceAxis": "us-gaap:ProductMember"},
    )

    result = select_financial_fact(
        [product, consolidated],
        FactSelectionRequest(metric=REVENUE),
    )

    assert result.selected is not None
    assert result.selected.value == Decimal("416161000000")
    assert not result.is_ambiguous


def test_select_product_revenue():
    product = make_metric(
        "307003000000",
        {"srt:ProductOrServiceAxis": "us-gaap:ProductMember"},
    )
    services = make_metric(
        "109158000000",
        {"srt:ProductOrServiceAxis": "us-gaap:ServiceMember"},
    )

    result = select_financial_fact(
        [product, services],
        FactSelectionRequest(
            metric=REVENUE,
            dimensions={
                "srt:ProductOrServiceAxis": "us-gaap:ProductMember"
            },
            consolidated_only=False,
        ),
    )

    assert result.selected is not None
    assert result.selected.value == Decimal("307003000000")


def test_select_service_revenue():
    services = make_metric(
        "109158000000",
        {"srt:ProductOrServiceAxis": "us-gaap:ServiceMember"},
    )

    result = select_financial_fact(
        [services],
        FactSelectionRequest(
            metric=REVENUE,
            dimensions={
                "srt:ProductOrServiceAxis": "us-gaap:ServiceMember"
            },
            consolidated_only=False,
        ),
    )

    assert result.selected is not None
    assert result.selected.value == Decimal("109158000000")


def test_deduplicate_equivalent_facts():
    first = make_metric("416161000000", fact_id="fact-1")
    second = make_metric("416161000000", fact_id="fact-2")

    result = select_financial_fact(
        [first, second],
        FactSelectionRequest(metric=REVENUE),
    )

    assert result.selected is not None
    assert result.selected.value == Decimal("416161000000")
    assert result.rejected_count == 1
    assert not result.is_ambiguous


def test_conflicting_consolidated_facts_are_ambiguous():
    first = make_metric("416161000000", fact_id="fact-1")
    second = make_metric("410000000000", fact_id="fact-2")

    result = select_financial_fact(
        [first, second],
        FactSelectionRequest(metric=REVENUE),
    )

    assert result.selected is None
    assert result.is_ambiguous
    assert len(result.candidates) == 2


def test_missing_fact_returns_no_selection():
    result = select_financial_fact(
        [],
        FactSelectionRequest(metric=REVENUE),
    )

    assert result.selected is None
    assert not result.is_ambiguous


def test_wrong_currency_is_rejected():
    metric = make_metric("416161000000")

    result = select_financial_fact(
        [metric],
        FactSelectionRequest(
            metric=REVENUE,
            currency="EUR",
        ),
    )

    assert result.selected is None


def test_wrong_period_is_rejected():
    metric = make_metric("416161000000")

    result = select_financial_fact(
        [metric],
        FactSelectionRequest(
            metric=REVENUE,
            period_start="2023-10-01",
            period_end="2024-09-28",
        ),
    )

    assert result.selected is None


def test_explicit_dimensions_can_select_segment():
    americas = make_metric(
        "178353000000",
        {
            "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
            "us-gaap:StatementBusinessSegmentsAxis": "aapl:AmericasSegmentMember",
        },
    )

    result = select_financial_fact(
        [americas],
        FactSelectionRequest(
            metric=REVENUE,
            dimensions={
                "us-gaap:StatementBusinessSegmentsAxis":
                    "aapl:AmericasSegmentMember"
            },
            consolidated_only=False,
        ),
    )

    assert result.selected is not None
    assert result.selected.value == Decimal("178353000000")


def test_consolidated_only_does_not_select_segment():
    americas = make_metric(
        "178353000000",
        {
            "us-gaap:StatementBusinessSegmentsAxis":
                "aapl:AmericasSegmentMember"
        },
    )

    result = select_financial_fact(
        [americas],
        FactSelectionRequest(metric=REVENUE),
    )

    assert result.selected is None



def test_select_q3_fiscal_year_standalone_revenue():
    standalone = make_metric(
        "109417000000",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="standalone",
        start_date=date(2026, 3, 29),
        end_date=date(2026, 6, 27),
    )

    ytd = make_metric(
        "364357000000",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="ytd",
        start_date=date(2025, 9, 28),
        end_date=date(2026, 6, 27),
    )

    result = select_financial_fact(
        [standalone, ytd],
        FactSelectionRequest(
            metric=REVENUE,
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="standalone",
        ),
    )

    assert result.selected is not None
    assert result.selected.value == Decimal("109417000000")
    assert result.selected.period.period_scope == "standalone"
    assert not result.is_ambiguous


def test_select_q3_fiscal_year_ytd_revenue():
    standalone = make_metric(
        "109417000000",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="standalone",
        start_date=date(2026, 3, 29),
        end_date=date(2026, 6, 27),
    )

    ytd = make_metric(
        "364357000000",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="ytd",
        start_date=date(2025, 9, 28),
        end_date=date(2026, 6, 27),
    )

    result = select_financial_fact(
        [standalone, ytd],
        FactSelectionRequest(
            metric=REVENUE,
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="ytd",
        ),
    )

    assert result.selected is not None
    assert result.selected.value == Decimal("364357000000")
    assert result.selected.period.period_scope == "ytd"
    assert not result.is_ambiguous


def test_missing_fiscal_period_returns_no_selection():
    metric = make_metric(
        "109417000000",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="standalone",
    )

    result = select_financial_fact(
        [metric],
        FactSelectionRequest(
            metric=REVENUE,
            fiscal_year=2025,
            fiscal_period="Q3",
            period_scope="standalone",
        ),
    )

    assert result.selected is None
    assert not result.is_ambiguous


def test_fiscal_period_conflicting_facts_are_ambiguous():
    first = make_metric(
        "109417000000",
        fact_id="fact-1",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="standalone",
    )

    second = make_metric(
        "110000000000",
        fact_id="fact-2",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="standalone",
    )

    result = select_financial_fact(
        [first, second],
        FactSelectionRequest(
            metric=REVENUE,
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="standalone",
        ),
    )

    assert result.selected is None
    assert result.is_ambiguous
    assert len(result.candidates) == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fiscal_year": 2026},
        {"fiscal_period": "Q3"},
        {"period_scope": "standalone"},
        {
            "fiscal_year": 2026,
            "fiscal_period": "Q3",
        },
        {
            "fiscal_year": 2026,
            "fiscal_period": "Q3",
            "period_scope": "annual",
        },
        {
            "fiscal_year": 2026,
            "fiscal_period": "FY",
            "period_scope": "standalone",
        },
    ],
)
def test_invalid_fiscal_selection_request(kwargs):
    with pytest.raises(ValueError):
        FactSelectionRequest(
            metric=REVENUE,
            **kwargs,
        )
