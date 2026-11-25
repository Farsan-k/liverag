
from decimal import Decimal
from typing import TypeAlias

from app.analysis.calculations import profit_margin


NumericInput: TypeAlias = Decimal | int | str


def _to_decimal(value: NumericInput, name: str) -> Decimal:
    """Convert a numeric input into a finite Decimal."""

    if isinstance(value, bool):
        raise TypeError(f"{name} must be numeric.")

    try:
        result = Decimal(str(value))
    except Exception as error:
        raise ValueError(f"{name} must be a valid number.") from error

    if not result.is_finite():
        raise ValueError(f"{name} must be finite.")

    return result


def _validate_same_currency(
    numerator_currency: str,
    denominator_currency: str,
) -> None:
    """Ensure monetary values use the same currency."""

    if numerator_currency.upper() != denominator_currency.upper():
        raise ValueError("Financial values must use the same currency.")


def _validate_positive_denominator(
    value: Decimal,
    name: str,
) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def gross_profit_margin(
    gross_profit: NumericInput,
    revenue: NumericInput,
) -> Decimal:
    """Gross Profit / Revenue * 100."""

    return profit_margin(gross_profit, revenue)


def operating_profit_margin(
    operating_income: NumericInput,
    revenue: NumericInput,
) -> Decimal:
    """Operating Income / Revenue * 100."""

    return profit_margin(operating_income, revenue)


def net_profit_margin(
    net_income: NumericInput,
    revenue: NumericInput,
) -> Decimal:
    """Net Income / Revenue * 100."""

    return profit_margin(net_income, revenue)


def return_on_assets(
    net_income: NumericInput,
    total_assets: NumericInput,
) -> Decimal:
    """Net Income / Total Assets * 100."""

    income = _to_decimal(net_income, "net_income")
    assets = _to_decimal(total_assets, "total_assets")

    _validate_positive_denominator(assets, "total_assets")

    return (income / assets) * Decimal("100")


def return_on_equity(
    net_income: NumericInput,
    total_equity: NumericInput,
) -> Decimal:
    """Net Income / Total Equity * 100."""

    income = _to_decimal(net_income, "net_income")
    equity = _to_decimal(total_equity, "total_equity")

    _validate_positive_denominator(equity, "total_equity")

    return (income / equity) * Decimal("100")


def current_ratio(
    current_assets: NumericInput,
    current_liabilities: NumericInput,
) -> Decimal:
    """Current Assets / Current Liabilities."""

    assets = _to_decimal(current_assets, "current_assets")
    liabilities = _to_decimal(
        current_liabilities,
        "current_liabilities",
    )

    _validate_positive_denominator(
        liabilities,
        "current_liabilities",
    )

    if assets < 0:
        raise ValueError("Current assets cannot be negative.")

    return assets / liabilities


def debt_to_equity_ratio(
    total_debt: NumericInput,
    total_equity: NumericInput,
) -> Decimal:
    """Total Debt / Total Equity."""

    debt = _to_decimal(total_debt, "total_debt")
    equity = _to_decimal(total_equity, "total_equity")

    _validate_positive_denominator(equity, "total_equity")

    if debt < 0:
        raise ValueError("Total debt cannot be negative.")

    return debt / equity
