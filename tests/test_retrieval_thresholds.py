
from types import SimpleNamespace

import pytest

from app import vector_store


def test_semantic_search_applies_score_threshold(monkeypatch):
    semantic_results = [
        SimpleNamespace(
            id=1,
            score=0.85,
            payload={"chunk_id": 1},
        ),
        SimpleNamespace(
            id=2,
            score=0.65,
            payload={"chunk_id": 2},
        ),
        SimpleNamespace(
            id=3,
            score=0.35,
            payload={"chunk_id": 3},
        ),
    ]

    captured = {}

    def fake_query_points(**kwargs):
        captured.update(kwargs)

        # Return all results without filtering.
        # The application itself must apply the threshold.
        return SimpleNamespace(points=semantic_results)

    class FakeClient:
        def query_points(self, **kwargs):
            return fake_query_points(**kwargs)

        def close(self):
            pass

    monkeypatch.setattr(
        vector_store,
        "QdrantClient",
        lambda **kwargs: FakeClient(),
    )

    monkeypatch.setattr(
        vector_store,
        "generate_embedding",
        lambda query: [0.1] * 384,
    )

    results = vector_store.search_embeddings(
        query="Apple revenue growth",
        limit=5,
        score_threshold=0.60,
        deduplicate_documents=False,
    )

    # Verify that the application filters results.
    assert len(results) == 2
    assert [result.id for result in results] == [1, 2]

    # Verify that Qdrant retrieves additional candidates.
    assert captured["limit"] == 25
    assert captured["with_payload"] is True


def test_semantic_search_without_threshold_keeps_all_results(
    monkeypatch,
):
    semantic_results = [
        SimpleNamespace(
            id=1,
            score=0.85,
            payload={"chunk_id": 1},
        ),
        SimpleNamespace(
            id=2,
            score=0.35,
            payload={"chunk_id": 2},
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=semantic_results)

        def close(self):
            pass

    monkeypatch.setattr(
        vector_store,
        "QdrantClient",
        lambda **kwargs: FakeClient(),
    )

    monkeypatch.setattr(
        vector_store,
        "generate_embedding",
        lambda query: [0.1] * 384,
    )

    results = vector_store.search_embeddings(
        query="Apple revenue",
        limit=5,
        score_threshold=None,
        deduplicate_documents=False,
    )

    assert len(results) == 2


def test_semantic_search_invalid_limit():
    with pytest.raises(ValueError):
        vector_store.search_embeddings(
            query="Apple revenue",
            limit=0,
        )


def test_semantic_search_rejects_invalid_score_threshold():
    for threshold in (1.5, -1.5):
        with pytest.raises(ValueError):
            vector_store.search_embeddings(
                query="Apple revenue",
                score_threshold=threshold,
            )


def test_semantic_search_returns_empty_for_blank_query():
    results = vector_store.search_embeddings(
        query="   ",
        limit=5,
    )

    assert results == []


def test_semantic_search_keeps_results_without_document_id(
    monkeypatch,
):
    semantic_results = [
        SimpleNamespace(
            id=1,
            score=0.90,
            payload={"chunk_id": 1},
        ),
        SimpleNamespace(
            id=2,
            score=0.85,
            payload={"chunk_id": 2},
        ),
        SimpleNamespace(
            id=3,
            score=0.80,
            payload={"chunk_id": 3},
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=semantic_results)

        def close(self):
            pass

    monkeypatch.setattr(
        vector_store,
        "QdrantClient",
        lambda **kwargs: FakeClient(),
    )

    monkeypatch.setattr(
        vector_store,
        "generate_embedding",
        lambda query: [0.1] * 384,
    )

    results = vector_store.search_embeddings(
        query="Apple revenue",
        limit=3,
        deduplicate_documents=True,
    )

    assert len(results) == 3
    assert [result.id for result in results] == [1, 2, 3]


def test_semantic_search_deduplicates_same_document(
    monkeypatch,
):
    semantic_results = [
        SimpleNamespace(
            id=1,
            score=0.95,
            payload={"chunk_id": 1, "document_id": 100},
        ),
        SimpleNamespace(
            id=2,
            score=0.90,
            payload={"chunk_id": 2, "document_id": 100},
        ),
        SimpleNamespace(
            id=3,
            score=0.85,
            payload={"chunk_id": 3, "document_id": 200},
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=semantic_results)

        def close(self):
            pass

    monkeypatch.setattr(
        vector_store,
        "QdrantClient",
        lambda **kwargs: FakeClient(),
    )

    monkeypatch.setattr(
        vector_store,
        "generate_embedding",
        lambda query: [0.1] * 384,
    )

    results = vector_store.search_embeddings(
        query="Apple revenue",
        limit=3,
        deduplicate_documents=True,
    )

    assert len(results) == 2
    assert [result.id for result in results] == [1, 3]


def test_semantic_search_returns_available_unique_documents(
    monkeypatch,
):
    semantic_results = [
        SimpleNamespace(
            id=1,
            score=0.99,
            payload={"chunk_id": 1, "document_id": 100},
        ),
        SimpleNamespace(
            id=2,
            score=0.95,
            payload={"chunk_id": 2, "document_id": 100},
        ),
        SimpleNamespace(
            id=3,
            score=0.90,
            payload={"chunk_id": 3, "document_id": 200},
        ),
        SimpleNamespace(
            id=4,
            score=0.85,
            payload={"chunk_id": 4, "document_id": 300},
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=semantic_results)

        def close(self):
            pass

    monkeypatch.setattr(
        vector_store,
        "QdrantClient",
        lambda **kwargs: FakeClient(),
    )

    monkeypatch.setattr(
        vector_store,
        "generate_embedding",
        lambda query: [0.1] * 384,
    )

    results = vector_store.search_embeddings(
        query="Apple revenue",
        limit=3,
        deduplicate_documents=True,
    )

    assert len(results) == 3
    assert [
        result.payload["document_id"]
        for result in results
    ] == [100, 200, 300]


def test_semantic_search_threshold_boundary(monkeypatch):
    semantic_results = [
        SimpleNamespace(id=1, score=0.60, payload={"chunk_id": 1}),
        SimpleNamespace(id=2, score=0.599, payload={"chunk_id": 2}),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=semantic_results)

        def close(self):
            pass

    monkeypatch.setattr(
        vector_store,
        "QdrantClient",
        lambda **kwargs: FakeClient(),
    )

    monkeypatch.setattr(
        vector_store,
        "generate_embedding",
        lambda query: [0.1] * 384,
    )

    results = vector_store.search_embeddings(
        query="Apple revenue",
        limit=5,
        score_threshold=0.60,
        deduplicate_documents=False,
    )

    assert [result.id for result in results] == [1]
