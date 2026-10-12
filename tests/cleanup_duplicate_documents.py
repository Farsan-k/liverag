
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Document, DocumentChunk


# Confirmed duplicate test documents.
DUPLICATE_DOCUMENT_IDS = [56, 57]


def cleanup_duplicate_documents():
    with SessionLocal.begin() as session:
        documents = session.execute(
            select(Document).where(
                Document.id.in_(DUPLICATE_DOCUMENT_IDS)
            )
        ).scalars().all()

        found_ids = {document.id for document in documents}

        if found_ids != set(DUPLICATE_DOCUMENT_IDS):
            raise RuntimeError(
                f"Expected documents {DUPLICATE_DOCUMENT_IDS}, "
                f"but found {sorted(found_ids)}. "
                "Nothing was deleted."
            )

        # Delete child chunks first to satisfy the foreign key.
        chunks_result = session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id.in_(
                    DUPLICATE_DOCUMENT_IDS
                )
            )
        )

        # Then delete the duplicate parent documents.
        documents_result = session.execute(
            delete(Document).where(
                Document.id.in_(DUPLICATE_DOCUMENT_IDS)
            )
        )

        print(f"Chunks deleted: {chunks_result.rowcount}")
        print(f"Documents deleted: {documents_result.rowcount}")


if __name__ == "__main__":
    confirmation = input(
        "Delete duplicate test documents 56 and 57 "
        "and their chunks? Type DELETE to confirm: "
    )

    if confirmation == "DELETE":
        cleanup_duplicate_documents()
        print("Duplicate test data cleanup completed.")
    else:
        print("Cancelled. No records were deleted.")
