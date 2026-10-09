
from app.chunking import create_text_chunks
from app.crud import save_document_chunks, get_document


def test_save_document_chunks():
    document_id = 8

    document = get_document(document_id)
    assert document is not None, f"Document {document_id} not found"

    chunks = create_text_chunks(
        document.content,
        document_id=document_id,
    )

    first_saved_count = save_document_chunks(chunks)
    second_saved_count = save_document_chunks(chunks)

    print("First insertion result:", repr(first_saved_count))
    print("Second insertion result:", repr(second_saved_count))

    print(f"Generated chunks: {len(chunks)}")
    print(f"First insertion: {first_saved_count}")
    print(f"Second insertion: {second_saved_count}")


if __name__ == "__main__":
    test_save_document_chunks()
