
import pytest

from app.validation import has_matching_metric_period


def test_rejects_metric_from_wrong_month():
    context = (
        "Revenue was 500000 rupees in March 2026. "
        "Net profit was 123456 rupees in April 2026."
    )

    assert not has_matching_metric_period(
        "What was the net profit in March 2026?",
        context,
    )


def test_accepts_metric_from_requested_month():
    context = "Net profit was 123456 rupees in March 2026."

    assert has_matching_metric_period(
        "What was the net profit in March 2026?",
        context,
    )


def test_distinguishes_different_metrics_and_periods():
    context = (
        "Revenue was 500000 rupees in March 2026. "
        "Net profit was 123456 rupees in April 2026."
    )

    assert has_matching_metric_period(
        "What was the revenue in March 2026?",
        context,
    )

    assert not has_matching_metric_period(
        "What was the net profit in March 2026?",
        context,
    )


def test_rejects_wrong_year():
    context = "Net profit was 123456 rupees in March 2025."

    assert not has_matching_metric_period(
        "What was the net profit in March 2026?",
        context,
    )


def test_accepts_question_without_reporting_period():
    context = "Net profit was 123456 rupees in April 2026."

    assert has_matching_metric_period(
        "What was the net profit?",
        context,
    )





def test_accepts_reporting_period_in_separate_heading():
    context = (
        "Reporting period: March 2026. "
        "Net profit was 123456 rupees."
    )

    assert has_matching_metric_period(
        "What was the net profit in March 2026?",
        context,
    )




def test_rejects_metric_when_heading_has_wrong_period():
    context = (
        "Reporting period: April 2026. "
        "Net profit was 123456 rupees."
    )

    assert not has_matching_metric_period(
        "What was the net profit in March 2026?",
        context,
    )


def test_does_not_apply_previous_period_to_unrelated_metric():
    context = (
        "Revenue was 500000 rupees in March 2026. "
        "Net profit was 123456 rupees in April 2026."
    )

    assert not has_matching_metric_period(
        "What was the net profit in March 2026?",
        context,
    )






def test_accepts_net_income_alias_for_net_profit():
    question = "What was the net income in March 2026?"
    context = "Net profit was 123456 rupees in March 2026."

    assert has_matching_metric_period(question, context) is True


def test_rejects_net_income_from_wrong_period():
    question = "What was the net income in March 2026?"
    context = "Net profit was 123456 rupees in April 2026."

    assert has_matching_metric_period(question, context) is False


def test_accepts_net_sales_alias_for_revenue():
    question = "What were the net sales in March 2026?"
    context = "Revenue was 500000 rupees in March 2026."

    assert has_matching_metric_period(question, context) is True


def test_rejects_net_sales_from_wrong_period():
    question = "What were the net sales in March 2026?"
    context = "Revenue was 500000 rupees in April 2026."

    assert has_matching_metric_period(question, context) is False
