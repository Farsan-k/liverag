
from decimal import Decimal

import pytest

from app.analysis.ratios import (
    gross_profit_margin,
    operating_profit_margin,
    net_profit_margin,
    return_on_assets,
    return_on_equity,
    current_ratio,
    debt_to_equity_ratio,
)


def test_gross_profit_margin():
    assert gross_profit_margin(40, 100) == Decimal("40.0")


def test_operating_profit_margin():
    assert operating_profit_margin(20, 100) == Decimal("20.0")


def test_net_profit_margin():
    assert net_profit_margin(15, 100) == Decimal("15.00")


def test_net_profit_margin_with_loss():
    assert net_profit_margin(-10, 100) == Decimal("-10.0")


def test_return_on_assets():
    assert return_on_assets(20, 200) == Decimal("10.0")


def test_return_on_equity():
    assert return_on_equity(30, 150) == Decimal("20.0")


def test_current_ratio():
    assert current_ratio(200, 100) == Decimal("2")


def test_debt_to_equity_ratio():
    assert debt_to_equity_ratio(150, 100) == Decimal("1.5")


def test_current_ratio_zero_liabilities():
    with pytest.raises(ValueError):
        current_ratio(200, 0)


def test_return_on_assets_zero_assets():
    with pytest.raises(ValueError):
        return_on_assets(20, 0)


def test_return_on_equity_negative_equity():
    with pytest.raises(ValueError):
        return_on_equity(30, -100)


def test_debt_to_equity_negative_debt():
    with pytest.raises(ValueError):
        debt_to_equity_ratio(-50, 100)


def test_invalid_numeric_input():
    with pytest.raises(ValueError):
        current_ratio("invalid", 100)


def test_nan_input():
    with pytest.raises(ValueError):
        return_on_assets(Decimal("NaN"), 100)


def test_boolean_input():
    with pytest.raises(TypeError):
        current_ratio(True, 100)
