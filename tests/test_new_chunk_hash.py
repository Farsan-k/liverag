
from app.crud import create_document_with_chunks, get_all_document_chunks
from app.hashing import calculate_content_hash

def test_new_chunks_have_hashes():
    result = create_document_with_chunks(
        title="Hash Test Document",
        source="test",
        content=(
            "This is a test document for verifying automatic "
            "SHA-256 hash generation for newly created chunks."
        ),
    )

    chunks = get_all_document_chunks()
    new_chunks = [
        chunk for chunk in chunks
        if chunk["document_id"] == result["id"]
    ]

    assert new_chunks, "No chunks were created"

    for chunk in new_chunks:
        expected_hash = calculate_content_hash(chunk["text"])

        assert chunk["content_hash"] is not None
        assert chunk["content_hash"] == expected_hash

    print(f"Created document ID: {result['id']}")
    print(f"Verified hashes for {len(new_chunks)} new chunk(s)")
    print("New chunk hash test passed!")

if __name__ == "__main__":
    test_new_chunks_have_hashes()
