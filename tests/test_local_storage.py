
import hashlib

import pytest

from app.storage.local import LocalStorageService


def test_save_file(tmp_path):
    storage = LocalStorageService(str(tmp_path))

    content = b"Finova AI financial report"

    result = storage.save_file(
        file_content=content,
        original_filename="report.pdf",
        category="pdf",
    )

    assert result["original_filename"] == "report.pdf"
    assert result["file_hash"] == hashlib.sha256(content).hexdigest()
    assert result["file_size"] == len(content)
    assert storage.file_exists(result["storage_path"])


def test_delete_file(tmp_path):
    storage = LocalStorageService(str(tmp_path))

    result = storage.save_file(
        file_content=b"test content",
        original_filename="test.pdf",
        category="pdf",
    )

    storage.delete_file(result["storage_path"])

    assert not storage.file_exists(result["storage_path"])


def test_empty_file_rejected(tmp_path):
    storage = LocalStorageService(str(tmp_path))

    with pytest.raises(ValueError):
        storage.save_file(b"", "empty.pdf", "pdf")


def test_invalid_category_rejected(tmp_path):
    storage = LocalStorageService(str(tmp_path))

    with pytest.raises(ValueError):
        storage.save_file(b"test", "test.pdf", "invalid")


def test_path_traversal_cannot_delete_outside_file(tmp_path):
    storage_dir = tmp_path / "storage"
    storage = LocalStorageService(str(storage_dir))

    outside_file = tmp_path / "important.txt"
    outside_file.write_text("keep this file")

    with pytest.raises(ValueError):
        storage.delete_file(str(outside_file))

    assert outside_file.exists()
