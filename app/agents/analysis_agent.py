
from __future__ import annotations

import re

from typing import Any

from app.agents.research_agent import ResearchPlan

from app.analysis.calculation_engine import (
    CalculationResult,
    calculate_net_profit_margin,
    calculate_revenue_growth,
)

from app.analysis.fact_selection import FactSelectionRequest

from app.analysis.query_service import (
    get_available_reporting_periods,
    resolve_fiscal_year_period,
    resolve_fiscal_quarter_period,
    resolve_metric_from_database,
)

from app.analysis.resolution import ResolutionResult


def _serialize_input(metric: Any) -> dict[str, Any]:
    """Convert a resolved financial metric into JSON-safe evidence."""

    return {
        "company": metric.company,
        "metric": metric.metric,
        "value": str(metric.value),
        "unit": metric.unit,
        "currency": metric.currency,
        "period": {
            "label": metric.period.label,
            "period_type": metric.period.period_type,
            "start_date": (
                metric.period.start_date.isoformat()
                if metric.period.start_date else None
            ),
            "end_date": (
                metric.period.end_date.isoformat()
                if metric.period.end_date else None
            ),
            "instant_date": (
                metric.period.instant_date.isoformat()
                if metric.period.instant_date else None
            ),
        },
        "source": metric.source.model_dump(mode="json"),
        "evidence": metric.evidence.model_dump(mode="json"),
        "dimensions": metric.dimensions,
    }


def _serialize_calculation(
    result: CalculationResult,
) -> dict[str, Any]:
    """Convert CalculationResult into a JSON-safe dictionary."""

    return {
        "metric": result.metric,
        "status": result.status,
        "value": (
            str(result.value)
            if result.value is not None else None
        ),
        "unit": result.unit,
        "formula": result.formula,
        "inputs": [
            _serialize_input(metric)
            for metric in result.inputs
        ],
        "errors": list(result.errors),
    }


def _blocked_result(
    metric: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "metric": metric,
        "status": "blocked",
        "value": None,
        "unit": "%",
        "formula": None,
        "inputs": [],
        "errors": [reason],
    }


def _resolve_fact(
    company: str,
    metric: str,
    period: dict[str, Any],
) -> ResolutionResult:
    """Resolve a consolidated fact for an exact reporting period."""

    request = FactSelectionRequest(
        company=company,
        metric=metric,
        period_start=period["start_date"].isoformat(),
        period_end=period["end_date"].isoformat(),
        consolidated_only=True,
    )

    return resolve_metric_from_database(request)


def _get_requested_periods(
    company: str,
    metric: str,
    requested_periods: list[str],
    period_scope: str | None = None,
) -> list[dict[str, Any]]:
    """
    Resolve explicitly requested annual or quarterly periods.

    Supported annual format:
        FY2026

    Supported quarterly formats:
        Q3 FY2026
        FY2026 Q3

    Quarterly periods require an explicit reporting scope:
        standalone
        ytd
    """

    periods = []

    quarter_pattern = re.compile(
        r"^(?:Q([1-4])\s*FY(\d{4})|FY(\d{4})\s*Q([1-4]))$",
        re.IGNORECASE,
    )

    for requested_period in requested_periods:
        normalized_period = requested_period.strip()

        quarter_match = quarter_pattern.fullmatch(
            normalized_period
        )

        if quarter_match:
            quarter = (
                quarter_match.group(1)
                or quarter_match.group(4)
            )

            fiscal_year = (
                quarter_match.group(2)
                or quarter_match.group(3)
            )

            if period_scope not in {"standalone", "ytd"}:
                raise ValueError(
                    f"Reporting scope must be explicitly specified "
                    f"for quarterly period {normalized_period}. "
                    "Choose standalone or ytd."
                )

            period = resolve_fiscal_quarter_period(
                company=company,
                metric=metric,
                fiscal_year=int(fiscal_year),
                fiscal_period=f"Q{quarter}",
                period_scope=period_scope,
            )

        else:
            period = resolve_fiscal_year_period(
                company=company,
                metric=metric,
                fiscal_year=normalized_period,
            )

        if period is None:
            raise ValueError(
                f"No reporting period found for "
                f"{normalized_period}."
            )

        periods.append(period)

    # Remove duplicate reporting periods.
    unique = {
        (
            period["start_date"],
            period["end_date"],
        ): period
        for period in periods
    }

    return sorted(
        unique.values(),
        key=lambda item: item["end_date"],
    )


def _get_latest_periods(
    company: str,
    metric: str,
    count: int,
) -> list[dict[str, Any]]:
    """Get the latest available consolidated reporting periods."""

    periods = get_available_reporting_periods(
        company=company,
        metric=metric,
    )

    if len(periods) < count:
        raise ValueError(
            f"Insufficient reporting periods for {metric}. "
            f"Required: {count}; available: {len(periods)}."
        )

    return sorted(
        periods[:count],
        key=lambda item: item["end_date"],
    )


def _get_growth_periods(
    company: str,
    requested_periods: list[str],
    period_scope: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Identify current and previous periods for revenue growth.

    Two explicitly requested periods are resolved directly.

    One requested period is compared with its immediately
    preceding matching reporting period.

    No requested periods means the latest two available periods.
    """

    if len(requested_periods) > 2:
        raise ValueError(
            "Revenue growth currently supports two reporting "
            "periods per calculation."
        )

    if len(requested_periods) == 2:
        periods = _get_requested_periods(
            company=company,
            metric="Revenue",
            requested_periods=requested_periods,
            period_scope=period_scope,
        )

    elif len(requested_periods) == 1:
        current = _get_requested_periods(
            company=company,
            metric="Revenue",
            requested_periods=requested_periods,
            period_scope=period_scope,
        )[0]

        available = get_available_reporting_periods(
            company,
            "Revenue",
        )

        previous_candidates = [
            period
            for period in available
            if (
                period["end_date"] < current["start_date"]
                and period["period_scope"] == current["period_scope"]
                and period["fiscal_period"] == current["fiscal_period"]
            )
        ]

        if not previous_candidates:
            raise ValueError(
                "No matching previous reporting period is "
                "available for revenue growth."
            )

        previous = max(
            previous_candidates,
            key=lambda item: item["end_date"],
        )

        periods = [previous, current]

    else:
        periods = _get_latest_periods(
            company,
            "Revenue",
            2,
        )

    if len(periods) != 2:
        raise ValueError(
            "Revenue growth requires exactly two reporting periods."
        )

    previous, current = periods

    # Prevent comparisons across different reporting scopes.
    if previous["period_scope"] != current["period_scope"]:
        raise ValueError(
            "Revenue growth cannot compare different reporting scopes."
        )

    # Quarterly growth must compare matching fiscal quarters.
    if previous["fiscal_period"] != current["fiscal_period"]:
        raise ValueError(
            "Quarterly revenue growth requires matching fiscal quarters."
        )

    return current, previous


def _calculate_net_profit_margin(
    company: str,
    requested_periods: list[str],
    period_scope: str | None = None,
) -> CalculationResult:
    """Calculate net profit margin for an annual or quarterly period."""

    if len(requested_periods) > 1:
        raise ValueError(
            "Net profit margin currently supports one reporting "
            "period per calculation."
        )

    if requested_periods:
        period = _get_requested_periods(
            company=company,
            metric="Revenue",
            requested_periods=requested_periods,
            period_scope=period_scope,
        )[0]

    else:
        period = _get_latest_periods(
            company,
            "Revenue",
            1,
        )[0]

    revenue = _resolve_fact(
        company,
        "Revenue",
        period,
    )

    net_income = _resolve_fact(
        company,
        "Net Income",
        period,
    )

    return calculate_net_profit_margin(
        net_income=net_income,
        revenue=revenue,
    )


def _calculate_revenue_growth(
    company: str,
    requested_periods: list[str],
    period_scope: str | None = None,
) -> CalculationResult:
    """Calculate revenue growth between two reporting periods."""

    current_period, previous_period = _get_growth_periods(
        company,
        requested_periods,
        period_scope,
    )

    current_revenue = _resolve_fact(
        company,
        "Revenue",
        current_period,
    )

    previous_revenue = _resolve_fact(
        company,
        "Revenue",
        previous_period,
    )

    return calculate_revenue_growth(
        current_revenue=current_revenue,
        previous_revenue=previous_revenue,
    )


def analyze_research_plan(
    plan: ResearchPlan,
) -> dict[str, Any]:
    """
    Execute supported deterministic financial calculations
    based on the Research Agent's structured plan.

    No LLM-generated financial arithmetic is used.
    """

    if not isinstance(plan, ResearchPlan):
        raise TypeError(
            "plan must be a ResearchPlan instance."
        )

    analysis = {
        "summary": "",
        "calculations": [],
        "comparisons": [],
        "trends": [],
        "insights": [],
        "limitations": [],
    }

    if not plan.requires_calculation:
        analysis["summary"] = (
            "The research plan does not require numerical calculations."
        )
        return analysis

    if not plan.company:
        analysis["limitations"].append(
            "A company must be identified before financial "
            "calculations can be performed."
        )
        return analysis

    try:
        if plan.analysis_type == "ratio_analysis":
            if "Net Profit Margin" not in plan.metrics:
                analysis["limitations"].append(
                    "The requested ratio is not currently supported."
                )
                return analysis

            result = _calculate_net_profit_margin(
                company=plan.company,
                requested_periods=plan.periods,
                period_scope=plan.period_scope,
            )

        elif plan.analysis_type == "growth_analysis":
            if "Revenue" not in plan.metrics:
                analysis["limitations"].append(
                    "Revenue growth is currently the only "
                    "supported growth calculation."
                )
                return analysis

            result = _calculate_revenue_growth(
                company=plan.company,
                requested_periods=plan.periods,
                period_scope=plan.period_scope,
            )

        else:
            analysis["limitations"].append(
                f"Calculation type '{plan.analysis_type}' "
                "is not currently supported by the Analysis Agent."
            )
            return analysis

        calculation = _serialize_calculation(result)

        analysis["calculations"].append(calculation)

        if result.is_calculated:
            analysis["summary"] = (
                f"{result.metric} calculated successfully."
            )
        else:
            analysis["limitations"].extend(
                result.errors
            )

        return analysis

    except (ValueError, TypeError) as exc:
        analysis["limitations"].append(str(exc))
        return analysis
