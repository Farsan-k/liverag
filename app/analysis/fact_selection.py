
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.analysis.metrics import normalize_metric_label
from app.analysis.schemas import FinancialMetric


@dataclass(frozen=True)
class FactSelectionRequest:
    """Criteria used to select a financial fact."""

    metric: str
    company: str | None = None

    # Date-based period selection
    period_start: str | None = None
    period_end: str | None = None
    instant_date: str | None = None

    # Fiscal-period selection
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    period_scope: str | None = None

    # Financial attributes
    currency: str | None = None
    unit: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)
    consolidated_only: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.metric, str) or not self.metric.strip():
            raise ValueError("Metric cannot be empty.")

        if self.company is not None and (
            not isinstance(self.company, str)
            or not self.company.strip()
        ):
            raise ValueError("Company cannot be empty.")

        if self.period_start and self.instant_date:
            raise ValueError(
                "Specify either a duration period or an instant date."
            )

        if bool(self.period_start) != bool(self.period_end):
            raise ValueError(
                "Both period_start and period_end must be provided."
            )

        if self.instant_date and (
            self.period_start or self.period_end
        ):
            raise ValueError(
                "Instant date cannot be combined with duration dates."
            )

        # Fiscal-period selection must be fully specified.
        fiscal_fields = (
            self.fiscal_year,
            self.fiscal_period,
            self.period_scope,
        )

        if any(value is not None for value in fiscal_fields):
            if any(value is None for value in fiscal_fields):
                raise ValueError(
                    "Fiscal year, fiscal period, and period scope "
                    "must be provided together."
                )

            if (
                isinstance(self.fiscal_year, bool)
                or not isinstance(self.fiscal_year, int)
                or not 1900 <= self.fiscal_year <= 2200
            ):
                raise ValueError("Invalid fiscal year.")

            if not isinstance(self.fiscal_period, str):
                raise ValueError("Invalid fiscal period.")

            if not isinstance(self.period_scope, str):
                raise ValueError("Invalid period scope.")

            fiscal_period = self.fiscal_period.upper().strip()
            period_scope = self.period_scope.lower().strip()

            if fiscal_period not in {"Q1", "Q2", "Q3", "Q4", "FY"}:
                raise ValueError("Invalid fiscal period.")

            if period_scope not in {
                "standalone",
                "ytd",
                "annual",
            }:
                raise ValueError("Invalid period scope.")

            if fiscal_period == "FY" and period_scope != "annual":
                raise ValueError(
                    "FY reporting periods must use annual scope."
                )

            if fiscal_period != "FY" and period_scope == "annual":
                raise ValueError(
                    "Quarterly reporting periods cannot use annual scope."
                )

            object.__setattr__(
                self,
                "fiscal_period",
                fiscal_period,
            )

            object.__setattr__(
                self,
                "period_scope",
                period_scope,
            )


@dataclass(frozen=True)
class FactSelectionResult:
    """Selected financial fact and selection diagnostics."""

    selected: FinancialMetric | None
    candidates: tuple[FinancialMetric, ...]
    rejected_count: int
    reason: str
    is_ambiguous: bool = False
    duplicate_sources: tuple[FinancialMetric, ...] = ()


def _normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _same_metric(
    actual: str,
    requested: str,
) -> bool:
    actual_normalized = normalize_metric_label(actual)
    requested_normalized = normalize_metric_label(requested)

    if actual_normalized and requested_normalized:
        return actual_normalized == requested_normalized

    return _normalize_name(actual) == _normalize_name(requested)


def _same_company(
    actual: str | None,
    requested: str | None,
) -> bool:
    """
    Check whether the actual company matches the requested company.

    If no company is requested, accept all companies.
    If a company is requested but the actual company is missing,
    reject that metric.
    """

    if requested is None:
        return True

    if actual is None:
        return False

    return _normalize_name(actual) == _normalize_name(requested)


def _same_period(
    metric: FinancialMetric,
    request: FactSelectionRequest,
) -> bool:
    """
    Match date-based and fiscal reporting-period criteria.

    All supplied period criteria must match.
    """

    period = metric.period

    # Match explicit instant date.
    if request.instant_date:
        if not (
            period.period_type == "instant"
            and period.instant_date is not None
            and period.instant_date.isoformat() == request.instant_date
        ):
            return False

    # Match explicit duration dates.
    if request.period_start and request.period_end:
        if not (
            period.period_type == "duration"
            and period.start_date is not None
            and period.end_date is not None
            and period.start_date.isoformat() == request.period_start
            and period.end_date.isoformat() == request.period_end
        ):
            return False

    # Match fiscal reporting identity.
    if request.fiscal_year is not None:
        if period.fiscal_year != request.fiscal_year:
            return False

        if period.fiscal_period != request.fiscal_period:
            return False

        if period.period_scope != request.period_scope:
            return False

    return True


def _matches_dimensions(
    metric: FinancialMetric,
    requested_dimensions: dict[str, str],
) -> bool:
    return all(
        metric.dimensions.get(axis) == member
        for axis, member in requested_dimensions.items()
    )


def _is_consolidated(metric: FinancialMetric) -> bool:
    return not metric.dimensions


def _matches_unit(
    metric: FinancialMetric,
    request: FactSelectionRequest,
) -> bool:
    if request.currency:
        if (metric.currency or "").upper() != request.currency.upper():
            return False

    if request.unit:
        if metric.unit != request.unit:
            return False

    return True


def _same_fact_value(
    first: FinancialMetric,
    second: FinancialMetric,
) -> bool:
    return (
        first.company == second.company
        and first.metric == second.metric
        and first.value == second.value
        and first.unit == second.unit
        and first.currency == second.currency
        and first.period == second.period
        and first.dimensions == second.dimensions
    )


def _deduplicate(
    metrics: Iterable[FinancialMetric],
) -> tuple[
    list[FinancialMetric],
    tuple[FinancialMetric, ...],
]:
    """Group equivalent facts while preserving duplicate source records."""

    unique: list[FinancialMetric] = []
    duplicates: list[FinancialMetric] = []

    for metric in metrics:
        existing = next(
            (
                candidate
                for candidate in unique
                if _same_fact_value(candidate, metric)
            ),
            None,
        )

        if existing is None:
            unique.append(metric)
        else:
            duplicates.append(metric)

    return unique, tuple(duplicates)


def select_financial_fact(
    metrics: Iterable[FinancialMetric],
    request: FactSelectionRequest,
) -> FactSelectionResult:
    """
    Select a financial fact using deterministic criteria.

    Conflicting facts are returned as ambiguous instead of
    arbitrarily selecting one.
    """

    all_metrics = list(metrics)

    matching = [
        metric
        for metric in all_metrics
        if _same_metric(metric.metric, request.metric)
        and _same_company(metric.company, request.company)
        and _same_period(metric, request)
        and _matches_dimensions(metric, request.dimensions)
        and _matches_unit(metric, request)
    ]

    rejected_count = len(all_metrics) - len(matching)

    if not matching:
        return FactSelectionResult(
            selected=None,
            candidates=(),
            rejected_count=rejected_count,
            reason="No facts matched the requested criteria.",
        )

    if request.dimensions:
        candidates = matching

    elif request.consolidated_only:
        candidates = [
            metric
            for metric in matching
            if _is_consolidated(metric)
        ]

        if not candidates:
            return FactSelectionResult(
                selected=None,
                candidates=(),
                rejected_count=rejected_count,
                reason="No consolidated fact was found.",
            )

    else:
        candidates = matching

    unique_candidates, duplicate_sources = _deduplicate(candidates)

    rejected_count += len(duplicate_sources)

    if len(unique_candidates) == 1:
        return FactSelectionResult(
            selected=unique_candidates[0],
            candidates=tuple(unique_candidates),
            rejected_count=rejected_count,
            reason="One unique fact matched the requested criteria.",
            duplicate_sources=duplicate_sources,
        )

    return FactSelectionResult(
        selected=None,
        candidates=tuple(unique_candidates),
        rejected_count=rejected_count,
        reason=(
            "Multiple conflicting facts matched. "
            "Manual resolution required."
        ),
        is_ambiguous=True,
        duplicate_sources=duplicate_sources,
    )
