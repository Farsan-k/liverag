
from decimal import Decimal

from app.analysis.fact_selection import FactSelectionRequest
from app.analysis.resolution import resolve_financial_fact
from app.analysis.schemas import (
    FinancialEvidence,
    FinancialMetric,
    ReportingPeriod,
    SourceProvenance,
)


def make_metric(
    value: str,
    *,
    metric: str = "Revenue",
    company: str = "Apple",
    currency: str = "USD",
    dimensions: dict | None = None,
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
            start_date="2024-09-29",
            end_date="2025-09-27",
        ),
        source=SourceProvenance(
            source_type="sec_xbrl",
            filename="apple_10k.html",
            fact_id=f"fact-{value}",
        ),
        evidence=FinancialEvidence(
            text=f"Revenue reported: {value}",
            original_label=metric,
            extraction_method="test",
            metadata={},
        ),
        dimensions=dimensions or {},
    )


def make_request() -> FactSelectionRequest:
    return FactSelectionRequest(
        metric="Revenue",
        company="Apple",
        period_start="2024-09-29",
        period_end="2025-09-27",
        currency="USD",
        consolidated_only=True,
    )


def test_resolves_single_matching_fact():
    metric = make_metric("416161000000")

    result = resolve_financial_fact(
        [metric],
        make_request(),
    )

    assert result.status == "resolved"
    assert result.is_resolved is True
    assert result.selected == metric
    assert result.candidates == (metric,)


def test_returns_ambiguous_for_conflicting_facts():
    metrics = [
        make_metric("416161000000"),
        make_metric("415000000000"),
    ]

    result = resolve_financial_fact(
        metrics,
        make_request(),
    )

    assert result.status == "ambiguous"
    assert result.is_resolved is False
    assert result.selected is None
    assert len(result.candidates) == 2


def test_returns_not_found_when_fact_is_missing():
    result = resolve_financial_fact(
        [],
        make_request(),
    )

    assert result.status == "not_found"
    assert result.is_resolved is False
    assert result.selected is None
    assert result.candidates == ()


def test_preserves_duplicate_source_information():
    metric = make_metric("416161000000")
    duplicate = make_metric("416161000000")

    result = resolve_financial_fact(
        [metric, duplicate],
        make_request(),
    )

    assert result.status == "resolved"
    assert result.selected is not None
    assert len(result.duplicate_sources) == 1


def test_rejects_invalid_metric_input():
    try:
        resolve_financial_fact(
            ["not-a-financial-metric"],
            make_request(),
        )
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError")
