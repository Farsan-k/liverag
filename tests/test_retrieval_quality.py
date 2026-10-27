
from types import SimpleNamespace

from app.vector_store import search_embeddings


def test_search_returns_at_most_one_chunk_per_document(monkeypatch):
    fake_results = [
        SimpleNamespace(
            id=1,
            score=0.90,
            payload={"document_id": 10, "text": "First chunk"},
        ),
        SimpleNamespace(
            id=2,
            score=0.85,
            payload={"document_id": 10, "text": "Second chunk"},
        ),
        SimpleNamespace(
            id=3,
            score=0.80,
            payload={"document_id": 20, "text": "Third chunk"},
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=fake_results)

        def close(self):
            pass

    monkeypatch.setattr(
        "app.vector_store.QdrantClient",
        lambda **kwargs: FakeClient(),
    )
    monkeypatch.setattr(
        "app.vector_store.generate_embedding",
        lambda query: [0.0] * 384,
    )

    results = search_embeddings("test query", limit=3)

    document_ids = [
        result.payload["document_id"] for result in results
    ]

    assert len(results) == 2
    assert document_ids == [10, 20]
    assert len(document_ids) == len(set(document_ids))



def test_search_filters_results_below_threshold(monkeypatch):
    fake_results = [
        SimpleNamespace(
            id=1,
            score=0.90,
            payload={"document_id": 10, "text": "Strong match"},
        ),
        SimpleNamespace(
            id=2,
            score=0.49,
            payload={"document_id": 20, "text": "Weak match"},
        ),
        SimpleNamespace(
            id=3,
            score=0.50,
            payload={"document_id": 30, "text": "Boundary match"},
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=fake_results)

        def close(self):
            pass

    monkeypatch.setattr(
        "app.vector_store.QdrantClient",
        lambda **kwargs: FakeClient(),
    )
    monkeypatch.setattr(
        "app.vector_store.generate_embedding",
        lambda query: [0.0] * 384,
    )

    results = search_embeddings(
        "test query",
        limit=3,
        score_threshold=0.50,
    )

    assert [result.id for result in results] == [1, 3]



def test_search_requests_extra_candidates(monkeypatch):
    captured = {}

    class FakeClient:
        def query_points(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(points=[])

        def close(self):
            pass

    monkeypatch.setattr(
        "app.vector_store.QdrantClient",
        lambda **kwargs: FakeClient(),
    )
    monkeypatch.setattr(
        "app.vector_store.generate_embedding",
        lambda query: [0.0] * 384,
    )

    search_embeddings("revenue in March 2026", limit=3)

    assert captured["limit"] == 20
    assert captured["with_payload"] is True



def test_search_returns_results_in_descending_score_order(monkeypatch):
    fake_results = [
        SimpleNamespace(
            id=1,
            score=0.65,
            payload={"document_id": 10, "text": "Lower score"},
        ),
        SimpleNamespace(
            id=2,
            score=0.92,
            payload={"document_id": 20, "text": "Highest score"},
        ),
        SimpleNamespace(
            id=3,
            score=0.78,
            payload={"document_id": 30, "text": "Middle score"},
        ),
    ]

    class FakeClient:
        def query_points(self, **kwargs):
            return SimpleNamespace(points=fake_results)

        def close(self):
            pass

    monkeypatch.setattr(
        "app.vector_store.QdrantClient",
        lambda **kwargs: FakeClient(),
    )
    monkeypatch.setattr(
        "app.vector_store.generate_embedding",
        lambda query: [0.0] * 384,
    )

    results = search_embeddings("revenue in March 2026", limit=3)

    assert [result.id for result in results] == [2, 3, 1]
    assert [result.score for result in results] == [0.92, 0.78, 0.65]
