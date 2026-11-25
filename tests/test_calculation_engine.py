
from decimal import Decimal

from app.analysis.calculation_engine import (
    calculate_net_profit_margin,
    calculate_revenue_growth,
)
from app.analysis.resolution import ResolutionResult
from app.analysis.schemas import (
    FinancialEvidence,
    FinancialMetric,
    ReportingPeriod,
    SourceProvenance,
)
def make_metric(
    value: str,
    *,
    metric: str,
    company: str = "Apple",
    currency: str = "USD",
    start_date: str = "2024-09-29",
    end_date: str = "2025-09-27",
) -> FinancialMetric:
    return FinancialMetric(
        company=company,
        metric=metric,
        value=Decimal(value),
        unit="USD",
        currency=currency,
        period=ReportingPeriod(
            label="FY2025",
            period_type="duration",
            start_date=start_date,
            end_date=end_date,
        ),
        source=SourceProvenance(
            source_type="sec_xbrl",
            filename="apple_10k.html",
            fact_id=f"fact-{metric}-{value}",
        ),
        evidence=FinancialEvidence(
            text=f"{metric}: {value}",
            original_label=metric,
            extraction_method="test",
            metadata={},
        ),
        dimensions={},
    )


def make_resolution(metric: FinancialMetric) -> ResolutionResult:
    return ResolutionResult(
        status="resolved",
        selected=metric,
        candidates=(metric,),
        duplicate_sources=(),
        rejected_count=0,
        reason="One matching financial fact found.",
    )


def make_unresolved() -> ResolutionResult:
    return ResolutionResult(
        status="not_found",
        selected=None,
        candidates=(),
        duplicate_sources=(),
        rejected_count=1,
        reason="No matching financial fact found.",
    )


def test_calculates_revenue_growth():
    current = make_metric(
        "120",
        metric="Revenue",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    previous = make_metric(
        "100",
        metric="Revenue",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )

    result = calculate_revenue_growth(
        make_resolution(current),
        make_resolution(previous),
    )

    assert result.status == "calculated"
    assert result.value == Decimal("20")
    assert result.unit == "%"
    assert result.is_calculated


def test_blocks_revenue_growth_when_previous_revenue_is_zero():
    current = make_metric(
        "120",
        metric="Revenue",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    previous = make_metric(
        "0",
        metric="Revenue",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )

    result = calculate_revenue_growth(
        make_resolution(current),
        make_resolution(previous),
    )

    assert result.status == "blocked"
    assert result.value is None
    assert result.errors


def test_blocks_revenue_growth_with_unresolved_input():
    current = make_metric(
        "120",
        metric="Revenue",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )

    result = calculate_revenue_growth(
        make_resolution(current),
        make_unresolved(),
    )

    assert result.status == "blocked"
    assert result.value is None


def test_blocks_revenue_growth_for_different_companies():
    current = make_metric(
        "120",
        metric="Revenue",
        company="Apple",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    previous = make_metric(
        "100",
        metric="Revenue",
        company="Microsoft",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )

    result = calculate_revenue_growth(
        make_resolution(current),
        make_resolution(previous),
    )

    assert result.status == "blocked"
    assert any("different companies" in error for error in result.errors)


def test_calculates_net_profit_margin():
    net_income = make_metric(
        "25",
        metric="Net Income",
    )
    revenue = make_metric(
        "100",
        metric="Revenue",
    )

    result = calculate_net_profit_margin(
        make_resolution(net_income),
        make_resolution(revenue),
    )

    assert result.status == "calculated"
    assert result.value == Decimal("25")
    assert result.unit == "%"
    assert result.is_calculated


def test_blocks_net_profit_margin_when_revenue_is_zero():
    net_income = make_metric(
        "25",
        metric="Net Income",
    )
    revenue = make_metric(
        "0",
        metric="Revenue",
    )

    result = calculate_net_profit_margin(
        make_resolution(net_income),
        make_resolution(revenue),
    )

    assert result.status == "blocked"
    assert result.value is None
    assert result.errors


def test_blocks_net_profit_margin_with_different_currencies():
    net_income = make_metric(
        "25",
        metric="Net Income",
        currency="USD",
    )
    revenue = make_metric(
        "100",
        metric="Revenue",
        currency="EUR",
    )

    result = calculate_net_profit_margin(
        make_resolution(net_income),
        make_resolution(revenue),
    )

    assert result.status == "blocked"
    assert any("different currencies" in error for error in result.errors)


def test_blocks_net_profit_margin_with_different_periods():
    net_income = make_metric(
        "25",
        metric="Net Income",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )
    revenue = make_metric(
        "100",
        metric="Revenue",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )

    result = calculate_net_profit_margin(
        make_resolution(net_income),
        make_resolution(revenue),
    )

    assert result.status == "blocked"
    assert any("same reporting period" in error for error in result.errors)


def test_blocks_net_profit_margin_with_ambiguous_input():
    net_income = make_metric(
        "25",
        metric="Net Income",
    )

    ambiguous = ResolutionResult(
        status="ambiguous",
        selected=None,
        candidates=(net_income,),
        duplicate_sources=(),
        rejected_count=0,
        reason="Conflicting financial facts found.",
    )

    result = calculate_net_profit_margin(
        ambiguous,
        make_resolution(make_metric("100", metric="Revenue")),
    )

    assert result.status == "blocked"
    assert result.value is None


