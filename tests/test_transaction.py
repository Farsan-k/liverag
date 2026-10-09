
from unittest.mock import patch

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Document
from app.crud import create_document_with_chunks


def test_document_rolls_back_if_chunk_insertion_fails():
    test_title = "Rollback Test - LiveRAG"

    with patch(
        "app.crud.insert_chunks_in_session",
        side_effect=RuntimeError("Simulated chunk insertion failure"),
    ):
        try:
            create_document_with_chunks(
                title=test_title,
                source="Test",
                content="This document tests transaction rollback."
            )
        except RuntimeError as exc:
            assert str(exc) == "Simulated chunk insertion failure"
        else:
            raise AssertionError("Expected chunk insertion to fail")

    with SessionLocal() as session:
        document = session.execute(
            select(Document).where(Document.title == test_title)
        ).scalar_one_or_none()

        assert document is None, "Document was not rolled back"

    print("Rollback test passed")


if __name__ == "__main__":
    test_document_rolls_back_if_chunk_insertion_fails()
