
import io
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.main.store_financial_file")
def test_upload_valid_pdf(mock_store):
    mock_store.return_value = {
        "id": 1,
        "original_filename": "report.pdf",
        "file_type": "pdf",
        "file_hash": "a" * 64,
        "file_size": 12,
        "company": "Test Company",
        "expected_cik": None,
        "extraction_status": "pending",
        "duplicate": False,
        "created_at": None,
    }

    response = client.post(
        "/financial-documents/upload",
        files={
            "file": (
                "report.pdf",
                io.BytesIO(b"%PDF-1.7 test"),
                "application/pdf",
            )
        },
        data={"company": "Test Company"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["duplicate"] is False


@patch("app.main.store_financial_file")
def test_duplicate_upload(mock_store):
    mock_store.return_value = {
        "id": 1,
        "original_filename": "report.pdf",
        "file_type": "pdf",
        "file_hash": "a" * 64,
        "file_size": 12,
        "company": None,
        "expected_cik": None,
        "extraction_status": "pending",
        "duplicate": True,
        "created_at": None,
    }

    response = client.post(
        "/financial-documents/upload",
        files={
            "file": (
                "report.pdf",
                io.BytesIO(b"%PDF-1.7 test"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["duplicate"] is True


def test_unsupported_extension():
    response = client.post(
        "/financial-documents/upload",
        files={
            "file": (
                "report.txt",
                io.BytesIO(b"some content"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400


def test_empty_file():
    response = client.post(
        "/financial-documents/upload",
        files={
            "file": (
                "empty.pdf",
                io.BytesIO(b""),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400


def test_invalid_pdf_content():
    response = client.post(
        "/financial-documents/upload",
        files={
            "file": (
                "invalid.pdf",
                io.BytesIO(b"this is not a PDF"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400


def test_invalid_cik():
    response = client.post(
        "/financial-documents/upload",
        files={
            "file": (
                "report.pdf",
                io.BytesIO(b"%PDF-1.7 test"),
                "application/pdf",
            )
        },
        data={"expected_cik": "ABC123"},
    )

    assert response.status_code == 400


def test_oversized_file():
    response = client.post(
        "/financial-documents/upload",
        files={
            "file": (
                "large.pdf",
                io.BytesIO(b"%PDF-" + b"x" * (20 * 1024 * 1024)),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
