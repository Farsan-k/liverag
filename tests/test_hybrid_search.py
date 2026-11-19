
from types import SimpleNamespace

import pytest

from app import vector_store


def test_hybrid_search_merges_duplicate_chunks(monkeypatch):
    semantic_results = [
        SimpleNamespace(
            id=1,
            score=0.90,
            payload={
                "chunk_id": 1,
                "document_id": 10,
                "chunk_index": 0,
                "text": "Apple revenue increased.",
            },
        ),
        SimpleNamespace(
            id=2,
            score=0.80,
            payload={
                "chunk_id": 2,
                "document_id": 20,
                "chunk_index": 0,
                "text": "Microsoft revenue increased.",
            },
        ),
    ]

    keyword_results = [
        {
            "chunk_id": 1,
            "document_id": 10,
            "chunk_index": 0,
            "text": "Apple revenue increased.",
            "rank": 0.05,
        },
        {
            "chunk_id": 3,
            "document_id": 30,
            "chunk_index": 0,
            "text": "Revenue growth was strong.",
            "rank": 0.04,
        },
    ]

    monkeypatch.setattr(
        vector_store,
        "search_embeddings",
        lambda **kwargs: semantic_results,
    )

    monkeypatch.setattr(
        vector_store,
        "search_keyword_chunks",
        lambda query, limit: keyword_results,
    )

    monkeypatch.setattr(
        vector_store,
        "get_chunk_metadata",
        lambda ids: {
            1: {"document_title": "Apple Report", "document_source": "SEC"},
            2: {"document_title": "Microsoft Report", "document_source": "SEC"},
            3: {"document_title": "Revenue Report", "document_source": "Test"},
        },
    )

    results = vector_store.hybrid_search(
        "Apple revenue",
        limit=5,
        rrf_k=60,
    )

    assert len(results) == 3

    # Chunk 1 appears in both retrieval lists.
    assert results[0]["chunk_id"] == 1
    assert results[0]["semantic_rank"] == 1
    assert results[0]["keyword_rank"] == 1

    expected_score = (1 / 61) + (1 / 61)
    assert results[0]["rrf_score"] == pytest.approx(expected_score)

    # Semantic-only and keyword-only chunks are preserved.
    assert results[1]["chunk_id"] in (2, 3)
    assert results[2]["chunk_id"] in (2, 3)


def test_hybrid_search_empty_query():
    assert vector_store.hybrid_search("   ") == []


def test_hybrid_search_invalid_limit():
    with pytest.raises(ValueError):
        vector_store.hybrid_search("Apple revenue", limit=0)


def test_hybrid_search_invalid_rrf_constant():
    with pytest.raises(ValueError):
        vector_store.hybrid_search("Apple revenue", rrf_k=0)


def test_hybrid_search_respects_limit(monkeypatch):
    semantic_results = [
        SimpleNamespace(
            id=i,
            score=0.9 - i * 0.01,
            payload={
                "chunk_id": i,
                "document_id": i,
                "chunk_index": 0,
                "text": f"Financial result {i}",
            },
        )
        for i in range(1, 5)
    ]

    monkeypatch.setattr(
        vector_store,
        "search_embeddings",
        lambda **kwargs: semantic_results,
    )

    monkeypatch.setattr(
        vector_store,
        "search_keyword_chunks",
        lambda query, limit: [],
    )

    monkeypatch.setattr(
        vector_store,
        "get_chunk_metadata",
        lambda ids: {},
    )

    results = vector_store.hybrid_search(
        "financial results",
        limit=2,
    )

    assert len(results) == 2
