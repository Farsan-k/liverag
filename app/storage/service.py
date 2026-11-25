
from app.crud import create_financial_document
from app.storage.factory import get_storage_service


def store_financial_file(
    file_content: bytes,
    original_filename: str,
    file_type: str,
    category: str,
    company: str | None = None,
    expected_cik: str | None = None,
) -> dict:
    """
    Save a financial file locally and register its metadata
    in PostgreSQL.

    If the file already exists, remove the newly saved copy.
    If database insertion fails, remove the saved file.
    """

    storage = get_storage_service()

    saved_file = storage.save_file(
        file_content=file_content,
        original_filename=original_filename,
        category=category,
    )

    try:
        result = create_financial_document(
            original_filename=original_filename,
            storage_path=saved_file["storage_path"],
            file_type=file_type,
            file_hash=saved_file["file_hash"],
            company=company,
            expected_cik=expected_cik,
        )

        if result["duplicate"]:
            storage.delete_file(saved_file["storage_path"])

        result["file_size"] = saved_file["file_size"]

        return result

    except Exception:
        storage.delete_file(saved_file["storage_path"])
        raise
