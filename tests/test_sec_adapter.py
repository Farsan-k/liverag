
from datetime import date
from decimal import Decimal

import pytest

import app.analysis.sec_adapter as sec_adapter
from app.analysis.extraction import ExtractionRequest


@pytest.fixture
def sec_data(monkeypatch):
    context = {
        "context_id": "FY2025",
        "identifier": "0000320193",
        "identifier_scheme": "http://www.sec.gov/CIK",
        "period_type": "duration",
        "start_date": "2024-09-29",
        "end_date": "2025-09-27",
        "instant": None,
        "dimensions": [],
    }

    facts = [
        {
            "name": "Revenue",
            "context_ref": "FY2025",
            "unit_ref": "USD",
            "scale": "6",
            "sign": None,
            "decimals": "-6",
            "format": None,
            "fact_id": "fact-001",
            "raw_value": "100",
        }
    ]

    contexts = {"FY2025": context}
    units = {"USD": ["iso4217:USD"]}

    enriched = [
        {
            **facts[0],
            "context": context,
            "unit_measures": ["iso4217:USD"],
        }
    ]

    filing_metadata = {
        "document_type": "10-K",
        "fiscal_year_focus": 2025,
        "fiscal_period_focus": "FY",
        "document_period_end_date": "2025-09-27",
    }

    monkeypatch.setattr(
        sec_adapter,
        "load_sec_report",
        lambda path: object(),
    )

    monkeypatch.setattr(
        sec_adapter,
        "extract_filing_metadata",
        lambda soup: filing_metadata,
    )

    monkeypatch.setattr(
        sec_adapter,
        "extract_contexts",
        lambda soup: contexts,
    )

    monkeypatch.setattr(
        sec_adapter,
        "extract_numeric_facts",
        lambda soup: facts,
    )

    monkeypatch.setattr(
        sec_adapter,
        "extract_units",
        lambda soup: units,
    )

    monkeypatch.setattr(
        sec_adapter,
        "enrich_facts_with_contexts",
        lambda facts, contexts, units: enriched,
    )


def test_extracts_standardized_revenue_metric(sec_data):
    extractor = sec_adapter.SECXBRLExtractor()

    request = ExtractionRequest(
        file_path="report.html",
        company="Apple",
        source_document_id=10,
        expected_cik="0000320193",
    )

    result = extractor.extract(request)

    assert result.source_type == "sec_xbrl"
    assert result.filename == "report.html"
    assert len(result.metrics) == 1

    metric = result.metrics[0]

    assert metric.company == "Apple"
    assert metric.metric == "Revenue"
    assert metric.value == Decimal("100000000")
    assert metric.currency == "USD"
    assert metric.period.period_type == "duration"
    assert metric.period.start_date == date(2024, 9, 29)
    assert metric.period.end_date == date(2025, 9, 27)

    assert metric.source.fact_id == "fact-001"
    assert metric.source.context_ref == "FY2025"
    assert metric.source.source_document_id == 10


def test_extract_preserves_source_evidence(sec_data):
    result = sec_adapter.SECXBRLExtractor().extract(
        ExtractionRequest(
            file_path="report.html",
        )
    )

    metric = result.metrics[0]

    assert metric.evidence.text == "100"
    assert metric.evidence.original_label == "Revenue"
    assert metric.evidence.extraction_method == (
        "SEC Inline XBRL numeric fact"
    )


def test_extract_rejects_wrong_cik(sec_data):
    result = sec_adapter.SECXBRLExtractor().extract(
        ExtractionRequest(
            file_path="report.html",
            expected_cik="0000789019",
        )
    )

    assert result.metrics == []
    assert result.metadata["skipped_fact_counts"]["cik_mismatch"] == 1


def test_extract_filters_reporting_period(sec_data):
    result = sec_adapter.SECXBRLExtractor().extract(
        ExtractionRequest(
            file_path="report.html",
            start_date=date(2023, 9, 24),
            end_date=date(2024, 9, 28),
        )
    )

    assert result.metrics == []
    assert result.metadata["skipped_fact_counts"]["period_mismatch"] == 1


def test_extract_rejects_unsupported_extension():
    extractor = sec_adapter.SECXBRLExtractor()

    with pytest.raises(
        ValueError,
        match="Unsupported SEC report extension",
    ):
        extractor.extract(
            ExtractionRequest(
                file_path="report.pdf",
            )
        )


def test_extract_rejects_invalid_cik():
    extractor = sec_adapter.SECXBRLExtractor()

    with pytest.raises(ValueError, match="10 digits"):
        extractor.extract(
            ExtractionRequest(
                file_path="report.html",
                expected_cik="12345",
            )
        )


def test_extract_preserves_dimensions(sec_data, monkeypatch):
    enriched = [
        {
            "name": "Revenue",
            "context_ref": "SEGMENT",
            "unit_ref": "USD",
            "raw_value": "50",
            "scale": "6",
            "sign": None,
            "format": None,
            "fact_id": "fact-segment",
            "context": {
                "period_type": "duration",
                "start_date": "2024-09-29",
                "end_date": "2025-09-27",
                "dimensions": [
                    {
                        "type": "explicit",
                        "axis": "us-gaap:ProductOrServiceAxis",
                        "member": "us-gaap:iPhoneMember",
                    }
                ],
            },
            "unit_measures": ["iso4217:USD"],
        }
    ]

    monkeypatch.setattr(
        sec_adapter,
        "enrich_facts_with_contexts",
        lambda facts, contexts, units: enriched,
    )

    result = sec_adapter.SECXBRLExtractor().extract(
        ExtractionRequest(file_path="report.html")
    )

    assert result.metrics[0].dimensions == {
        "us-gaap:ProductOrServiceAxis": "us-gaap:iPhoneMember"
    }


@pytest.mark.parametrize(
    "start_date,end_date,expected",
    [
        (
            date(2026, 3, 29),
            date(2026, 6, 27),
            (2026, "Q3", "standalone"),
        ),
        (
            date(2025, 9, 28),
            date(2026, 6, 27),
            (2026, "Q3", "ytd"),
        ),
        (
            date(2025, 3, 30),
            date(2025, 6, 28),
            (2025, "Q3", "standalone"),
        ),
        (
            date(2024, 9, 29),
            date(2025, 6, 28),
            (2025, "Q3", "ytd"),
        ),
        (
            date(2024, 9, 29),
            date(2025, 9, 27),
            (2025, "FY", "annual"),
        ),
    ],
)
def test_classifies_apple_q3_fiscal_periods(
    start_date,
    end_date,
    expected,
):
    filing_metadata = {
        "document_type": "10-Q",
        "fiscal_year_focus": 2026,
        "fiscal_period_focus": "Q3",
        "document_period_end_date": "2026-06-27",
    }

    result = sec_adapter.SECXBRLExtractor._classify_duration_period(
        start_date=start_date,
        end_date=end_date,
        filing_metadata=filing_metadata,
    )

    assert result == expected
