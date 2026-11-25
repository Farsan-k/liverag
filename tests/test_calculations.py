
from decimal import Decimal

import pytest

from app.analysis.calculations import (
    absolute_change,
    percentage_change,
    revenue_growth,
    profit_margin,
)


def test_absolute_change():
    assert absolute_change(150, 100) == Decimal("50")


def test_absolute_change_negative():
    assert absolute_change(80, 100) == Decimal("-20")


def test_percentage_change():
    assert percentage_change(150, 100) == Decimal("50")


def test_percentage_change_decrease():
    assert percentage_change(80, 100) == Decimal("-20")


def test_percentage_change_from_negative_baseline():
    assert percentage_change(-50, -100) == Decimal("50")


def test_percentage_change_zero_baseline():
    with pytest.raises(ZeroDivisionError):
        percentage_change(100, 0)


def test_revenue_growth():
    assert revenue_growth(150, 100) == Decimal("50")


def test_revenue_growth_decrease():
    assert revenue_growth(80, 100) == Decimal("-20")


def test_revenue_growth_negative_previous_revenue():
    with pytest.raises(ValueError):
        revenue_growth(100, -50)


def test_revenue_growth_zero_previous_revenue():
    with pytest.raises(ValueError):
        revenue_growth(100, 0)


def test_revenue_growth_negative_current_revenue():
    with pytest.raises(ValueError):
        revenue_growth(-100, 50)


def test_profit_margin():
    assert profit_margin(20, 100) == Decimal("20")


def test_profit_margin_with_loss():
    assert profit_margin(-20, 100) == Decimal("-20")


def test_profit_margin_zero_revenue():
    with pytest.raises(ValueError):
        profit_margin(20, 0)


def test_profit_margin_negative_revenue():
    with pytest.raises(ValueError):
        profit_margin(20, -100)


def test_decimal_precision():
    result = revenue_growth(
        Decimal("110.50"),
        Decimal("100.00"),
    )

    assert result == Decimal("10.50")


def test_invalid_numeric_input():
    with pytest.raises(ValueError):
        absolute_change("invalid", 100)


def test_nan_input():
    with pytest.raises(ValueError):
        absolute_change(Decimal("NaN"), 100)


def test_infinite_input():
    with pytest.raises(ValueError):
        absolute_change(Decimal("Infinity"), 100)


def test_boolean_input():
    with pytest.raises(TypeError):
        absolute_change(True, 100)
