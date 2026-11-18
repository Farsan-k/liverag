
from pathlib import Path

from app.pdf_extractor import extract_pdf_text


PDF_PATH = Path("data/raw/apple_10K.pdf")


def test_apple_pdf_extraction():
    result = extract_pdf_text(PDF_PATH)

    print("\nFilename:", result["filename"])
    print("Total pages:", result["total_pages"])

    print("\nFirst page:")
    print(result["pages"][0]["text"])

    print("\nLast page:")
    print(result["pages"][-1]["text"])

    # Validate PDF metadata and structure
    assert result["filename"] == "apple_10K.pdf"
    assert result["total_pages"] == 80
    assert len(result["pages"]) == 80
    assert isinstance(result["metadata"], dict)

    # Validate page structure
    for page in result["pages"]:
        assert "page_number" in page
        assert "text" in page
        assert "character_count" in page
        assert "has_text" in page

        assert isinstance(page["text"], str)
        assert page["character_count"] == len(page["text"])
        assert page["has_text"] == bool(page["text"])

    # Validate first and last pages
    assert result["pages"][0]["text"]
    assert result["pages"][-1]["text"]

    # Validate all pages contain extracted text
    assert all(page["has_text"] for page in result["pages"])
