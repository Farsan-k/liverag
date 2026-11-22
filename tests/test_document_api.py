
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_new_document_upload_triggers_qdrant_sync():
    document_result = {
        "id": 101,
        "title": "Apple Earnings",
        "source": "Reuters",
        "content": "Apple reported strong revenue growth.",
        "content_hash": "a" * 64,
        "chunks_created": 1,
        "chunks_saved": 1,
        "duplicate": False,
    }

    with (
        patch(
            "app.main.create_document_with_chunks",
            return_value=document_result,
        ) as mock_create,
        patch(
            "app.main.sync_postgres_chunks_to_qdrant"
        ) as mock_sync,
    ):
        response = client.post(
            "/documents",
            json={
                "title": "Apple Earnings",
                "source": "Reuters",
                "content": "Apple reported strong revenue growth.",
            },
        )

    assert response.status_code == 200
    assert response.json()["duplicate"] is False
    assert response.json()["id"] == 101

    mock_create.assert_called_once()
    mock_sync.assert_called_once()


def test_duplicate_document_upload_skips_qdrant_sync():
    document_result = {
        "id": 101,
        "title": "Apple Earnings",
        "source": "Reuters",
        "content": "Apple reported strong revenue growth.",
        "content_hash": "a" * 64,
        "chunks_created": 0,
        "chunks_saved": 0,
        "duplicate": True,
    }

    with (
        patch(
            "app.main.create_document_with_chunks",
            return_value=document_result,
        ) as mock_create,
        patch(
            "app.main.sync_postgres_chunks_to_qdrant"
        ) as mock_sync,
    ):
        response = client.post(
            "/documents",
            json={
                "title": "Apple Quarterly Results",
                "source": "Bloomberg",
                "content": "Apple reported strong revenue growth.",
            },
        )

    assert response.status_code == 200
    assert response.json()["duplicate"] is True
    assert response.json()["id"] == 101

    mock_create.assert_called_once()
    mock_sync.assert_not_called()
