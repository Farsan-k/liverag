
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Literal

from app.analysis.calculations import profit_margin, revenue_growth
from app.analysis.resolution import ResolutionResult
from app.analysis.schemas import FinancialMetric


CalculationStatus = Literal["calculated", "blocked"]


@dataclass(frozen=True)
class CalculationResult:
    metric: str
    status: CalculationStatus
    value: Decimal | None
    unit: str
    formula: str
    inputs: tuple[FinancialMetric, ...]
    errors: tuple[str, ...]

    @property
    def is_calculated(self) -> bool:
        return self.status == "calculated"


def _get_resolved_metric(
    result: ResolutionResult,
    input_name: str,
) -> tuple[FinancialMetric | None, str | None]:
    if not isinstance(result, ResolutionResult):
        raise TypeError(
            f"{input_name} must be a ResolutionResult"
        )

    if not result.is_resolved or result.selected is None:
        return None, (
            f"{input_name} is not resolved: {result.status}. "
            f"{result.reason}"
        )

    return result.selected, None


def _validate_same_company(
    metrics: tuple[FinancialMetric, ...],
) -> str | None:
    companies = {
        metric.company.strip().casefold()
        for metric in metrics
    }

    if len(companies) != 1:
        return "Calculation inputs belong to different companies."

    return None


def _validate_same_currency(
    metrics: tuple[FinancialMetric, ...],
) -> str | None:
    currencies = {
        metric.currency
        for metric in metrics
    }

    if len(currencies) != 1:
        return "Calculation inputs use different currencies."

    return None


def _same_reporting_period(
    first: FinancialMetric,
    second: FinancialMetric,
) -> bool:
    return (
        first.period.period_type == second.period.period_type
        and first.period.start_date == second.period.start_date
        and first.period.end_date == second.period.end_date
        and first.period.instant_date == second.period.instant_date
    )



def calculate_revenue_growth(
    current_revenue: ResolutionResult,
    previous_revenue: ResolutionResult,
) -> CalculationResult:
    formula = (
        "((Current Revenue - Previous Revenue) "
        "/ Previous Revenue) × 100"
    )

    current, current_error = _get_resolved_metric(
        current_revenue,
        "Current revenue",
    )

    previous, previous_error = _get_resolved_metric(
        previous_revenue,
        "Previous revenue",
    )

    errors = tuple(
        error
        for error in (current_error, previous_error)
        if error is not None
    )

    inputs = tuple(
        metric
        for metric in (current, previous)
        if metric is not None
    )

    if errors:
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=errors,
        )

    assert current is not None and previous is not None

    # Validate company and currency.
    company_error = _validate_same_company(inputs)
    currency_error = _validate_same_currency(inputs)

    if company_error or currency_error:
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=tuple(
                error
                for error in (company_error, currency_error)
                if error is not None
            ),
        )

    # Revenue growth requires duration reporting periods.
    if (
        current.period.period_type != "duration"
        or previous.period.period_type != "duration"
    ):
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(
                "Revenue growth requires duration reporting periods.",
            ),
        )

    # Validate reporting period dates.
    if (
        current.period.start_date is None
        or current.period.end_date is None
        or previous.period.start_date is None
        or previous.period.end_date is None
    ):
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(
                "Revenue growth requires complete reporting period dates.",
            ),
        )

    # Validate date ranges.
    if (
        current.period.start_date > current.period.end_date
        or previous.period.start_date > previous.period.end_date
    ):
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(
                "Reporting period start date cannot be later than end date.",
            ),
        )

    # Current period must follow previous period.
    if current.period.end_date <= previous.period.end_date:
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(
                "Current revenue must belong to a later reporting period.",
            ),
        )

    # Both periods must have comparable durations.
    current_duration = (
        current.period.end_date - current.period.start_date
    )

    previous_duration = (
        previous.period.end_date - previous.period.start_date
    )

    if abs(current_duration - previous_duration) > timedelta(days=1):
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(
                "Revenue growth requires comparable reporting period durations.",
            ),
        )

    # Check whether these are consecutive annual periods.
    consecutive_annual = (
        current.period.start_date
        == previous.period.end_date + timedelta(days=1)
    )

    # Check whether these are matching quarters
    # in consecutive fiscal years.
    current_fiscal_year = getattr(
        current.period,
        "fiscal_year",
        None,
    )

    previous_fiscal_year = getattr(
        previous.period,
        "fiscal_year",
        None,
    )

    current_fiscal_period = getattr(
        current.period,
        "fiscal_period",
        None,
    )

    previous_fiscal_period = getattr(
        previous.period,
        "fiscal_period",
        None,
    )

    current_scope = getattr(
        current.period,
        "period_scope",
        None,
    )

    previous_scope = getattr(
        previous.period,
        "period_scope",
        None,
    )

    consecutive_quarterly = (
        current_fiscal_year is not None
        and previous_fiscal_year is not None
        and current_fiscal_year == previous_fiscal_year + 1
        and current_fiscal_period in {"Q1", "Q2", "Q3", "Q4"}
        and current_fiscal_period == previous_fiscal_period
        and current_scope in {"standalone", "ytd"}
        and current_scope == previous_scope
    )

    if not (consecutive_annual or consecutive_quarterly):
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(
                "Revenue growth requires consecutive annual periods "
                "or matching quarters in consecutive fiscal years "
                "with the same reporting scope.",
            ),
        )

    # Perform deterministic calculation.
    try:
        value = revenue_growth(
            current.value,
            previous.value,
        )

    except (ValueError, TypeError, ZeroDivisionError) as exc:
        return CalculationResult(
            metric="Revenue Growth",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(str(exc),),
        )

    return CalculationResult(
        metric="Revenue Growth",
        status="calculated",
        value=value,
        unit="%",
        formula=formula,
        inputs=inputs,
        errors=(),
    )



def calculate_net_profit_margin(
    net_income: ResolutionResult,
    revenue: ResolutionResult,
) -> CalculationResult:
    formula = "(Net Income / Revenue) × 100"

    profit, profit_error = _get_resolved_metric(
        net_income,
        "Net income",
    )

    sales, revenue_error = _get_resolved_metric(
        revenue,
        "Revenue",
    )

    errors = tuple(
        error
        for error in (profit_error, revenue_error)
        if error is not None
    )

    inputs = tuple(
        metric
        for metric in (profit, sales)
        if metric is not None
    )

    if errors:
        return CalculationResult(
            metric="Net Profit Margin",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=errors,
        )

    assert profit is not None and sales is not None

    company_error = _validate_same_company(inputs)
    currency_error = _validate_same_currency(inputs)

    if company_error or currency_error:
        return CalculationResult(
            metric="Net Profit Margin",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=tuple(
                error
                for error in (company_error, currency_error)
                if error is not None
            ),
        )

    if not _same_reporting_period(profit, sales):
        return CalculationResult(
            metric="Net Profit Margin",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(
                "Net income and revenue must use the same reporting period.",
            ),
        )

    try:
        value = profit_margin(
            profit.value,
            sales.value,
        )

    except (ValueError, TypeError) as exc:
        return CalculationResult(
            metric="Net Profit Margin",
            status="blocked",
            value=None,
            unit="%",
            formula=formula,
            inputs=inputs,
            errors=(str(exc),),
        )

    return CalculationResult(
        metric="Net Profit Margin",
        status="calculated",
        value=value,
        unit="%",
        formula=formula,
        inputs=inputs,
        errors=(),
    )
