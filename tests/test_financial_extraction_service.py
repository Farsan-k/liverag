
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.analysis import service
from app.analysis.extraction import ExtractionResult
from app import crud
from app.database import Base
from app.models import Company, FinancialDocument
from app.storage.local import LocalStorageService
from decimal import Decimal

# ============================================================
# EXISTING TEST FIXTURE
# ============================================================

@pytest.fixture
def mock_document(monkeypatch):
    document = {
        "id": 1,
        "document_id": None,
        "original_filename": "apple_report.html",
        "storage_path": "financial_documents/sec/apple_report.html",
        "file_type": "html",
        "file_hash": "a" * 64,
        "company": "Apple",
        "expected_cik": "0000320193",
        "extraction_status": "pending",
    }

    monkeypatch.setattr(
        service,
        "get_financial_document",
        lambda document_id: document,
    )

    return document


# ============================================================
# EXISTING UNIT TESTS
# ============================================================

def test_extract_financial_document_success(
    monkeypatch,
    mock_document,
):
    storage = MagicMock()
    storage.file_exists.return_value = True

    monkeypatch.setattr(
        service,
        "get_storage_service",
        lambda: storage,
    )

    status_updates = []

    monkeypatch.setattr(
        service,
        "update_financial_document_extraction_status",
        lambda document_id, status: status_updates.append(status),
    )

    expected_result = ExtractionResult(
        source_type="sec_xbrl",
        filename="apple_report.html",
        metrics=[],
    )

    registry = MagicMock()
    registry.extract.return_value = expected_result

    monkeypatch.setattr(
        service,
        "create_default_registry",
        lambda: registry,
    )

    # Mock metric persistence to isolate this unit test
    # from the actual PostgreSQL database.
    persisted_metrics = []

    monkeypatch.setattr(
        service,
        "create_financial_metrics",
        lambda source_document_id, metrics: (
            persisted_metrics.append({
                "source_document_id": source_document_id,
                "metrics": metrics,
            })
        ),
    )

    result = service.extract_financial_document(1)

    # Verify extraction result.
    assert result == expected_result

    # Verify extraction status lifecycle.
    assert status_updates == [
        "processing",
        "completed",
    ]

    # Verify registry execution.
    registry.extract.assert_called_once()

    # Verify metric persistence.
    assert len(persisted_metrics) == 1
    assert persisted_metrics[0]["source_document_id"] == 1
    assert persisted_metrics[0]["metrics"] == []


def test_extract_rejects_missing_document(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_financial_document",
        lambda document_id: None,
    )

    with pytest.raises(ValueError, match="not found"):
        service.extract_financial_document(999)


def test_extract_rejects_missing_file(
    monkeypatch,
    mock_document,
):
    storage = MagicMock()
    storage.file_exists.return_value = False

    monkeypatch.setattr(
        service,
        "get_storage_service",
        lambda: storage,
    )

    status_updates = []

    monkeypatch.setattr(
        service,
        "update_financial_document_extraction_status",
        lambda document_id, status: status_updates.append(status),
    )

    with pytest.raises(FileNotFoundError):
        service.extract_financial_document(1)

    assert status_updates == ["failed"]


def test_extraction_failure_updates_status(
    monkeypatch,
    mock_document,
):
    storage = MagicMock()
    storage.file_exists.return_value = True

    monkeypatch.setattr(
        service,
        "get_storage_service",
        lambda: storage,
    )

    status_updates = []

    monkeypatch.setattr(
        service,
        "update_financial_document_extraction_status",
        lambda document_id, status: status_updates.append(status),
    )

    registry = MagicMock()
    registry.extract.side_effect = ValueError("Extraction failed")

    monkeypatch.setattr(
        service,
        "create_default_registry",
        lambda: registry,
    )

    with pytest.raises(ValueError, match="Extraction failed"):
        service.extract_financial_document(1)

    assert status_updates == ["processing", "failed"]


# ============================================================
# REAL SEC EXTRACTION INTEGRATION TEST FIXTURE
# ============================================================

@pytest.fixture
def real_sec_extraction_environment(
    tmp_path,
    monkeypatch,
):
    # Locate the actual Apple SEC filing.
    source_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "raw"
        / "apple_2026_q3_10q.xml"
    )

    assert source_path.is_file(), (
        f"Apple SEC XML fixture not found: {source_path}"
    )

    # Create isolated real file storage.
    storage = LocalStorageService(
        str(tmp_path / "financial_storage")
    )

    stored_file = storage.save_file(
        file_content=source_path.read_bytes(),
        original_filename="apple_2026_q3_10q.xml",
        category="sec",
    )

    # Create an isolated SQLite database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    # Make real CRUD functions use the isolated database.
    monkeypatch.setattr(
        crud,
        "SessionLocal",
        TestingSessionLocal,
    )

    session = TestingSessionLocal()

    try:
        company = Company(
            cik="0000320193",
            canonical_name="Apple Inc.",
            normalized_name="apple",
        )

        session.add(company)
        session.flush()

        document = FinancialDocument(
            original_filename="apple_2026_q3_10q.xml",
            storage_path=stored_file["storage_path"],
            file_type="xml",
            file_hash=stored_file["file_hash"],
            company="Apple Inc.",
            expected_cik="0000320193",
            company_id=company.id,
            extraction_status="pending",
        )

        session.add(document)
        session.commit()

        document_id = document.id

    finally:
        session.close()

    # Use the real LocalStorageService.
    monkeypatch.setattr(
        service,
        "get_storage_service",
        lambda: storage,
    )

    yield document_id

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ============================================================
# REAL SEC QUARTERLY EXTRACTION END-TO-END TEST
# ============================================================


def test_real_sec_quarterly_extraction_end_to_end(
    real_sec_extraction_environment,
):
    document_id = real_sec_extraction_environment

    # Execute the real extraction workflow.
    # No extractor or metric-persistence mocks are used.
    result = service.extract_financial_document(document_id)

    # Verify extraction produced financial metrics.
    assert result.source_type == "sec_xbrl"
    assert len(result.metrics) > 0

    # --------------------------------------------------------
    # 1. Verify expected fiscal reporting periods.
    # --------------------------------------------------------

    extracted_periods = {
        (
            metric.period.fiscal_year,
            metric.period.fiscal_period,
            metric.period.period_scope,
        )
        for metric in result.metrics
        if metric.period.period_type == "duration"
    }

    expected_periods = {
        (2025, "FY", "annual"),
        (2025, "Q3", "standalone"),
        (2025, "Q3", "ytd"),
        (2026, "Q3", "standalone"),
        (2026, "Q3", "ytd"),
    }

    assert expected_periods.issubset(extracted_periods)

    # --------------------------------------------------------
    # 2. Verify actual consolidated financial values.
    # --------------------------------------------------------

    # Exclude dimensional facts such as product and segment revenue.
    consolidated_metrics = [
        metric
        for metric in result.metrics
        if not metric.dimensions
    ]

    def get_values(metric_name, period_scope):
        return {
            metric.value
            for metric in consolidated_metrics
            if metric.metric.lower() == metric_name.lower()
            and metric.period.fiscal_year == 2026
            and metric.period.fiscal_period == "Q3"
            and metric.period.period_scope == period_scope
        }

    # Q3 FY2026 standalone revenue.
    assert Decimal("109417000000") in get_values(
        "Revenue",
        "standalone",
    )

    # Q3 FY2026 year-to-date revenue.
    assert Decimal("364357000000") in get_values(
        "Revenue",
        "ytd",
    )

    # Q3 FY2026 standalone net income.
    assert Decimal("29789000000") in get_values(
        "Net Income",
        "standalone",
    )

    # Q3 FY2026 year-to-date net income.
    assert Decimal("101464000000") in get_values(
        "Net Income",
        "ytd",
    )

    # --------------------------------------------------------
    # 3. Verify database persistence.
    # --------------------------------------------------------

    persisted_metrics = crud.get_financial_metrics(
        source_document_id=document_id,
    )

    assert len(persisted_metrics) == len(result.metrics)

    persisted_periods = {
        (
            record["fiscal_year"],
            record["fiscal_period"],
            record["period_scope"],
        )
        for record in persisted_metrics
    }

    assert expected_periods.issubset(persisted_periods)

    # --------------------------------------------------------
    # 4. Verify persisted financial values.
    # --------------------------------------------------------

    persisted_consolidated_metrics = [
        record
        for record in persisted_metrics
        if not record["dimensions"]
    ]

    def get_persisted_values(metric_name, period_scope):
        return {
            record["value"]
            for record in persisted_consolidated_metrics
            if record["metric"].lower() == metric_name.lower()
            and record["fiscal_year"] == 2026
            and record["fiscal_period"] == "Q3"
            and record["period_scope"] == period_scope
        }

    assert Decimal("109417000000") in get_persisted_values(
        "Revenue",
        "standalone",
    )

    assert Decimal("364357000000") in get_persisted_values(
        "Revenue",
        "ytd",
    )

    assert Decimal("29789000000") in get_persisted_values(
        "Net Income",
        "standalone",
    )

    assert Decimal("101464000000") in get_persisted_values(
        "Net Income",
        "ytd",
    )

    # --------------------------------------------------------
    # 5. Verify standalone and YTD remain distinguishable.
    # --------------------------------------------------------

    q3_2026_records = [
        record
        for record in persisted_metrics
        if record["fiscal_year"] == 2026
        and record["fiscal_period"] == "Q3"
    ]

    q3_scopes = {
        record["period_scope"]
        for record in q3_2026_records
    }

    assert "standalone" in q3_scopes
    assert "ytd" in q3_scopes

    # --------------------------------------------------------
    # 6. Verify extraction status.
    # --------------------------------------------------------

    document = crud.get_financial_document(document_id)

    assert document["extraction_status"] == "completed"

