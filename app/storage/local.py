
import hashlib
import re
from pathlib import Path
from uuid import uuid4


class LocalStorageService:

    def __init__(self, base_directory: str = "financial_documents"):
        self.base_directory = Path(base_directory).resolve()
        self.base_directory.mkdir(parents=True, exist_ok=True)

    def save_file(
        self,
        file_content: bytes,
        original_filename: str,
        category: str,
    ) -> dict:

        if not file_content:
            raise ValueError("Uploaded file cannot be empty.")

        if category not in {"sec", "pdf", "other"}:
            raise ValueError("Unsupported storage category.")

        safe_filename = Path(original_filename).name
        safe_filename = re.sub(
            r"[^A-Za-z0-9._-]",
            "_",
            safe_filename,
        )

        file_hash = hashlib.sha256(file_content).hexdigest()

        category_directory = self.base_directory / category
        category_directory.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid4().hex}_{safe_filename}"
        file_path = (category_directory / stored_filename).resolve()

        if not file_path.is_relative_to(self.base_directory):
            raise ValueError("Invalid storage path.")

        with file_path.open("xb") as file:
            file.write(file_content)

        return {
            "original_filename": safe_filename,
            "storage_path": str(file_path),
            "file_hash": file_hash,
            "file_size": len(file_content),
            "category": category,
        }

    def delete_file(self, storage_path: str) -> None:

        file_path = Path(storage_path).resolve()

        if not file_path.is_relative_to(self.base_directory):
            raise ValueError("Cannot delete files outside storage directory.")

        if file_path.is_file():
            file_path.unlink()

    def file_exists(self, storage_path: str) -> bool:

        file_path = Path(storage_path).resolve()

        if not file_path.is_relative_to(self.base_directory):
            return False

        return file_path.is_file()

