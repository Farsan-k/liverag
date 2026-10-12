
from app.crud import (
    create_document_with_chunks,
    update_document,
    get_all_document_chunks,
)
from app.chunking import create_text_chunks

def test_document_update():
    # Create a document with its initial chunks.
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

    # Capture the original chunks.
    chunks_before = [
        chunk for chunk in get_all_document_chunks()
        if chunk["document_id"] == document_id
    ]

    print(f"Document ID: {document_id}")
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

    # Read the chunks after updating the document.
    chunks_after = [
        chunk for chunk in get_all_document_chunks()
        if chunk["document_id"] == document_id
    ]

    print(f"Updated document content: {updated_document['content']}")
    print(f"Chunks after update: {len(chunks_after)}")

    # The document itself should be updated.
    assert updated_document["content"] == updated_content

    # This currently checks whether chunk records remain unchanged.
# Updated chunks should contain the new document content.
    assert chunks_after, "No chunks found after document update"

    combined_text = " ".join(
        chunk["text"] for chunk in chunks_after
    )

    assert "Microsoft" in combined_text
    assert "Apple" not in combined_text

    print("Updated chunks verified!")
    print("Document update test passed!")
    
    # Test shortening the document.
    short_content = "Microsoft released a new AI product."

    update_document(
        document_id=document_id,
        title=None,
        source=None,
        content=short_content,
    )

    short_chunks = [
        chunk for chunk in get_all_document_chunks()
        if chunk["document_id"] == document_id
    ]

    expected_chunks = create_text_chunks(
        short_content,
        document_id=document_id,
    )

    print(f"Chunks after shortening: {len(short_chunks)}")

    assert len(short_chunks) == len(expected_chunks)

    combined_short_text = " ".join(
        chunk["text"] for chunk in short_chunks
    )

    assert "Microsoft released a new AI product." in combined_short_text

    print("Shortened document chunks verified!")


    print("Current document update behavior verified!")


if __name__ == "__main__":
    test_document_update()
