
from app.crud import (
    create_document_with_chunks,
    save_document_chunks,
    get_all_document_chunks,
)
from app.hashing import calculate_content_hash


def test_save_chunk_hash():
    # Create a real document so the foreign key is valid.
    document = create_document_with_chunks(
        title="Independent Chunk Hash Test",
        source="test",
        content="Temporary parent document for testing chunk hash insertion.",
    )

    document_id = document["id"]

    text = "Unique test chunk for automatic hash verification."

    chunks = [{
        "document_id": document_id,
        "chunk_index": 100,
        "text": text,
    }]

    inserted = save_document_chunks(chunks)
    print(f"Chunks inserted: {inserted}")

    all_chunks = get_all_document_chunks()

    saved = [
        chunk for chunk in all_chunks
        if chunk["document_id"] == document_id
        and chunk["chunk_index"] == 100
    ]

    assert saved, "Chunk was not found in PostgreSQL"

    expected_hash = calculate_content_hash(text)
    assert saved[0]["content_hash"] == expected_hash

    print("SHA-256 hash verified for saved chunk!")
    print("Test passed!")


if __name__ == "__main__":
    test_save_chunk_hash()
