
from pathlib import Path
from typing import Protocol


class StorageService(Protocol):

    def save_file(
        self,
        file_content: bytes,
        original_filename: str,
        category: str,
    ) -> dict:
        ...

    def delete_file(self, storage_path: str) -> None:
        ...

    def file_exists(self, storage_path: str) -> bool:
        ...
