
import pytest

from app.crud import (
    create_document_with_chunks,
    save_document_chunks,
    get_all_document_chunks,
    delete_document,
)
from app.hashing import calculate_content_hash
from app.vector_store import sync_postgres_chunks_to_qdrant


def test_changed_chunk_content():
    document = create_document_with_chunks(
        title="Changed Chunk Test",
        source="test",
        content="Original document content for just testing.",
    )

    document_id = document["id"]

    try:
        original_text = "Original chunk text."
        changed_text = "Updated chunk text."

        original_chunks = [{
            "document_id": document_id,
            "chunk_index": 100,
            "text": original_text,
        }]

        first_insert = save_document_chunks(original_chunks)

        changed_chunks = [{
            "document_id": document_id,
            "chunk_index": 100,
            "text": changed_text,
        }]

        second_insert = save_document_chunks(changed_chunks)

        all_chunks = get_all_document_chunks()

        saved_chunk = next(
            chunk for chunk in all_chunks
            if chunk["document_id"] == document_id
            and chunk["chunk_index"] == 100
        )

        assert saved_chunk["text"] == changed_text
        assert saved_chunk["content_hash"] == calculate_content_hash(
            changed_text
        )

        unchanged_chunks = [{
            "document_id": document_id,
            "chunk_index": 100,
            "text": changed_text,
        }]

        third_insert = save_document_chunks(unchanged_chunks)

        assert third_insert == 0

    finally:
        delete_document(document_id)
        sync_postgres_chunks_to_qdrant()
