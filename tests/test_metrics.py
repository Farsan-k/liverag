
import pytest

from app.analysis.metrics import (
    get_metric_label,
    normalize_metric_label,
)


@pytest.mark.parametrize(
    "label, expected",
    [
        ("Revenue", "Revenue"),
        ("Total Revenue", "Revenue"),
        ("Revenues", "Revenue"),
        ("Net Sales", "Revenue"),
        ("Profit After Tax", "Net Income"),
        ("Net Profit", "Net Income"),
        ("Operating Profit", "Operating Income"),
        ("Gross Profit", "Gross Profit"),
        ("Operating Cash Flow", "Operating Cash Flow"),
        ("Total Assets", "Total Assets"),
        ("Capital Expenditure", "Capital Expenditure"),
    ],
)
def test_metric_alias_normalization(label, expected):
    assert normalize_metric_label(label) == expected


def test_unknown_metric_returns_none():
    assert normalize_metric_label("Customer Acquisition Cost") is None


def test_unknown_metric_label_is_preserved():
    label = "Customer Acquisition Cost"

    assert get_metric_label(label) == label


def test_empty_metric_returns_none():
    assert normalize_metric_label("") is None


def test_whitespace_metric_returns_none():
    assert normalize_metric_label("   ") is None


def test_metric_normalization_ignores_case():
    assert normalize_metric_label("TOTAL REVENUE") == "Revenue"


def test_metric_normalization_handles_extra_spaces():
    assert normalize_metric_label("  Total   Revenue  ") == "Revenue"


def test_non_string_metric_raises_type_error():
    with pytest.raises(TypeError):
        normalize_metric_label(123)
