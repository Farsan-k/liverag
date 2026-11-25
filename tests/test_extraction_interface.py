
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.analysis.extraction import (
    ExtractionRequest,
    ExtractionResult,
)


def test_valid_extraction_request():
    request = ExtractionRequest(
        file_path=Path("data/raw/report.pdf"),
        company="Apple",
        start_date=date(2024, 9, 29),
        end_date=date(2025, 9, 27),
    )

    assert request.company == "Apple"
    assert request.file_path == Path("data/raw/report.pdf")


def test_extraction_request_rejects_single_reporting_date():
    with pytest.raises(ValidationError):
        ExtractionRequest(
            file_path=Path("report.pdf"),
            start_date=date(2024, 1, 1),
        )


def test_extraction_request_rejects_invalid_date_range():
    with pytest.raises(ValidationError):
        ExtractionRequest(
            file_path=Path("report.pdf"),
            start_date=date(2025, 1, 1),
            end_date=date(2024, 1, 1),
        )


def test_empty_extraction_result():
    result = ExtractionResult(
        source_type="pdf",
        filename="report.pdf",
    )

    assert result.metrics == []
    assert result.warnings == []
    assert result.metadata == {}


def test_extraction_result_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ExtractionResult(
            source_type="pdf",
            filename="report.pdf",
            unknown_field="invalid",
        )
