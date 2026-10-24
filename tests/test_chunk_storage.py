
from app.chunking import create_text_chunks
from app.crud import (
    create_document_with_chunks,
    save_document_chunks,
    get_all_document_chunks,
    delete_document,
)
from app.vector_store import sync_postgres_chunks_to_qdrant


def test_save_document_chunks():
    document = create_document_with_chunks(
        title="Chunk Storage Test",
        source="test",
        content=(
            "Temporary test content for verifying chunk storage "
            "and duplicate insertion handling."
        ),
    )

    document_id = document["id"]

    try:
        chunks = create_text_chunks(
            document["content"],
            document_id=document_id,
        )

        # The document creation function already stored these chunks.
        saved_chunks = [
            chunk for chunk in get_all_document_chunks()
            if chunk["document_id"] == document_id
        ]

        assert len(saved_chunks) == len(chunks)

        # Saving identical chunks should not insert duplicates.
        first_saved_count = save_document_chunks(chunks)
        second_saved_count = save_document_chunks(chunks)

        print("First duplicate-save result:", first_saved_count)
        print("Second duplicate-save result:", second_saved_count)
        print(f"Generated chunks: {len(chunks)}")

        assert first_saved_count == 0
        assert second_saved_count == 0

        print("Chunk storage and duplicate handling verified!")

    finally:
        delete_document(document_id)
        sync_postgres_chunks_to_qdrant()


if __name__ == "__main__":
    test_save_document_chunks()
