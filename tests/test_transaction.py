
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Document
from app.crud import create_document_with_chunks


def test_document_rolls_back_if_chunk_insertion_fails():
    test_title = f"Rollback Test - LiveRAG - {uuid4()}"

    with patch(
        "app.crud.insert_chunks_in_session",
        side_effect=RuntimeError("Simulated chunk insertion failure"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Simulated chunk insertion failure",
        ):
            create_document_with_chunks(
                title=test_title,
                source="Test",
                content="This document tests transaction rollback.",
            )

    # Verify that the failed transaction left no document behind.
    with SessionLocal() as session:
        document = session.execute(
            select(Document).where(Document.title == test_title)
        ).scalar_one_or_none()

        assert document is None, "Document was not rolled back"

    print("Transaction rollback verified successfully!")


if __name__ == "__main__":
    test_document_rolls_back_if_chunk_insertion_fails()
