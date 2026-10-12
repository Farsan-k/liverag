
from app.crud import create_document, get_document, delete_document


def test_create_get_and_delete_document():
    # Create a test document
    document = create_document(
        title="Test Financial News",
        source="TestSource",
        content="This is a test document.",
    )

    assert document is not None
    document_id = document.id

    try:
        # Retrieve and verify the document
        found_document = get_document(document_id)

        assert found_document is not None
        assert found_document.title == "Test Financial News"
        assert found_document.source == "TestSource"
        assert found_document.content == "This is a test document."

    finally:
        # Clean up the test document even if an assertion fails
        delete_document(document_id)
