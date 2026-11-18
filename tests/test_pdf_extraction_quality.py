
from pathlib import Path

from app.pdf_extractor import extract_pdf_text


def test_pdf_extraction_quality():
    pdf_path = Path("data/raw/apple_10K.pdf")
    result = extract_pdf_text(pdf_path)

    pages = result["pages"]

    empty_pages = [
        page["page_number"]
        for page in pages
        if not page["text"].strip()
    ]

    short_pages = [
        (page["page_number"], page["character_count"])
        for page in pages
        if 0 < page["character_count"] < 100
    ]

    total_characters = sum(
        page["character_count"] for page in pages
    )

    pages_with_text = sum(
        1 for page in pages if page["has_text"]
    )

    extraction_coverage = pages_with_text / result["total_pages"]

    print("\n========== PDF QUALITY REPORT ==========")
    print("Total pages:", result["total_pages"])
    print("Total characters:", total_characters)
    print("Pages with text:", pages_with_text)
    print(f"Extraction coverage: {extraction_coverage:.2%}")
    print("Empty pages:", empty_pages)
    print("Short pages:", short_pages)

    print("\nSample page character counts:")
    for page in pages[:10]:
        print(
            f"Page {page['page_number']}: "
            f"{page['character_count']} characters"
        )

    # Basic quality checks
    assert result["total_pages"] == 80
    assert not empty_pages
    assert total_characters > 0
    assert extraction_coverage >= 0.95
