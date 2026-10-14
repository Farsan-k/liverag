
from app.crud import (
    create_document_with_chunks,
    save_document_chunks,
    get_all_document_chunks,
)
from app.hashing import calculate_content_hash


def test_changed_chunk_content():
    # Create a real document to satisfy the foreign key.
    document = create_document_with_chunks(
        title="Changed Chunk Test",
        source="test",
        content="Original document content for just testing.",
    )

    document_id = document["id"]

    original_text = "Original chunk text."
    changed_text = "Updated chunk text."

    # Insert the original chunk.
    original_chunks = [{
        "document_id": document_id,
        "chunk_index": 100,
        "text": original_text,
    }]

    first_insert = save_document_chunks(original_chunks)

    # Try saving different text at the same chunk index.
    changed_chunks = [{
        "document_id": document_id,
        "chunk_index": 100,
        "text": changed_text,
    }]

    second_insert = save_document_chunks(changed_chunks)

    # Read the saved chunk from PostgreSQL.
    all_chunks = get_all_document_chunks()

    saved_chunk = next(
        chunk for chunk in all_chunks
        if chunk["document_id"] == document_id
        and chunk["chunk_index"] == 100
    )

    print(f"First insert count: {first_insert}")
    print(f"Second insert count: {second_insert}")
    print(f"Saved text: {saved_chunk['text']}")
    print(f"Saved hash: {saved_chunk['content_hash']}")

    # Confirm the current insert-only behavior.

# The changed text should now be saved.
    assert saved_chunk["text"] == changed_text

    # The stored hash should match the changed text.
    assert saved_chunk["content_hash"] == calculate_content_hash(
        changed_text
    )

    unchanged_chunks = [{
    "document_id": document_id,
    "chunk_index": 100,
    "text": changed_text,
    }]

    third_insert = save_document_chunks(unchanged_chunks)

    print(f"Unchanged content result: {third_insert}")

    assert third_insert == 0

    print("Unchanged content correctly skipped!")

    print("Changed chunk text verified!")
    print("Updated SHA-256 hash verified!")
    print("Changed chunk test passed!")



if __name__ == "__main__":
    test_changed_chunk_content()
