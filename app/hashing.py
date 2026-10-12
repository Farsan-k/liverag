
import hashlib


def calculate_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
