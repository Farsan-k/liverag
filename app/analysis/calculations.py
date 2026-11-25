
from decimal import Decimal, InvalidOperation
from typing import TypeAlias


NumericInput: TypeAlias = Decimal | int | str


def _to_decimal(value: NumericInput, name: str) -> Decimal:
    """Convert an input into a finite Decimal value."""

    if isinstance(value, bool):
        raise TypeError(f"{name} must be a numeric value.")

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError(
            f"{name} must be a valid numeric value."
        ) from error

    if not result.is_finite():
        raise ValueError(f"{name} must be finite.")

    return result


def absolute_change(
    current_value: NumericInput,
    previous_value: NumericInput,
) -> Decimal:
    """
    Calculate the absolute difference between two values.

    Formula:
        Current value - Previous value
    """

    current = _to_decimal(current_value, "current_value")
    previous = _to_decimal(previous_value, "previous_value")

    return current - previous


def percentage_change(
    current_value: NumericInput,
    previous_value: NumericInput,
) -> Decimal:
    """
    Calculate percentage change between two values.

    Formula:
        ((Current - Previous) / abs(Previous)) * 100

    Uses the absolute previous value as the denominator,
    allowing mathematically defined changes from negative values.

    A zero previous value is not supported.
    """

    current = _to_decimal(current_value, "current_value")
    previous = _to_decimal(previous_value, "previous_value")

    if previous == 0:
        raise ZeroDivisionError(
            "Percentage change is undefined when previous_value is zero."
        )

    change = current - previous

    return (change / abs(previous)) * Decimal("100")


def revenue_growth(
    current_revenue: NumericInput,
    previous_revenue: NumericInput,
) -> Decimal:
    """
    Calculate revenue growth percentage.

    Formula:
        ((Current Revenue - Previous Revenue)
        / Previous Revenue) * 100

    Revenue growth requires a positive previous-period revenue.
    """

    current = _to_decimal(current_revenue, "current_revenue")
    previous = _to_decimal(previous_revenue, "previous_revenue")

    if current < 0:
        raise ValueError("Current revenue cannot be negative.")

    if previous <= 0:
        raise ValueError(
            "Previous revenue must be positive to calculate revenue growth."
        )

    return (
        (current - previous) / previous
    ) * Decimal("100")


def profit_margin(
    profit: NumericInput,
    revenue: NumericInput,
) -> Decimal:
    """
    Calculate profit margin percentage.

    Formula:
        (Profit / Revenue) * 100

    Negative profit is allowed because companies can report losses.
    Revenue must be positive.
    """

    profit_value = _to_decimal(profit, "profit")
    revenue_value = _to_decimal(revenue, "revenue")

    if revenue_value <= 0:
        raise ValueError(
            "Revenue must be positive to calculate profit margin."
        )

    return (
        profit_value / revenue_value
    ) * Decimal("100")
