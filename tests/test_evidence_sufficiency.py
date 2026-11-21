
import pytest

from app.validation import requires_metric_amount, has_matching_metric_category_amount


@pytest.mark.parametrize(
    "question",
    [
        "What was Apple's iPhone revenue amount?",
        "How much revenue did Apple generate?",
        "What was the total amount of net profit?",
        "What is the value of Apple's total assets?",
    ],
)
def test_detects_amount_questions(question):
    assert requires_metric_amount(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "What drove Apple's revenue growth?",
        "Which products contributed to growth?",
        "How did Apple's earnings perform?",
        "What is Apple's growth outlook?",
    ],
)
def test_does_not_require_amount_for_descriptive_questions(question):
    assert requires_metric_amount(question) is False


@pytest.mark.parametrize(
    "question, context",
    [
        (
            "What was Apple's iPhone revenue amount?",
            "Apple revenue was $100 billion. "
            "iPhone sales contributed to growth."
        ),
        (
            "How much revenue came from services?",
            "Apple reported total revenue of $100 billion. "
            "Services contributed to growth."
        ),
    ],
)
def test_rejects_amount_from_wrong_category(question, context):
    assert has_matching_metric_category_amount(question, context) is False


@pytest.mark.parametrize(
    "question, context",
    [
        (
            "What was Apple's iPhone revenue amount?",
            "iPhone revenue was $50 billion. "
            "Total Apple revenue was $100 billion."
        ),
        (
            "How much revenue came from services?",
            "Services revenue was $25 billion. "
            "Total Apple revenue was $100 billion."
        ),
    ],
)
def test_accepts_category_specific_amount(question, context):
    assert has_matching_metric_category_amount(question, context) is True


@pytest.mark.parametrize(
    "question, context",
    [
        (
            "What was Apple's Mac revenue amount?",
            "Mac revenue reached $30 billion."
        ),
        (
            "What was Apple's China revenue amount?",
            "Revenue in Greater China was $18 billion."
        ),
        (
            "What was Apple's Europe revenue amount?",
            "Europe revenue increased to $25 billion."
        ),
    ],
)
def test_supports_multiple_category_types(question, context):
    assert has_matching_metric_category_amount(question, context) is True


@pytest.mark.parametrize(
    "question, context",
    [
        (
            "What was Apple's iPhone revenue amount?",
            "iPhone sales increased significantly."
        ),
        (
            "How much revenue came from services?",
            "Services revenue increased by 15%."
        ),
    ],
)
def test_rejects_growth_percentage_as_revenue_amount(question, context):
    assert has_matching_metric_category_amount(question, context) is False


@pytest.mark.parametrize(
    "question, context",
    [
        (
            "What was Apple's iPhone revenue amount?",
            "iPhone revenue increased by 15% to 50 units."
        ),
        (
            "How much revenue came from services?",
            "Services revenue reached 25 products."
        ),
        (
            "What was Apple's Mac revenue amount?",
            "Mac revenue increased by 10% across 30 markets."
        ),
    ],
)
def test_rejects_non_monetary_numbers_as_revenue_amount(
    question,
    context,
):
    assert has_matching_metric_category_amount(question, context) is False


@pytest.mark.parametrize(
    "question, context",
    [
        (
            "What was Apple's iPhone revenue amount?",
            "iPhone revenue was $50 billion."
        ),
        (
            "How much revenue came from services?",
            "Services revenue was 25 million USD."
        ),
        (
            "What was Apple's Mac revenue amount?",
            "Mac revenue reached ₹30 crore."
        ),
    ],
)
def test_accepts_monetary_revenue_amounts(question, context):
    assert has_matching_metric_category_amount(question, context) is True


def test_multiple_requested_categories_require_amount_for_each():
    question = "What was the revenue of iPhone and Mac?"

    context = (
        "iPhone revenue was $50 billion. "
        "Mac revenue increased by 15%."
    )

    assert not has_matching_metric_category_amount(
        question,
        context,
    )

def test_multiple_metrics_in_separate_sentences_are_accepted():
    question = "What were iPhone revenue and operating profit?"
    context = (
        "iPhone revenue was $50 billion. "
        "iPhone operating profit was $10 billion."
    )

    assert has_matching_metric_category_amount(question, context)


def test_descriptive_question_with_explicit_amount_requires_amount():
    question = "How did iPhone revenue perform, and what was the amount?"

    assert requires_metric_amount(question) is True


def test_multiple_categories_with_different_metrics_require_matching_evidence():
    question = "What were iPhone revenue and Mac operating profit?"

    context = (
        "iPhone revenue was $50 billion. "
        "Mac revenue was $30 billion."
    )

    assert not has_matching_metric_category_amount(
        question,
        context,
    )


def test_accepts_multiple_categories_with_matching_metrics():
    question = "What were iPhone revenue and Mac operating profit?"

    context = (
        "iPhone revenue was $50 billion. "
        "Mac operating profit was $10 billion."
    )

    assert has_matching_metric_category_amount(
        question,
        context,
    )
