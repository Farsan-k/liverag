
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any


SUPPORTED_FORMULAS = {
    "Net Profit Margin": "(Net Income / Revenue) × 100",
    "Revenue Growth": (
        "((Current Revenue - Previous Revenue) "
        "/ Previous Revenue) × 100"
    ),
}

TOLERANCE = Decimal("1e-20")


def _decimal(value: Any, field: str) -> Decimal:
    """Convert a value to a finite Decimal."""

    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric.")

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} is not a valid number.") from exc

    if not result.is_finite():
        raise ValueError(f"{field} must be finite.")

    return result


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} is missing or invalid.")

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid ISO date.") from exc


def _validate_input_provenance(
    metric: dict[str, Any],
) -> list[str]:
    errors = []

    source = metric.get("source")
    evidence = metric.get("evidence")

    if not isinstance(source, dict):
        return ["Input is missing source provenance."]

    if not source.get("source_type"):
        errors.append("Input is missing its source type.")

    if source.get("source_document_id") is None:
        errors.append("Input is missing its source document ID.")

    if not isinstance(evidence, dict):
        errors.append("Input is missing its evidence record.")

    if metric.get("dimensions"):
        errors.append(
            "Dimensional financial facts are not accepted "
            "for consolidated calculations."
        )

    return errors


def _validate_common_inputs(
    inputs: list[dict[str, Any]],
) -> list[str]:
    errors = []

    if len(inputs) != 2:
        return ["Exactly two financial inputs are required."]

    if not all(isinstance(item, dict) for item in inputs):
        return ["Financial inputs must be dictionaries."]

    companies = {
        str(item.get("company") or "").strip().casefold()
        for item in inputs
    }

    if "" in companies or len(companies) != 1:
        errors.append(
            "Inputs must belong to the same identified company."
        )

    currencies = {
        str(item.get("currency") or "").strip().upper()
        for item in inputs
    }

    if "" in currencies or len(currencies) != 1:
        errors.append(
            "Inputs must use the same identified currency."
        )

    units = {
        str(item.get("unit") or "").strip()
        for item in inputs
    }

    if "" in units or len(units) != 1:
        errors.append(
            "Inputs must use the same identified unit."
        )

    for item in inputs:
        errors.extend(_validate_input_provenance(item))

    return errors


def _validate_same_period(
    first: dict[str, Any],
    second: dict[str, Any],
) -> list[str]:
    errors = []

    first_period = first.get("period")
    second_period = second.get("period")

    if not isinstance(first_period, dict) or not isinstance(
        second_period, dict
    ):
        return ["Reporting period metadata is missing."]

    if first_period != second_period:
        errors.append(
            "Calculation inputs must belong to the same reporting period."
        )

    if first_period.get("period_type") != "duration":
        errors.append(
            "This calculation requires duration reporting periods."
        )

    return errors


def _verify_net_profit_margin(
    calculation: dict[str, Any],
) -> list[str]:
    errors = []

    inputs = calculation.get("inputs")

    if not isinstance(inputs, list) or len(inputs) != 2:
        return ["Net profit margin requires two financial inputs."]

    by_metric = {
        item.get("metric"): item
        for item in inputs
        if isinstance(item, dict)
    }

    net_income = by_metric.get("Net Income")
    revenue = by_metric.get("Revenue")

    if net_income is None or revenue is None:
        return [
            "Net profit margin requires Net Income and Revenue inputs."
        ]

    errors.extend(_validate_common_inputs(inputs))
    errors.extend(_validate_same_period(net_income, revenue))

    try:
        profit_value = _decimal(
            net_income.get("value"),
            "Net Income",
        )
        revenue_value = _decimal(
            revenue.get("value"),
            "Revenue",
        )

        if revenue_value <= 0:
            errors.append(
                "Revenue must be positive to calculate net profit margin."
            )
        else:
            expected = (
                profit_value / revenue_value
            ) * Decimal("100")

            reported = _decimal(
                calculation.get("value"),
                "Calculation result",
            )

            if abs(expected - reported) > TOLERANCE:
                errors.append(
                    "Reported net profit margin does not match "
                    "the independently verified result."
                )

    except ValueError as exc:
        errors.append(str(exc))

    return errors


def _verify_revenue_growth(
    calculation: dict[str, Any],
) -> list[str]:
    errors = []

    inputs = calculation.get("inputs")

    if not isinstance(inputs, list) or len(inputs) != 2:
        return ["Revenue growth requires two financial inputs."]

    # Analysis Agent serializes current revenue first.
    current, previous = inputs

    if not isinstance(current, dict) or not isinstance(previous, dict):
        return ["Revenue growth inputs are invalid."]

    if current.get("metric") != "Revenue":
        errors.append("Current input must be Revenue.")

    if previous.get("metric") != "Revenue":
        errors.append("Previous input must be Revenue.")

    errors.extend(_validate_common_inputs(inputs))

    try:
        current_period = current.get("period") or {}
        previous_period = previous.get("period") or {}

        if (
            current_period.get("period_type") != "duration"
            or previous_period.get("period_type") != "duration"
        ):
            errors.append(
                "Revenue growth requires duration reporting periods."
            )

        current_start = _parse_date(
            current_period.get("start_date"),
            "Current period start date",
        )
        current_end = _parse_date(
            current_period.get("end_date"),
            "Current period end date",
        )
        previous_start = _parse_date(
            previous_period.get("start_date"),
            "Previous period start date",
        )
        previous_end = _parse_date(
            previous_period.get("end_date"),
            "Previous period end date",
        )

        if current_start > current_end:
            errors.append("Current reporting period dates are invalid.")

        if previous_start > previous_end:
            errors.append("Previous reporting period dates are invalid.")

        current_duration = current_end - current_start
        previous_duration = previous_end - previous_start

        if abs(current_duration - previous_duration) > timedelta(days=1):
            errors.append(
                "Revenue growth requires comparable reporting periods."
            )

        if current_start != previous_end + timedelta(days=1):
            errors.append(
                "Revenue growth requires consecutive reporting periods."
            )

        if current_end <= previous_end:
            errors.append(
                "Current revenue must belong to a later reporting period."
            )

        current_value = _decimal(
            current.get("value"),
            "Current revenue",
        )
        previous_value = _decimal(
            previous.get("value"),
            "Previous revenue",
        )

        if current_value < 0:
            errors.append("Current revenue cannot be negative.")

        if previous_value <= 0:
            errors.append(
                "Previous revenue must be positive to calculate growth."
            )

        if previous_value > 0 and current_value >= 0:
            expected = (
                (current_value - previous_value) / previous_value
            ) * Decimal("100")

            reported = _decimal(
                calculation.get("value"),
                "Calculation result",
            )

            if abs(expected - reported) > TOLERANCE:
                errors.append(
                    "Reported revenue growth does not match "
                    "the independently verified result."
                )

    except ValueError as exc:
        errors.append(str(exc))

    return errors


def verify_analysis(
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """
    Independently verify Analysis Agent calculations.

    Returns an overall verification status, individual
    calculation results and verification errors.
    """

    if not isinstance(analysis, dict):
        raise TypeError("analysis must be a dictionary.")

    calculations = analysis.get("calculations", [])

    if not isinstance(calculations, list):
        raise TypeError("analysis.calculations must be a list.")

    if not calculations:
        return {
            "verified": False,
            "errors": [
                "No financial calculations were provided for verification."
            ],
            "calculations": [],
        }

    verified_calculations = []
    overall_errors = []

    for calculation in calculations:
        if not isinstance(calculation, dict):
            errors = ["Calculation entry must be a dictionary."]
            verified_calculations.append({
                "metric": "Unknown",
                "verified": False,
                "errors": errors,
            })
            overall_errors.extend(errors)
            continue

        metric = calculation.get("metric", "Unknown")
        errors = []

        if calculation.get("status") != "calculated":
            errors.append(
                "Calculation was not successfully completed."
            )

        expected_formula = SUPPORTED_FORMULAS.get(metric)

        if expected_formula is None:
            errors.append(
                f"Unsupported calculation metric: {metric}."
            )
        elif calculation.get("formula") != expected_formula:
            errors.append(
                "Calculation formula does not match the approved formula."
            )

        if calculation.get("unit") != "%":
            errors.append(
                "The calculation result must use percentage units."
            )

        if expected_formula is not None:
            if metric == "Net Profit Margin":
                errors.extend(
                    _verify_net_profit_margin(calculation)
                )

            elif metric == "Revenue Growth":
                errors.extend(
                    _verify_revenue_growth(calculation)
                )

        item_verified = len(errors) == 0

        verified_calculations.append({
            "metric": metric,
            "verified": item_verified,
            "errors": errors,
        })

        overall_errors.extend(
            f"{metric}: {error}"
            for error in errors
        )

    return {
        "verified": (
            bool(verified_calculations)
            and all(
                item["verified"]
                for item in verified_calculations
            )
        ),
        "errors": overall_errors,
        "calculations": verified_calculations,
    }
