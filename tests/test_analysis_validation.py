
from datetime import date
from decimal import Decimal

import pytest

from app.analysis.schemas import (
    FinancialMetric,
    ReportingPeriod,
    SourceProvenance,
)
from app.analysis.validation import (
    validate_metric_set,
    validate_ratio_inputs,
)


def make_metric(
    name,
    value="100",
    company="Apple",
    currency="USD",
    unit="USD",
    period_type="duration",
    start_date=date(2024, 9, 29),
    end_date=date(2025, 9, 27),
    instant_date=None,
):
    return FinancialMetric(
        company=company,
        metric=name,
        value=Decimal(value),
        unit=unit,
        currency=currency,
        period=ReportingPeriod(
            label="FY2025",
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
            instant_date=instant_date,
        ),
        source=SourceProvenance(
            source_type="sec_xbrl",
            fact_id=f"fact_{name.replace(' ', '_')}",
        ),
    )


def test_valid_net_profit_margin_inputs():
    metrics = [
        make_metric("Net Income", "200"),
        make_metric("Revenue", "1000"),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is True
    assert result.errors == ()


def test_missing_required_metric():
    metrics = [
        make_metric("Net Income", "200"),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("Revenue" in error for error in result.errors)


def test_company_mismatch():
    metrics = [
        make_metric("Net Income", company="Apple"),
        make_metric("Revenue", company="Microsoft"),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("Company mismatch" in error for error in result.errors)


def test_currency_mismatch():
    metrics = [
        make_metric("Net Income", currency="USD"),
        make_metric("Revenue", currency="INR"),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("Currency mismatch" in error for error in result.errors)


def test_unit_mismatch():
    metrics = [
        make_metric("Net Income", unit="USD"),
        make_metric("Revenue", unit="USD millions"),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("Unit mismatch" in error for error in result.errors)


def test_period_mismatch():
    metrics = [
        make_metric("Net Income"),
        make_metric(
            "Revenue",
            start_date=date(2023, 9, 30),
            end_date=date(2024, 9, 28),
        ),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("Reporting periods are incompatible" in error
               for error in result.errors)


def test_unknown_period_is_rejected():
    metrics = [
        make_metric("Net Income", period_type="unknown"),
        make_metric("Revenue", period_type="unknown"),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("reporting period is unknown" in error
               for error in result.errors)


def test_unknown_currency_is_rejected():
    metrics = [
        make_metric("Net Income", currency=None),
        make_metric("Revenue", currency=None),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("currency is unknown" in error for error in result.errors)


def test_duplicate_metric_is_rejected():
    metrics = [
        make_metric("Net Income"),
        make_metric("Net Income"),
        make_metric("Revenue"),
    ]

    result = validate_ratio_inputs("net_profit_margin", metrics)

    assert result.is_valid is False
    assert any("Duplicate metric" in error for error in result.errors)


def test_unsupported_ratio_is_rejected():
    result = validate_ratio_inputs("unknown_ratio", [])

    assert result.is_valid is False
    assert "Unsupported ratio: unknown_ratio." in result.errors


def test_current_ratio_dependencies():
    metrics = [
        make_metric("Current Assets"),
        make_metric("Current Liabilities"),
    ]

    result = validate_ratio_inputs("current_ratio", metrics)

    assert result.is_valid is True


def test_instant_period_metrics_can_match():
    metrics = [
        make_metric(
            "Total Assets",
            period_type="instant",
            start_date=None,
            end_date=None,
            instant_date=date(2025, 9, 27),
        ),
        make_metric(
            "Total Equity",
            period_type="instant",
            start_date=None,
            end_date=None,
            instant_date=date(2025, 9, 27),
        ),
    ]

    result = validate_metric_set(
        metrics,
        ["Total Assets", "Total Equity"],
    )

    assert result.is_valid is True


def test_duration_and_instant_periods_cannot_match():
    metrics = [
        make_metric("Net Income"),
        make_metric(
            "Total Assets",
            period_type="instant",
            start_date=None,
            end_date=None,
            instant_date=date(2025, 9, 27),
        ),
    ]

    result = validate_metric_set(
        metrics,
        ["Net Income", "Total Assets"],
    )

    assert result.is_valid is False
    assert any("Reporting periods are incompatible" in error
               for error in result.errors)





def test_valid_standalone_quarter_period():
    period = ReportingPeriod(
        label="Q3 FY2026",
        period_type="duration",
        start_date=date(2026, 3, 29),
        end_date=date(2026, 6, 27),
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="standalone",
    )

    assert period.fiscal_year == 2026
    assert period.fiscal_period == "Q3"
    assert period.period_scope == "standalone"


def test_valid_ytd_quarter_period():
    period = ReportingPeriod(
        label="Q3 FY2026 YTD",
        period_type="duration",
        start_date=date(2025, 9, 28),
        end_date=date(2026, 6, 27),
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="ytd",
    )

    assert period.period_scope == "ytd"


def test_valid_annual_period():
    period = ReportingPeriod(
        label="FY2026",
        period_type="duration",
        start_date=date(2025, 9, 28),
        end_date=date(2026, 9, 26),
        fiscal_year=2026,
        fiscal_period="FY",
        period_scope="annual",
    )

    assert period.period_scope == "annual"


def test_rejects_annual_period_with_quarter_label():
    with pytest.raises(ValueError):
        ReportingPeriod(
            period_type="duration",
            start_date=date(2026, 3, 29),
            end_date=date(2026, 6, 27),
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="annual",
        )


def test_rejects_standalone_period_without_fiscal_metadata():
    with pytest.raises(ValueError):
        ReportingPeriod(
            period_type="duration",
            start_date=date(2026, 3, 29),
            end_date=date(2026, 6, 27),
            period_scope="standalone",
        )


def test_rejects_fiscal_year_without_fiscal_period():
    with pytest.raises(ValueError):
        ReportingPeriod(
            period_type="duration",
            start_date=date(2026, 3, 29),
            end_date=date(2026, 6, 27),
            fiscal_year=2026,
        )


def test_rejects_fiscal_period_without_fiscal_year():
    with pytest.raises(ValueError):
        ReportingPeriod(
            period_type="duration",
            start_date=date(2026, 3, 29),
            end_date=date(2026, 6, 27),
            fiscal_period="Q3",
        )


def test_rejects_instant_period_with_quarter_scope():
    with pytest.raises(ValueError):
        ReportingPeriod(
            period_type="instant",
            instant_date=date(2026, 6, 27),
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="standalone",
        )
