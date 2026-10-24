
from app.crud import (
    create_document_with_chunks,
    get_all_document_chunks,
    delete_document,
)
from app.hashing import calculate_content_hash
from app.vector_store import sync_postgres_chunks_to_qdrant


def test_new_chunks_have_hashes():
    result = create_document_with_chunks(
        title="Hash Test Document",
        source="test",
        content=(
            "This is a test document for verifying automatic "
            "SHA-256 hash generation for newly created chunks."
        ),
    )

    document_id = result["id"]

    try:
        chunks = get_all_document_chunks()
        new_chunks = [
            chunk for chunk in chunks
            if chunk["document_id"] == document_id
        ]

        assert new_chunks, "No chunks were created"

        for chunk in new_chunks:
            expected_hash = calculate_content_hash(chunk["text"])

            assert chunk["content_hash"] is not None
            assert chunk["content_hash"] == expected_hash

        print(f"Created document ID: {document_id}")
        print(f"Verified hashes for {len(new_chunks)} new chunk(s)")
        print("New chunk hash test passed!")

    finally:
        delete_document(document_id)
        sync_postgres_chunks_to_qdrant()


if __name__ == "__main__":
    test_new_chunks_have_hashes()
