
import pytest

from app.analysis.extraction import ExtractionRequest
from app.analysis.registry import (
    ExtractorRegistry,
    create_default_registry,
)
from app.analysis.sec_adapter import SECXBRLExtractor


def test_default_registry_registers_sec_extensions():
    registry = create_default_registry()

    for extension in (".html", ".htm", ".xhtml", ".xml"):
        extractor = registry.get_extractor(
            f"report{extension}"
        )

        assert isinstance(extractor, SECXBRLExtractor)


def test_registry_is_case_insensitive():
    registry = create_default_registry()

    extractor = registry.get_extractor("REPORT.HTML")

    assert isinstance(extractor, SECXBRLExtractor)


def test_registry_rejects_unsupported_extension():
    registry = create_default_registry()

    with pytest.raises(ValueError, match="No financial extractor registered"):
        registry.get_extractor("report.pdf")


def test_registry_rejects_unknown_extension():
    registry = create_default_registry()

    with pytest.raises(ValueError, match="unknown"):
        registry.get_extractor("financial_report")


def test_registry_rejects_duplicate_extensions():
    registry = ExtractorRegistry()

    registry.register(SECXBRLExtractor())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(SECXBRLExtractor())
