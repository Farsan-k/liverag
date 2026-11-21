
import pytest

from app.crud import (
    create_document_with_chunks,
    delete_document,
    search_keyword_chunks,
)


def test_keyword_search_returns_relevant_chunks():
    document = create_document_with_chunks(
        title="Keyword Search Test",
        source="Test Source",
        content=(
            "Apple reported strong revenue growth. "
            "The company improved its operating performance."
        ),
    )

    document_id = document["id"]

    try:
        results = search_keyword_chunks("Apple revenue", limit=5)

        matching_results = [
            result for result in results
            if result["document_id"] == document_id
        ]

        assert len(matching_results) >= 1
        assert matching_results[0]["document_title"] == "Keyword Search Test"
        assert matching_results[0]["document_source"] == "Test Source"
        assert matching_results[0]["rank"] > 0

    finally:
        delete_document(document_id)


def test_keyword_search_empty_query():
    assert search_keyword_chunks("   ") == []


def test_keyword_search_invalid_limit():
    with pytest.raises(ValueError):
        search_keyword_chunks("Apple revenue", limit=0)


def test_keyword_search_respects_limit():
    results = search_keyword_chunks("Apple revenue", limit=2)

    assert len(results) <= 2


def test_keyword_search_uses_or_fallback_when_strict_search_finds_nothing():
    document = create_document_with_chunks(
        title="OR Fallback Test",
        source="Test Source",
        content=(
            "FinovaZebra announced its latest financial results."
        ),
    )

    document_id = document["id"]

    try:
        # Use a unique term to avoid matching unrelated existing documents.
        results = search_keyword_chunks(
            "FinovaZebra revenue",
            limit=5,
        )

        matching_results = [
            result for result in results
            if result["document_id"] == document_id
        ]

        assert len(matching_results) >= 1
        assert matching_results[0]["document_title"] == "OR Fallback Test"
        assert matching_results[0]["rank"] > 0

    finally:
        delete_document(document_id)


def test_keyword_search_handles_punctuation():
    results = search_keyword_chunks(
        "Apple's revenue!!!",
        limit=5,
    )

    assert isinstance(results, list)


def test_keyword_search_or_fallback_returns_matching_terms():
    document = create_document_with_chunks(
        title="Fallback Precision Test",
        source="Test Source",
        content=(
            "FinovaZebra reported strong revenue growth."
        ),
    )

    document_id = document["id"]

    try:
        results = search_keyword_chunks(
            "FinovaZebra operating expenses",
            limit=5,
        )

        matching_results = [
            result for result in results
            if result["document_id"] == document_id
        ]

        assert len(matching_results) >= 1

    finally:
        delete_document(document_id)
