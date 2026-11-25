
from dataclasses import dataclass
from typing import Mapping, Sequence

from app.analysis.metrics import normalize_metric_label
from app.analysis.schemas import FinancialMetric


# Required input metrics for each supported financial ratio.
RATIO_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "gross_profit_margin": (
        "Gross Profit",
        "Revenue",
    ),
    "operating_profit_margin": (
        "Operating Income",
        "Revenue",
    ),
    "net_profit_margin": (
        "Net Income",
        "Revenue",
    ),
    "return_on_assets": (
        "Net Income",
        "Beginning Total Assets",
        "Ending Total Assets",
    ),
    "return_on_equity": (
        "Net Income",
        "Beginning Total Equity",
        "Ending Total Equity",
    ),
    "current_ratio": (
        "Current Assets",
        "Current Liabilities",
    ),
    "debt_to_equity_ratio": (
        "Total Debt",
        "Total Equity",
    ),
}


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a group of financial metrics."""

    is_valid: bool
    errors: tuple[str, ...]
    metrics: Mapping[str, FinancialMetric]


def _canonical_metric_name(name: str) -> str:
    """Return a known canonical name, preserving unknown labels."""

    normalized = normalize_metric_label(name)

    if normalized is not None:
        return normalized

    return " ".join(name.strip().split())


def _period_signature(metric: FinancialMetric) -> tuple:
    """Build a comparable reporting-period signature."""

    period = metric.period

    return (
        period.period_type,
        period.start_date,
        period.end_date,
        period.instant_date,
    )


def _validate_periods(
    metrics: Sequence[FinancialMetric],
    errors: list[str],
) -> None:
    """Ensure all metrics have known and matching reporting periods."""

    for metric in metrics:
        if metric.period.period_type == "unknown":
            errors.append(
                f"{metric.metric}: reporting period is unknown."
            )

    if any(
        metric.period.period_type == "unknown"
        for metric in metrics
    ):
        return

    signatures = {
        _period_signature(metric)
        for metric in metrics
    }

    if len(signatures) > 1:
        errors.append(
            "Reporting periods are incompatible. "
            "All metrics must refer to the same reporting period."
        )


def _validate_companies(
    metrics: Sequence[FinancialMetric],
    errors: list[str],
) -> None:
    """Ensure all metrics belong to the same known company."""

    companies = []

    for metric in metrics:
        if not metric.company or not metric.company.strip():
            errors.append(
                f"{metric.metric}: company identity is unknown."
            )
        else:
            companies.append(
                metric.company.strip().casefold()
            )

    if (
        len(companies) == len(metrics)
        and len(set(companies)) > 1
    ):
        errors.append(
            "Company mismatch. Metrics belong to different companies."
        )


def _validate_currencies(
    metrics: Sequence[FinancialMetric],
    errors: list[str],
) -> None:
    """Ensure all metrics have the same known currency."""

    currencies = []

    for metric in metrics:
        if not metric.currency:
            errors.append(
                f"{metric.metric}: currency is unknown."
            )
        else:
            currencies.append(
                metric.currency.strip().upper()
            )

    if (
        len(currencies) == len(metrics)
        and len(set(currencies)) > 1
    ):
        errors.append(
            "Currency mismatch. Metrics use different currencies."
        )


def _validate_units(
    metrics: Sequence[FinancialMetric],
    errors: list[str],
) -> None:
    """Ensure metric values use compatible units."""

    units = [
        metric.unit.strip().casefold()
        for metric in metrics
    ]

    if len(set(units)) > 1:
        errors.append(
            "Unit mismatch. Metrics must use compatible units "
            "before they can be combined."
        )


def _validate_common_compatibility(
    metrics: Sequence[FinancialMetric],
    errors: list[str],
) -> None:
    """Check company, currency and unit compatibility."""

    _validate_companies(metrics, errors)
    _validate_currencies(metrics, errors)
    _validate_units(metrics, errors)


def _validate_average_balance_periods(
    metrics: Mapping[str, FinancialMetric],
    balance_names: tuple[str, str],
    errors: list[str],
) -> None:
    """
    Validate duration income against opening and closing
    instant balance-sheet values.
    """

    net_income = metrics["Net Income"]
    beginning_balance = metrics[balance_names[0]]
    ending_balance = metrics[balance_names[1]]

    income_period = net_income.period

    if income_period.period_type != "duration":
        errors.append(
            "Net Income must have a duration reporting period."
        )
        return

    if (
        beginning_balance.period.period_type != "instant"
        or ending_balance.period.period_type != "instant"
    ):
        errors.append(
            "Opening and closing balances must use instant periods."
        )
        return

    opening_date = beginning_balance.period.instant_date
    closing_date = ending_balance.period.instant_date

    if opening_date is None or closing_date is None:
        errors.append(
            "Opening and closing balance dates must be known."
        )
        return

    if (
        income_period.start_date is None
        or income_period.end_date is None
    ):
        errors.append(
            "Net Income reporting period dates must be known."
        )
        return

    if opening_date >= income_period.start_date:
        errors.append(
            "Opening balance must precede the income reporting period."
        )

    if closing_date != income_period.end_date:
        errors.append(
            "Closing balance date must match the end of the "
            "income reporting period."
        )

    if opening_date >= closing_date:
        errors.append(
            "Opening balance date must precede closing balance date."
        )


def validate_metric_set(
    metrics: Sequence[FinancialMetric],
    required_metrics: Sequence[str],
) -> ValidationResult:
    """
    Validate that required metrics exist and are compatible.

    Checks:
    - Required metric availability
    - Duplicate metric entries
    - Company consistency
    - Reporting-period compatibility
    - Currency compatibility
    - Unit compatibility
    """

    errors: list[str] = []
    indexed_metrics: dict[str, FinancialMetric] = {}

    for metric in metrics:
        canonical_name = _canonical_metric_name(metric.metric)
        key = canonical_name.casefold()

        if key in indexed_metrics:
            errors.append(
                f"Duplicate metric found: {canonical_name}."
            )
        else:
            indexed_metrics[key] = metric

    selected_metrics: dict[str, FinancialMetric] = {}

    for required_name in required_metrics:
        canonical_name = _canonical_metric_name(required_name)
        key = canonical_name.casefold()

        metric = indexed_metrics.get(key)

        if metric is None:
            errors.append(
                f"Required metric is missing: {canonical_name}."
            )
        else:
            selected_metrics[canonical_name] = metric

    if errors:
        return ValidationResult(
            is_valid=False,
            errors=tuple(errors),
            metrics=selected_metrics,
        )

    selected = list(selected_metrics.values())

    _validate_common_compatibility(selected, errors)
    _validate_periods(selected, errors)

    return ValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        metrics=selected_metrics,
    )


def validate_ratio_inputs(
    ratio_name: str,
    metrics: Sequence[FinancialMetric],
) -> ValidationResult:
    """Validate required inputs and period rules for a financial ratio."""

    dependencies = RATIO_DEPENDENCIES.get(ratio_name)

    if dependencies is None:
        return ValidationResult(
            is_valid=False,
            errors=(f"Unsupported ratio: {ratio_name}.",),
            metrics={},
        )

    indexed_metrics: dict[str, FinancialMetric] = {}
    errors: list[str] = []

    # Index metrics and detect duplicates.
    for metric in metrics:
        canonical_name = _canonical_metric_name(metric.metric)
        key = canonical_name.casefold()

        if key in indexed_metrics:
            errors.append(
                f"Duplicate metric found: {canonical_name}."
            )
        else:
            indexed_metrics[key] = metric

    # Find required dependencies.
    selected_metrics: dict[str, FinancialMetric] = {}

    for required_name in dependencies:
        canonical_name = _canonical_metric_name(required_name)
        metric = indexed_metrics.get(canonical_name.casefold())

        if metric is None:
            errors.append(
                f"Required metric is missing: {canonical_name}."
            )
        else:
            selected_metrics[canonical_name] = metric

    if errors:
        return ValidationResult(
            is_valid=False,
            errors=tuple(errors),
            metrics=selected_metrics,
        )

    selected = list(selected_metrics.values())

    # ROA: Net Income / Average Total Assets.
    if ratio_name == "return_on_assets":
        _validate_common_compatibility(selected, errors)

        _validate_average_balance_periods(
            selected_metrics,
            (
                "Beginning Total Assets",
                "Ending Total Assets",
            ),
            errors,
        )

    # ROE: Net Income / Average Total Equity.
    elif ratio_name == "return_on_equity":
        _validate_common_compatibility(selected, errors)

        _validate_average_balance_periods(
            selected_metrics,
            (
                "Beginning Total Equity",
                "Ending Total Equity",
            ),
            errors,
        )

    # Other ratios require matching reporting periods.
    else:
        _validate_common_compatibility(selected, errors)
        _validate_periods(selected, errors)

    return ValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        metrics=selected_metrics,
    )
