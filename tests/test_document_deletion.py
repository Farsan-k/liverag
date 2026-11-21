
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.main import app
from app.vector_store import (
    COLLECTION_NAME,
    create_collection,
    delete_document_embeddings,
    sync_postgres_chunks_to_qdrant,
)


client = TestClient(app)


def test_document_delete_api_removes_database_and_vector_data():
    document_id = 123456

    with (
        patch("app.main.get_document", return_value={"id": document_id}),
        patch("app.main.delete_document", return_value=True) as mock_db_delete,
        patch("app.main.delete_document_embeddings") as mock_vector_delete,
        patch("app.main.sync_postgres_chunks_to_qdrant") as mock_sync,
    ):
        response = client.delete(f"/documents/{document_id}")

    assert response.status_code == 204
    mock_db_delete.assert_called_once_with(document_id)
    mock_vector_delete.assert_called_once_with(document_id)
    mock_sync.assert_not_called()


def test_delete_document_embeddings_preserves_other_documents():
    create_collection()

    target_document_id = int(uuid4().hex[:12], 16)
    other_document_id = int(uuid4().hex[:12], 16)

    target_chunk_id = int(uuid4().hex[:12], 16)
    other_chunk_id = int(uuid4().hex[:12], 16)

    setup_client = QdrantClient(path="./qdrant_data")

    try:
        setup_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=target_chunk_id,
                    vector=[0.0] * 384,
                    payload={"document_id": target_document_id},
                ),
                PointStruct(
                    id=other_chunk_id,
                    vector=[0.0] * 384,
                    payload={"document_id": other_document_id},
                ),
            ],
            wait=True,
        )
    finally:
        setup_client.close()

    try:
        # The setup client is closed before opening another client.
        delete_document_embeddings(target_document_id)

        verify_client = QdrantClient(path="./qdrant_data")

        try:
            remaining_points = verify_client.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[target_chunk_id, other_chunk_id],
                with_payload=True,
                with_vectors=False,
            )

            remaining_ids = {point.id for point in remaining_points}

            assert target_chunk_id not in remaining_ids
            assert other_chunk_id in remaining_ids

        finally:
            verify_client.close()

    finally:
        cleanup_client = QdrantClient(path="./qdrant_data")

        try:
            cleanup_client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=[target_chunk_id, other_chunk_id],
                wait=True,
            )
        finally:
            cleanup_client.close()


def test_sync_protects_qdrant_when_postgres_is_empty():
    fake_client = MagicMock()

    fake_client.scroll.return_value = (
        [MagicMock(id=123)],
        None,
    )

    with (
        patch("app.vector_store.get_all_document_chunks", return_value=[]),
        patch("app.vector_store.QdrantClient", return_value=fake_client),
    ):
        with pytest.raises(RuntimeError, match="zero chunks"):
            sync_postgres_chunks_to_qdrant()

    fake_client.delete.assert_not_called()
    fake_client.close.assert_called_once()
