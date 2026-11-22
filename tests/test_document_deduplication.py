
from uuid import uuid4

from app.crud import (
    create_document_with_chunks,
    delete_document,
    update_document,
)
from app.hashing import calculate_content_hash

import pytest
from sqlalchemy.exc import IntegrityError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


def test_new_document_is_created_with_content_hash():
    content = f"Unique financial report {uuid4()}"

    document = create_document_with_chunks(
        title="Financial Report",
        source="Reuters",
        content=content,
    )

    try:
        assert document["id"] is not None
        assert document["content_hash"] == calculate_content_hash(content)
        assert document["duplicate"] is False
        assert document["chunks_created"] > 0

    finally:
        delete_document(document["id"])


def test_duplicate_content_returns_existing_document():
    content = f"Apple revenue report {uuid4()}"

    first_document = create_document_with_chunks(
        title="Apple Earnings Report",
        source="Reuters",
        content=content,
    )

    try:
        second_document = create_document_with_chunks(
            title="Apple Quarterly Results",
            source="Bloomberg",
            content=content,
        )

        assert second_document["id"] == first_document["id"]
        assert second_document["duplicate"] is True
        assert second_document["chunks_created"] == 0
        assert second_document["chunks_saved"] == 0

        # The original document's metadata remains unchanged.
        assert second_document["title"] == "Apple Earnings Report"
        assert second_document["source"] == "Reuters"

    finally:
        delete_document(first_document["id"])


def test_different_content_creates_separate_documents():
    first_content = f"Apple report {uuid4()}"
    second_content = f"Microsoft report {uuid4()}"

    first_document = create_document_with_chunks(
        title="Apple Report",
        source="Reuters",
        content=first_content,
    )

    second_document = create_document_with_chunks(
        title="Microsoft Report",
        source="Bloomberg",
        content=second_content,
    )

    try:
        assert first_document["id"] != second_document["id"]
        assert first_document["duplicate"] is False
        assert second_document["duplicate"] is False

        assert (
            first_document["content_hash"]
            != second_document["content_hash"]
        )

    finally:
        delete_document(first_document["id"])
        delete_document(second_document["id"])




def test_update_rejects_content_already_owned_by_another_document():
    content_a = f"Original document A {uuid4()}"
    content_b = f"Original document B {uuid4()}"

    document_a = create_document_with_chunks(
        title="Document A",
        source="Reuters",
        content=content_a,
    )

    document_b = create_document_with_chunks(
        title="Document B",
        source="Bloomberg",
        content=content_b,
    )

    try:
        with pytest.raises(IntegrityError):
            update_document(
                document_id=document_a["id"],
                title=None,
                source=None,
                content=content_b,
            )

        # Verify the failed update did not change Document A.
        from app.crud import get_document

        unchanged_document = get_document(document_a["id"])

        assert unchanged_document.content == content_a
        assert unchanged_document.content_hash == calculate_content_hash(
            content_a
        )

    finally:
        delete_document(document_a["id"])
        delete_document(document_b["id"])





def test_concurrent_duplicate_uploads_create_only_one_document():
    content = f"Concurrent financial report {uuid4()}"
    barrier = Barrier(2)

    def upload_document():
        barrier.wait(timeout=10)

        return create_document_with_chunks(
            title="Concurrent Report",
            source="Reuters",
            content=content,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(upload_document)
            for _ in range(2)
        ]

        results = [future.result(timeout=30) for future in futures]

    document_ids = {result["id"] for result in results}
    duplicate_flags = sorted(
        result["duplicate"] for result in results
    )

    try:
        assert len(document_ids) == 1
        assert duplicate_flags == [False, True]

    finally:
        delete_document(results[0]["id"])
