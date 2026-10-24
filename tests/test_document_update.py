
from app.crud import (
    create_document_with_chunks,
    update_document,
    get_all_document_chunks,
    delete_document,
)
from app.chunking import create_text_chunks
from app.vector_store import (
    sync_postgres_chunks_to_qdrant,
    search_embeddings,
)


def test_document_update():
    original_content = (
        "Apple reported strong revenue growth during the quarter. "
        "Its earnings increased compared with the previous period."
    )

    document = create_document_with_chunks(
        title="Document Update Test",
        source="test",
        content=original_content,
    )

    document_id = document["id"]

    try:
        # Verify the original chunks.
        chunks_before = [
            chunk for chunk in get_all_document_chunks()
            if chunk["document_id"] == document_id
        ]

        assert chunks_before
        print(f"Chunks before update: {len(chunks_before)}")

        # Update the document content.
        updated_content = (
            "Microsoft announced new AI products this quarter. "
            "Its cloud revenue increased due to enterprise demand."
        )

        updated_document = update_document(
            document_id=document_id,
            title=None,
            source=None,
            content=updated_content,
        )

        assert updated_document["content"] == updated_content

        # Verify PostgreSQL chunks.
        chunks_after = [
            chunk for chunk in get_all_document_chunks()
            if chunk["document_id"] == document_id
        ]

        combined_text = " ".join(
            chunk["text"] for chunk in chunks_after
        )

        assert chunks_after
        assert "Microsoft" in combined_text
        assert "Apple" not in combined_text

        # Synchronize the updated chunks to Qdrant.
        sync_postgres_chunks_to_qdrant()

        qdrant_results = search_embeddings(
            query="Microsoft AI products and cloud revenue",
            limit=5,
            score_threshold=0.0,
        )

        matching_results = [
            result for result in qdrant_results
            if (result.payload or {}).get("document_id") == document_id
        ]

        assert matching_results, (
            "Updated document chunks were not found in Qdrant"
        )

        print("Updated PostgreSQL and Qdrant chunks verified!")

        # Shorten the document and verify obsolete chunks are removed.
        short_content = "Microsoft released a new AI product."

        update_document(
            document_id=document_id,
            title=None,
            source=None,
            content=short_content,
        )

        sync_postgres_chunks_to_qdrant()

        short_chunks = [
            chunk for chunk in get_all_document_chunks()
            if chunk["document_id"] == document_id
        ]

        expected_chunks = create_text_chunks(
            short_content,
            document_id=document_id,
        )

        assert len(short_chunks) == len(expected_chunks)

        combined_short_text = " ".join(
            chunk["text"] for chunk in short_chunks
        )

        assert short_content in combined_short_text

        final_results = search_embeddings(
            query="Microsoft released a new AI product",
            limit=5,
            score_threshold=0.0,
        )

        final_matching_results = [
            result for result in final_results
            if (result.payload or {}).get("document_id") == document_id
        ]

        assert final_matching_results, (
            "Shortened document was not synchronized to Qdrant"
        )

        print("Document shortening and Qdrant synchronization verified!")
        print("Document update test passed!")

    finally:
        delete_document(document_id)
        sync_postgres_chunks_to_qdrant()
        print("Test document and its vectors cleaned up.")


if __name__ == "__main__":
    test_document_update()
