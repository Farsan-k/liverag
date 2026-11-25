
from __future__ import annotations

import re

from dataclasses import replace
from datetime import date
from typing import Any

from app.database import SessionLocal
from app.crud import get_financial_metrics
from app.company_identity import resolve_company

from app.analysis.schemas import FinancialMetric
from app.analysis.fact_selection import FactSelectionRequest
from app.analysis.resolution import (
    ResolutionResult,
    resolve_financial_fact,
)


def _resolve_company_identity(
    company_name: str,
) -> dict[str, Any]:
    """
    Resolve a company name or alias into a verified company ID.

    Returns the company ID and canonical name only when
    the identity resolver confirms a unique match.
    """

    if not isinstance(company_name, str) or not company_name.strip():
        return {
            "status": "not_found",
            "company_id": None,
            "canonical_name": None,
            "reason": "A valid company name is required.",
        }

    with SessionLocal() as session:
        result = resolve_company(
            db=session,
            name=company_name,
        )

        status = result["status"]
        company = result.get("company")

        if status != "resolved" or company is None:
            return {
                "status": status,
                "company_id": None,
                "canonical_name": None,
                "reason": (
                    f"Company identity resolution returned: {status}."
                ),
            }

        return {
            "status": "resolved",
            "company_id": company.id,
            "canonical_name": company.canonical_name,
            "reason": "Company identity successfully resolved.",
        }



def _database_record_to_metric(
    record: dict[str, Any],
) -> FinancialMetric:
    """
    Convert a persisted financial metric record into
    a validated FinancialMetric object.
    """

    provenance = record.get("provenance") or {}

    period = {
        "label": record.get("period_label"),
        "period_type": record.get("period_type", "unknown"),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
        "instant_date": record.get("instant_date"),

        # Fiscal reporting identity
        "fiscal_year": record.get("fiscal_year"),
        "fiscal_period": record.get("fiscal_period"),
        "period_scope": record.get("period_scope", "unknown"),
    }

    return FinancialMetric.model_validate(
        {
            "company": record.get("company"),
            "metric": record["metric"],
            "value": record["value"],
            "unit": record["unit"],
            "currency": record.get("currency"),
            "period": period,
            "source": provenance,
            "evidence": record.get("evidence") or {},
            "dimensions": record.get("dimensions") or {},
            "confidence": record.get("confidence"),
        }
    )



def _company_resolution_failure(
    status: str,
    reason: str,
) -> ResolutionResult:
    """
    Convert company identity resolution failures into
    the existing financial fact resolution interface.
    """

    if status == "ambiguous":
        resolution_status = "ambiguous"
    else:
        resolution_status = "not_found"

    return ResolutionResult(
        status=resolution_status,
        selected=None,
        candidates=(),
        duplicate_sources=(),
        rejected_count=0,
        reason=reason,
    )


def resolve_metric_from_database(
    request: FactSelectionRequest,
) -> ResolutionResult:
    """
    Retrieve persisted financial metrics and resolve
    the requested financial fact deterministically.

    Company aliases are resolved to a verified company ID
    before database retrieval.
    """

    if not isinstance(request, FactSelectionRequest):
        raise TypeError(
            "request must be a FactSelectionRequest"
        )

    # Resolve company identity when a company is specified.
    if request.company is not None:
        identity = _resolve_company_identity(
            request.company
        )

        if identity["status"] != "resolved":
            return _company_resolution_failure(
                status=identity["status"],
                reason=identity["reason"],
            )

        company_id = identity["company_id"]
        canonical_name = identity["canonical_name"]

        # Preserve all existing selection criteria while
        # replacing the alias with the canonical company name.
        selection_request = replace(
            request,
            company=canonical_name,
        )

        records = get_financial_metrics(
            company_id=company_id,
            metric=request.metric,
        )

    else:
        # Preserve support for requests without a company filter.
        selection_request = request

        records = get_financial_metrics(
            metric=request.metric,
        )

    metrics = [
        _database_record_to_metric(record)
        for record in records
    ]

    return resolve_financial_fact(
        metrics=metrics,
        request=selection_request,
    )



def get_available_reporting_periods(
    company: str,
    metric: str,
) -> list[dict[str, Any]]:
    """
    Return unique consolidated duration periods available
    for a verified company and financial metric.

    Includes fiscal reporting identity and period scope.
    """

    identity = _resolve_company_identity(company)

    if identity["status"] == "not_found":
        return []

    if identity["status"] != "resolved":
        raise ValueError(
            "Company identity could not be resolved safely: "
            f"{identity['reason']}"
        )

    records = get_financial_metrics(
        company_id=identity["company_id"],
        metric=metric,
    )

    periods = {}

    for record in records:
        # Ignore segment and dimensional facts.
        if record.get("dimensions"):
            continue

        if record.get("period_type") != "duration":
            continue

        start_date = record.get("start_date")
        end_date = record.get("end_date")

        if not start_date or not end_date:
            continue

        fiscal_year = record.get("fiscal_year")
        fiscal_period = record.get("fiscal_period")
        period_scope = record.get("period_scope", "unknown")

        key = (
            start_date,
            end_date,
            fiscal_year,
            fiscal_period,
            period_scope,
        )

        periods[key] = {
            "start_date": start_date,
            "end_date": end_date,
            "period_label": record.get("period_label"),
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "period_scope": period_scope,
        }

    return sorted(
        periods.values(),
        key=lambda item: item["end_date"],
        reverse=True,
    )




def resolve_fiscal_year_period(
    company: str,
    metric: str,
    fiscal_year: str,
) -> dict | None:
    """
    Resolve an annual fiscal-year reporting period.

    Resolution priority:
    1. Explicit annual records (FY / annual).
    2. Legacy records with unknown fiscal metadata whose
       reporting duration is approximately one year.

    Quarterly standalone and YTD records are never treated
    as annual reporting periods.

    Returns None if no annual period exists.
    Raises ValueError if multiple annual periods match.
    """

    match = re.fullmatch(
        r"FY[\s-]?(\d{4})",
        fiscal_year.strip(),
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            f"Invalid fiscal year format: {fiscal_year}"
        )

    requested_year = int(match.group(1))

    periods = get_available_reporting_periods(
        company=company,
        metric=metric,
    )

    # First, identify records ending in the requested year.
    year_periods = [
        period
        for period in periods
        if period["end_date"].year == requested_year
    ]

    if not year_periods:
        return None

    # Prefer records explicitly identified as annual.
    explicit_annual = [
        period
        for period in year_periods
        if (
            period["fiscal_period"] == "FY"
            or period["period_scope"] == "annual"
        )
    ]

    if len(explicit_annual) == 1:
        return explicit_annual[0]

    if len(explicit_annual) > 1:
        raise ValueError(
            f"Multiple annual reporting periods found "
            f"for {fiscal_year}."
        )

    # Legacy records may not have fiscal_year or fiscal_period
    # populated. Identify them using their duration.
    legacy_annual = []

    for period in year_periods:
        fiscal_period = period["fiscal_period"]
        period_scope = period["period_scope"]

        # Do not interpret identified quarterly records
        # as annual records.
        if fiscal_period not in (None, "FY"):
            continue

        if period_scope not in (None, "unknown"):
            continue

        start_date = period["start_date"]
        end_date = period["end_date"]

        duration_days = (
            end_date - start_date
        ).days + 1

        # Allow 350–380 days to accommodate fiscal calendars
        # and 52/53-week reporting years.
        if 350 <= duration_days <= 380:
            legacy_annual.append(period)

    if len(legacy_annual) == 1:
        return legacy_annual[0]

    if len(legacy_annual) > 1:
        raise ValueError(
            f"Multiple annual reporting periods found "
            f"for {fiscal_year}."
        )

    return None






def resolve_fiscal_quarter_period(
    company: str,
    metric: str,
    fiscal_year: int,
    fiscal_period: str,
    period_scope: str = "standalone",
) -> dict[str, Any] | None:
    """
    Resolve a specific fiscal quarter and reporting scope.

    Examples:
        FY2026 Q3 standalone
        FY2026 Q3 YTD

    Returns None if no matching period exists.
    Raises ValueError if multiple periods match.
    """

    if not isinstance(fiscal_year, int) or not 1900 <= fiscal_year <= 2200:
        raise ValueError("Invalid fiscal year.")

    fiscal_period = fiscal_period.upper().strip()
    period_scope = period_scope.lower().strip()

    if fiscal_period not in {"Q1", "Q2", "Q3", "Q4"}:
        raise ValueError(
            "Fiscal period must be Q1, Q2, Q3, or Q4."
        )

    if period_scope not in {"standalone", "ytd"}:
        raise ValueError(
            "Period scope must be 'standalone' or 'ytd'."
        )

    periods = get_available_reporting_periods(
        company=company,
        metric=metric,
    )

    matches = [
        period
        for period in periods
        if (
            period["fiscal_year"] == fiscal_year
            and period["fiscal_period"] == fiscal_period
            and period["period_scope"] == period_scope
        )
    ]

    if not matches:
        return None

    if len(matches) > 1:
        raise ValueError(
            f"Multiple reporting periods found for "
            f"FY{fiscal_year} {fiscal_period} ({period_scope})."
        )

    return matches[0]
