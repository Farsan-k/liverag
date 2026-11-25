
from app.storage.local import LocalStorageService


def get_storage_service() -> LocalStorageService:
    return LocalStorageService()
