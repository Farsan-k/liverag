
from app.crud import (
    create_document_with_chunks,
    save_document_chunks,
    get_all_document_chunks,
    delete_document,
)
from app.vector_store import (
    create_collection,
    sync_postgres_chunks_to_qdrant,
    COLLECTION_NAME,
)
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
)


def test_changed_chunk_sync():
    create_collection()

    document = create_document_with_chunks(
        title="Qdrant Sync Test",
        source="test",
        content="Initial content for testing synchronization.",
    )

    document_id = document["id"]
    chunk_index = 100
    original_text = "Original financial information."
    updated_text = "Updated financial information."

    try:
        save_document_chunks([
            {
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": original_text,
            }
        ])

        sync_postgres_chunks_to_qdrant()

        chunks = get_all_document_chunks()
        chunk = next(
            item
            for item in chunks
            if item["document_id"] == document_id
            and item["chunk_index"] == chunk_index
        )

        original_hash = chunk["content_hash"]

        # Verify the original Qdrant point.
        client = QdrantClient(path="./qdrant_data")
        try:
            original_point = client.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[chunk["id"]],
                with_payload=True,
                with_vectors=False,
            )[0]

            assert original_point.payload["text"] == original_text
            assert (
                original_point.payload["content_hash"]
                == original_hash
            )
        finally:
            client.close()

        save_document_chunks([
            {
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": updated_text,
            }
        ])

        sync_postgres_chunks_to_qdrant()

        updated_chunks = get_all_document_chunks()
        updated_chunk = next(
            item
            for item in updated_chunks
            if item["document_id"] == document_id
            and item["chunk_index"] == chunk_index
        )

        client = QdrantClient(path="./qdrant_data")
        try:
            updated_point = client.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[updated_chunk["id"]],
                with_payload=True,
                with_vectors=False,
            )[0]

            assert updated_chunk["text"] == updated_text
            assert updated_point.payload["text"] == updated_text

            assert updated_chunk["content_hash"] != original_hash
            assert (
                updated_point.payload["content_hash"]
                == updated_chunk["content_hash"]
            )
        finally:
            client.close()

        print("Qdrant text updated successfully!")
        print("Qdrant content hash updated successfully!")

    finally:
        delete_document(document_id)

        sync_postgres_chunks_to_qdrant()

        print("Test document and its vectors cleaned up.")


def test_document_deletion_removes_qdrant_vectors():
    create_collection()

    document = create_document_with_chunks(
        title="Qdrant Deletion Test",
        source="test",
        content="Temporary financial content for deletion testing.",
    )
    document_id = document["id"]

    try:
        sync_postgres_chunks_to_qdrant()

        client = QdrantClient(path="./qdrant_data")
        try:
            points, _ = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            assert len(points) > 0
        finally:
            client.close()

        assert delete_document(document_id) is True

        sync_postgres_chunks_to_qdrant()

        client = QdrantClient(path="./qdrant_data")
        try:
            points, _ = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False,
            )
            assert len(points) == 0
        finally:
            client.close()

        remaining_chunks = [
            chunk
            for chunk in get_all_document_chunks()
            if chunk["document_id"] == document_id
        ]
        assert remaining_chunks == []

        assert delete_document(document_id) is False

    finally:
        delete_document(document_id)
        sync_postgres_chunks_to_qdrant()

        print("Test document and its vectors cleaned up.")


if __name__ == "__main__":
    test_changed_chunk_sync()
