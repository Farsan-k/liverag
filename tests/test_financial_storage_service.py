
import hashlib
from datetime import date
from decimal import Decimal

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.storage import service
from app import crud
from app.database import Base
from app.models import Company, FinancialDocument
from app.analysis.schemas import (
    FinancialMetric,
    ReportingPeriod,
    SourceProvenance,
    FinancialEvidence,
)
from sqlalchemy.orm import Session
from types import SimpleNamespace

# ============================================================
# EXISTING FILE STORAGE TESTS
# ============================================================

def test_store_new_financial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        service,
        "get_storage_service",
        lambda: __import__(
            "app.storage.local",
            fromlist=["LocalStorageService"],
        ).LocalStorageService(str(tmp_path)),
    )

    content = b"Finova financial report"

    def mock_create(**kwargs):
        return {
            "id": 1,
            "file_hash": kwargs["file_hash"],
            "storage_path": kwargs["storage_path"],
            "duplicate": False,
        }

    monkeypatch.setattr(
        service,
        "create_financial_document",
        mock_create,
    )

    result = service.store_financial_file(
        file_content=content,
        original_filename="report.pdf",
        file_type="pdf",
        category="pdf",
    )

    assert result["id"] == 1
    assert result["duplicate"] is False
    assert result["file_hash"] == hashlib.sha256(content).hexdigest()
    assert result["file_size"] == len(content)
    assert __import__("pathlib").Path(
        result["storage_path"]
    ).exists()


def test_duplicate_file_removes_new_physical_copy(
    tmp_path,
    monkeypatch,
):
    from app.storage.local import LocalStorageService

    monkeypatch.setattr(
        service,
        "get_storage_service",
        lambda: LocalStorageService(str(tmp_path)),
    )

    def mock_create(**kwargs):
        return {
            "id": 10,
            "file_hash": kwargs["file_hash"],
            "storage_path": "existing/file.pdf",
            "duplicate": True,
        }

    monkeypatch.setattr(
        service,
        "create_financial_document",
        mock_create,
    )

    result = service.store_financial_file(
        file_content=b"same report",
        original_filename="duplicate.pdf",
        file_type="pdf",
        category="pdf",
    )

    assert result["duplicate"] is True
    assert not list(tmp_path.rglob("*_duplicate.pdf"))


def test_database_failure_removes_saved_file(
    tmp_path,
    monkeypatch,
):
    from app.storage.local import LocalStorageService

    monkeypatch.setattr(
        service,
        "get_storage_service",
        lambda: LocalStorageService(str(tmp_path)),
    )

    def mock_create(**kwargs):
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(
        service,
        "create_financial_document",
        mock_create,
    )

    with pytest.raises(RuntimeError):
        service.store_financial_file(
            file_content=b"test report",
            original_filename="failure.pdf",
            file_type="pdf",
            category="pdf",
        )

    assert not list(tmp_path.rglob("*_failure.pdf"))


# ============================================================
# QUARTERLY FINANCIAL METRIC DATABASE TESTS
# ============================================================

@pytest.fixture
def financial_db(monkeypatch):
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
            original_filename="apple_2026_q3.xml",
            storage_path="financial_documents/apple_2026_q3.xml",
            file_type="xml",
            file_hash="a" * 64,
            company="Apple Inc.",
            expected_cik="0000320193",
            company_id=company.id,
            extraction_status="completed",
        )

        session.add(document)
        session.commit()

        yield document.id

    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_store_and_retrieve_quarterly_financial_metrics(
    financial_db,
):
    standalone = FinancialMetric(
        company="Apple Inc.",
        metric="Revenue",
        value=Decimal("109417000000"),
        unit="USD",
        currency="USD",
        period=ReportingPeriod(
            label="Q3 FY2026",
            period_type="duration",
            start_date=date(2026, 3, 29),
            end_date=date(2026, 6, 27),
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="standalone",
        ),
        source=SourceProvenance(
            source_type="sec_xbrl",
            source_document_id=financial_db,
            filename="apple_2026_q3.xml",
        ),
        evidence=FinancialEvidence(
            text="Apple reported Q3 FY2026 revenue."
        ),
        confidence=0.99,
    )

    ytd = FinancialMetric(
        company="Apple Inc.",
        metric="Revenue",
        value=Decimal("364357000000"),
        unit="USD",
        currency="USD",
        period=ReportingPeriod(
            label="Q3 FY2026 YTD",
            period_type="duration",
            start_date=date(2025, 9, 28),
            end_date=date(2026, 6, 27),
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="ytd",
        ),
        source=SourceProvenance(
            source_type="sec_xbrl",
            source_document_id=financial_db,
            filename="apple_2026_q3.xml",
        ),
        evidence=FinancialEvidence(
            text="Apple reported FY2026 year-to-date revenue."
        ),
        confidence=0.99,
    )

    saved = crud.create_financial_metrics(
        source_document_id=financial_db,
        metrics=[standalone, ytd],
    )

    assert len(saved) == 2

    retrieved = crud.get_financial_metrics(
        source_document_id=financial_db,
    )

    assert len(retrieved) == 2

    standalone_record = next(
        record
        for record in retrieved
        if record["period_scope"] == "standalone"
    )

    ytd_record = next(
        record
        for record in retrieved
        if record["period_scope"] == "ytd"
    )

    # Verify standalone quarterly metric.
    assert standalone_record["fiscal_year"] == 2026
    assert standalone_record["fiscal_period"] == "Q3"
    assert standalone_record["period_scope"] == "standalone"
    assert standalone_record["value"] == Decimal("109417000000")

    # Verify year-to-date metric.
    assert ytd_record["fiscal_year"] == 2026
    assert ytd_record["fiscal_period"] == "Q3"
    assert ytd_record["period_scope"] == "ytd"
    assert ytd_record["value"] == Decimal("364357000000")




def test_failed_metric_replacement_preserves_existing_metrics(
    financial_db,
    monkeypatch,
):
    def make_metric(value: str, evidence_text: str) -> FinancialMetric:
        return FinancialMetric(
            company="Apple Inc.",
            metric="Revenue",
            value=Decimal(value),
            unit="USD",
            currency="USD",
            period=ReportingPeriod(
                label="Q3 FY2026",
                period_type="duration",
                start_date=date(2026, 3, 29),
                end_date=date(2026, 6, 27),
                fiscal_year=2026,
                fiscal_period="Q3",
                period_scope="standalone",
            ),
            source=SourceProvenance(
                source_type="sec_xbrl",
                source_document_id=financial_db,
                filename="apple_2026_q3.xml",
            ),
            evidence=FinancialEvidence(text=evidence_text),
            confidence=0.99,
        )

    original_metric = make_metric(
        "109417000000",
        "Original Q3 FY2026 revenue.",
    )

    replacement_metric = make_metric(
        "120000000000",
        "Replacement Q3 FY2026 revenue.",
    )

    # Save the original metric.
    crud.create_financial_metrics(
        source_document_id=financial_db,
        metrics=[original_metric],
    )

    # Confirm the original metric exists.
    before = crud.get_financial_metrics(
        source_document_id=financial_db,
    )

    assert len(before) == 1
    assert before[0]["value"] == Decimal("109417000000")

    # Force an insertion failure during replacement.
    def fail_on_add(self, instance, _warn=True):
        raise RuntimeError("Simulated database insertion failure")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "add", fail_on_add)

        with pytest.raises(
            RuntimeError,
            match="Simulated database insertion failure",
        ):
            crud.create_financial_metrics(
                source_document_id=financial_db,
                metrics=[replacement_metric],
            )

    # The transaction should have rolled back.
    after = crud.get_financial_metrics(
        source_document_id=financial_db,
    )

    assert len(after) == 1
    assert after[0]["value"] == Decimal("109417000000")
    assert after[0]["fiscal_year"] == 2026
    assert after[0]["fiscal_period"] == "Q3"
    assert after[0]["period_scope"] == "standalone"




def test_create_financial_document_links_verified_company(
    monkeypatch,
):
    company = SimpleNamespace(
        id=1,
        canonical_name="Apple Inc.",
        cik="0000320193",
    )

    document = SimpleNamespace(
        id=50,
        company_id=None,
    )

    class FakeResult:
        def scalar_one_or_none(self):
            return 50

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, statement):
            return FakeResult()

        def get(self, model, document_id):
            assert model is FinancialDocument
            assert document_id == 50
            return document

        def flush(self):
            pass

    fake_session = FakeSession()

    monkeypatch.setattr(
        crud,
        "SessionLocal",
        SimpleNamespace(begin=lambda: fake_session),
    )

    def mock_resolve_company(session, name=None, cik=None):
        assert session is fake_session
        assert name == "Apple Inc."
        assert cik == "0000320193"

        return {
            "status": "resolved",
            "company": company,
            "candidates": [company],
            "match_type": "cik",
        }

    monkeypatch.setattr(
        crud,
        "resolve_company",
        mock_resolve_company,
    )

    monkeypatch.setattr(
        crud,
        "_financial_document_to_dict",
        lambda doc, duplicate=False: {
            "id": doc.id,
            "company_id": doc.company_id,
            "duplicate": duplicate,
        },
    )

    result = crud.create_financial_document(
        original_filename="apple_test.xml",
        storage_path="financial_documents/apple_test.xml",
        file_type="xml",
        file_hash="b" * 64,
        company="Apple Inc.",
        expected_cik="0000320193",
    )

    assert document.company_id == 1
    assert result["company_id"] == 1
    assert result["duplicate"] is False
