
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ask_returns_fallback_when_no_results():
    with patch("app.main.search_embeddings", return_value=[]) as mock_search:
        response = client.post(
            "/ask",
            json={
                "question": "What was net profit in April 2026?",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == (
        "I do not have enough information to answer this question."
    )
    assert body["sources"] == []
    mock_search.assert_called_once()


def test_ask_does_not_call_llm_when_no_results():
    with (
        patch("app.main.search_embeddings", return_value=[]),
        patch("app.main.generate_answer") as mock_generate,
    ):
        response = client.post(
            "/ask",
            json={
                "question": "What was net profit in April 2026?",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    mock_generate.assert_not_called()



def test_ask_does_not_invent_answer_for_mismatched_evidence():
    march_revenue = (
        "The company recorded revenue of 500000 rupees "
        "in March 2026."
    )

    fake_result = type(
        "FakeResult",
        (),
        {
            "id": 101,
            "score": 0.75,
            "payload": {
                "document_id": 55,
                "text": march_revenue,
            },
        },
    )()

    with (
        patch(
            "app.main.search_embeddings",
            return_value=[fake_result],
        ),
        patch(
            "app.main.generate_answer",
            return_value=(
                "The net profit was 75000 rupees in April 2026."
            ),
        ) as mock_generate,
    ):
        response = client.post(
            "/ask",
            json={
                "question": "What was the net profit in April 2026?",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "I do not have enough information to answer this question."
    )
    mock_generate.assert_not_called()



def test_ask_rejects_mismatched_metric():
    revenue_result = type(
        "FakeResult",
        (),
        {
            "id": 102,
            "score": 0.80,
            "payload": {
                "document_id": 55,
                "text": (
                    "The company recorded revenue of "
                    "987654 rupees in March 2026."
                ),
            },
        },
    )()

    with (
        patch(
            "app.main.search_embeddings",
            return_value=[revenue_result],
        ),
        patch("app.main.generate_answer") as mock_generate,
    ):
        response = client.post(
            "/ask",
            json={
                "question": (
                    "What was the net profit in March 2026?"
                ),
                "limit": 3,
            },
        )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "I do not have enough information to answer this question."
    )
    assert response.json()["sources"] == []
    mock_generate.assert_not_called()



def test_ask_returns_answer_when_evidence_matches():
    revenue_result = type(
        "FakeResult",
        (),
        {
            "id": 41,
            "score": 0.57,
            "payload": {
                "document_id": 55,
                "text": (
                    "Finova synchronization test: monthly revenue "
                    "was 987654 rupees in March 2026. "
                    "Updated version: net profit was 123456 rupees "
                    "in March 2026."
                ),
            },
        },
    )()

    with (
        patch(
            "app.main.search_embeddings",
            return_value=[revenue_result],
        ),
        patch(
            "app.main.generate_answer",
            return_value="987654 rupees",
        ) as mock_generate,
    ):
        response = client.post(
            "/ask",
            json={
                "question": (
                    "What was the company's revenue in March 2026?"
                ),
                "limit": 3,
            },
        )

    assert response.status_code == 200

    body = response.json()
    assert body["answer"] == "987654 rupees"
    assert len(body["sources"]) == 1
    assert body["sources"][0]["document_id"] == 55
    mock_generate.assert_called_once()



def test_ask_rejects_missing_cash_flow_evidence():
    revenue_result = type(
        "FakeResult",
        (),
        {
            "id": 103,
            "score": 0.75,
            "payload": {
                "document_id": 55,
                "text": (
                    "The company recorded revenue of "
                    "987654 rupees in March 2026. "
                    "Net profit was 123456 rupees in March 2026."
                ),
            },
        },
    )()

    with (
        patch(
            "app.main.search_embeddings",
            return_value=[revenue_result],
        ),
        patch("app.main.generate_answer") as mock_generate,
    ):
        response = client.post(
            "/ask",
            json={
                "question": (
                    "What was the company's cash flow in March 2026?"
                ),
                "limit": 3,
            },
        )

    assert response.status_code == 200
    body = response.json()

    assert body["answer"] == (
        "I do not have enough information to answer this question."
    )
    assert body["sources"] == []
    mock_generate.assert_not_called()



def test_ask_rejects_answer_that_contradicts_evidence():
    revenue_result = type(
        "FakeResult",
        (),
        {
            "id": 104,
            "score": 0.80,
            "payload": {
                "document_id": 55,
                "text": (
                    "The company recorded revenue of "
                    "500000 rupees in April 2026."
                ),
            },
        },
    )()

    with (
        patch(
            "app.main.search_embeddings",
            return_value=[revenue_result],
        ),
        patch(
            "app.main.generate_answer",
            return_value=(
                "The revenue was 900000 rupees in April 2026."
            ),
        ),
    ):
        response = client.post(
            "/ask",
            json={
                "question": "What was the revenue in April 2026?",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "I do not have enough information to answer this question."
    )
    assert response.json()["sources"] == []

def test_ask_accepts_equivalent_number_formatting():
    from app.main import answer_numbers_match_context

    context = "The company recorded revenue of 500000 rupees."
    answer = "The revenue was 500,000 rupees."

    assert answer_numbers_match_context(answer, context) is True



def test_ask_rejects_number_from_wrong_metric():
    evidence = (
        "The company recorded revenue of 500000 rupees "
        "and net profit of 123456 rupees in March 2026."
    )

    fake_result = type(
        "FakeResult",
        (),
        {
            "id": 105,
            "score": 0.85,
            "payload": {
                "document_id": 55,
                "text": evidence,
            },
        },
    )()

    with (
        patch(
            "app.main.search_embeddings",
            return_value=[fake_result],
        ),
        patch(
            "app.main.generate_answer",
            return_value="The revenue was 123456 rupees in March 2026.",
        ),
    ):
        response = client.post(
            "/ask",
            json={
                "question": "What was the revenue in March 2026?",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "I do not have enough information to answer this question."
    )
    assert response.json()["sources"] == []


def test_metric_validator_accepts_multiple_supported_metrics():
    from app.main import answer_metric_numbers_match_context

    question = "What were revenue and net profit in March 2026?"

    context = (
        "The company recorded revenue of 500000 rupees "
        "and net profit of 123456 rupees in March 2026."
    )

    answer = (
        "Revenue was 500000 rupees and net profit "
        "was 123456 rupees."
    )

    assert answer_metric_numbers_match_context(
        question, answer, context
    ) is True


def test_metric_validator_rejects_wrong_second_metric():
    from app.main import answer_metric_numbers_match_context

    question = "What were revenue and net profit in March 2026?"

    context = (
        "The company recorded revenue of 500000 rupees "
        "and net profit of 123456 rupees in March 2026."
    )

    answer = (
        "Revenue was 500000 rupees and net profit "
        "was 500000 rupees."
    )

    assert answer_metric_numbers_match_context(
        question, answer, context
    ) is False


def test_currency_validator_accepts_matching_currency():
    from app.main import answer_currency_matches_context

    context = "Revenue was ₹500,000."
    answer = "Revenue was ₹500,000."

    assert answer_currency_matches_context(answer, context) is True


def test_currency_validator_rejects_wrong_currency():
    from app.main import answer_currency_matches_context

    context = "Revenue was ₹500,000."
    answer = "Revenue was $500,000."

    assert answer_currency_matches_context(answer, context) is False


def test_currency_validator_rejects_inr_usd_mismatch():
    from app.main import answer_currency_matches_context

    context = "Revenue was USD 500,000."
    answer = "Revenue was INR 500,000."

    assert answer_currency_matches_context(answer, context) is False


def test_currency_validator_accepts_rupee_text_format():
    from app.main import answer_currency_matches_context

    context = "Revenue was 500,000 rupees."
    answer = "Revenue was 500,000 rupees."

    assert answer_currency_matches_context(answer, context) is True

def test_ask_rejects_wrong_currency():
    evidence = (
        "The company recorded revenue of "
        "500000 rupees in March 2026."
    )

    fake_result = type(
        "FakeResult",
        (),
        {
            "id": 106,
            "score": 0.85,
            "payload": {
                "document_id": 55,
                "text": evidence,
            },
        },
    )()

    with (
        patch(
            "app.main.search_embeddings",
            return_value=[fake_result],
        ),
        patch(
            "app.main.generate_answer",
            return_value=(
                "The revenue was USD 500000 in March 2026."
            ),
        ),
    ):
        response = client.post(
            "/ask",
            json={
                "question": "What was the revenue in March 2026?",
                "limit": 3,
            },
        )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "I do not have enough information to answer this question."
    )
    assert response.json()["sources"] == []


def test_number_validator_accepts_lakh_conversion():
    from app.main import answer_numbers_match_context

    assert answer_numbers_match_context(
        "Revenue was 500000.",
        "Revenue was 5 lakh."
    ) is True


def test_number_validator_accepts_crore_conversion():
    from app.main import answer_numbers_match_context

    assert answer_numbers_match_context(
        "Revenue was 20000000.",
        "Revenue was 2 crore."
    ) is True


def test_number_validator_accepts_million_conversion():
    from app.main import answer_numbers_match_context

    assert answer_numbers_match_context(
        "Revenue was 3000000.",
        "Revenue was 3 million."
    ) is True


def test_number_validator_rejects_wrong_lakh_conversion():
    from app.main import answer_numbers_match_context

    assert answer_numbers_match_context(
        "Revenue was 5000000.",
        "Revenue was 5 lakh."
    ) is False


def test_currency_validator_accepts_lakh_conversion():
    from app.main import answer_currency_matches_context

    assert answer_currency_matches_context(
        "Revenue was ₹500000.",
        "Revenue was ₹5 lakh."
    ) is True
