from app.crud import create_document, get_document, delete_document


document = create_document(
    title="Test Financial News",
    source="TestSource",
    content="This is a test document."
)

print(f"Created document ID: {document.id}")


found_document = get_document(document.id)

print(f"Retrieved title: {found_document.title}")

delete_result = delete_document(document.id)

print(f"Delete result: {delete_result}")