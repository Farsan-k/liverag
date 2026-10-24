
from unittest.mock import patch

from app.llm import generate_answer, FALLBACK_ANSWER


def test_empty_context_returns_fallback_without_calling_llm():
    with patch("app.llm.ollama.chat") as mock_chat:
        answer = generate_answer(
            question="What was the net profit in April 2026?",
            context="   ",
        )

    assert answer == FALLBACK_ANSWER
    mock_chat.assert_not_called()


def test_empty_model_response_returns_fallback():
    with patch(
        "app.llm.ollama.chat",
        return_value={"message": {"content": "   "}},
    ):
        answer = generate_answer(
            question="What was the net profit in April 2026?",
            context="Revenue was 500000 rupees in April 2026.",
        )

    assert answer == FALLBACK_ANSWER


def test_nonempty_model_response_is_returned():
    expected = "The net profit was 75000 rupees in April 2026."

    with patch(
        "app.llm.ollama.chat",
        return_value={"message": {"content": f"  {expected}  "}},
    ) as mock_chat:
        answer = generate_answer(
            question="What was the net profit in April 2026?",
            context=(
                "Revenue was 500000 rupees and net profit was "
                "75000 rupees in April 2026."
            ),
        )

    assert answer == expected
    assert mock_chat.call_args.kwargs["options"]["temperature"] == 0
