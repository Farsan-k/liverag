
import pymupdf
from pathlib import Path
from typing import Any


def extract_pdf_text(pdf_path: str | Path) -> dict[str, Any]:
    """
    Extract text from a PDF page by page.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dictionary containing PDF metadata and extracted pages.
    """

    file_path = Path(pdf_path)

    # Validate file existence
    if not file_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {file_path}"
        )

    # Validate that the path points to a file
    if not file_path.is_file():
        raise ValueError(
            f"Expected a file, got: {file_path}"
        )

    # Validate PDF extension
    if file_path.suffix.lower() != ".pdf":
        raise ValueError(
            "The provided file must be a PDF."
        )

    pages = []

    try:
        with pymupdf.open(file_path) as pdf:

            # Validate PDF page count
            if len(pdf) == 0:
                raise ValueError(
                    "The PDF contains no pages."
                )

            # Extract PDF metadata
            metadata = pdf.metadata

            # Extract text page by page
            for page_number, page in enumerate(pdf, start=1):

                text = page.get_text("text").strip()

                pages.append({
                    "page_number": page_number,
                    "text": text,
                    "character_count": len(text),
                    "has_text": bool(text),
                })

            return {
                "filename": file_path.name,
                "metadata": metadata,
                "total_pages": len(pdf),
                "pages": pages,
            }

    except pymupdf.FileDataError as error:
        raise ValueError(
            f"Invalid or unreadable PDF file: {file_path}"
        ) from error
