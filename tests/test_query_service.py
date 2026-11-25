
from datetime import date
from decimal import Decimal

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.company_identity import (
    add_company_alias,
    create_or_get_company,
)

from app.analysis.fact_selection import FactSelectionRequest
from app.analysis import query_service


@pytest.fixture
def db(monkeypatch):
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
        query_service,
        "SessionLocal",
        TestingSessionLocal,
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def apple_company(db):
    company = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    add_company_alias(
        db,
        company.id,
        "AAPL",
    )

    add_company_alias(
        db,
        company.id,
        "Apple",
    )

    db.commit()

    return company


def make_metric_record(
    company_name="Apple Inc.",
    fiscal_year=None,
    fiscal_period=None,
    period_scope="unknown",
):
    return {
        "id": 1,
        "source_document_id": 1,
        "company_id": 1,
        "company": company_name,
        "metric": "Revenue",
        "value": Decimal("100000000"),
        "unit": "USD",
        "currency": "USD",
        "period_type": "duration",
        "period_label": "FY2025",
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 12, 31),
        "instant_date": None,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_scope": period_scope,
        "source_type": "sec_xbrl",
        "provenance": {
            "source_type": "sec_xbrl",
            "source_document_id": 1,
        },
        "evidence": {
            "text": "Reported financial revenue."
        },
        "dimensions": {},
        "confidence": 0.99,
        "created_at": None,
    }


def test_resolve_metric_using_canonical_company_name(
    db,
    apple_company,
    monkeypatch,
):
    calls = []

    def fake_get_financial_metrics(**kwargs):
        calls.append(kwargs)
        return [make_metric_record()]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    request = FactSelectionRequest(
        metric="Revenue",
        company="Apple Inc.",
        period_start="2024-01-01",
        period_end="2024-12-31",
        currency="USD",
        unit="USD",
    )

    result = query_service.resolve_metric_from_database(
        request
    )

    assert result.status == "resolved"
    assert result.selected is not None
    assert result.selected.company == "Apple Inc."

    assert calls[0]["company_id"] == apple_company.id
    assert calls[0]["metric"] == "Revenue"


def test_resolve_metric_using_apple_alias(
    db,
    apple_company,
    monkeypatch,
):
    calls = []

    def fake_get_financial_metrics(**kwargs):
        calls.append(kwargs)
        return [make_metric_record()]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    request = FactSelectionRequest(
        metric="Revenue",
        company="Apple",
        period_start="2024-01-01",
        period_end="2024-12-31",
        currency="USD",
        unit="USD",
    )

    result = query_service.resolve_metric_from_database(
        request
    )

    assert result.status == "resolved"
    assert result.selected.company == "Apple Inc."
    assert calls[0]["company_id"] == apple_company.id


def test_resolve_metric_using_ticker_alias(
    db,
    apple_company,
    monkeypatch,
):
    calls = []

    def fake_get_financial_metrics(**kwargs):
        calls.append(kwargs)
        return [make_metric_record()]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    request = FactSelectionRequest(
        metric="Revenue",
        company="AAPL",
        period_start="2024-01-01",
        period_end="2024-12-31",
        currency="USD",
        unit="USD",
    )

    result = query_service.resolve_metric_from_database(
        request
    )

    assert result.status == "resolved"
    assert result.selected.company == "Apple Inc."
    assert calls[0]["company_id"] == apple_company.id


def test_unknown_company_returns_not_found(
    db,
    monkeypatch,
):
    def unexpected_database_call(**kwargs):
        pytest.fail(
            "Metric retrieval should not happen for an unknown company."
        )

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        unexpected_database_call,
    )

    request = FactSelectionRequest(
        metric="Revenue",
        company="Unknown Company",
    )

    result = query_service.resolve_metric_from_database(
        request
    )

    assert result.status == "not_found"
    assert result.selected is None


def test_ambiguous_company_alias_is_rejected(
    db,
    monkeypatch,
):
    first = create_or_get_company(
        db,
        canonical_name="Example Holdings One",
        cik="0000000001",
    )

    second = create_or_get_company(
        db,
        canonical_name="Example Holdings Two",
        cik="0000000002",
    )

    add_company_alias(
        db,
        first.id,
        "Example Group",
    )

    add_company_alias(
        db,
        second.id,
        "Example Group",
    )

    db.commit()

    def unexpected_database_call(**kwargs):
        pytest.fail(
            "Metric retrieval should not happen for an ambiguous company."
        )

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        unexpected_database_call,
    )

    request = FactSelectionRequest(
        metric="Revenue",
        company="Example Group",
    )

    result = query_service.resolve_metric_from_database(
        request
    )

    assert result.status == "ambiguous"
    assert result.selected is None


def test_reporting_periods_use_verified_company_id(
    db,
    apple_company,
    monkeypatch,
):
    calls = []

    def fake_get_financial_metrics(**kwargs):
        calls.append(kwargs)

        return [
            make_metric_record(),
        ]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    periods = query_service.get_available_reporting_periods(
        company="AAPL",
        metric="Revenue",
    )

    assert len(periods) == 1

    assert periods[0]["start_date"] == date(2024, 1, 1)
    assert periods[0]["end_date"] == date(2024, 12, 31)

    assert calls[0]["company_id"] == apple_company.id
    assert calls[0]["metric"] == "Revenue"



def test_fiscal_year_resolution_with_company_alias(
    db,
    apple_company,
    monkeypatch,
):
    def fake_get_financial_metrics(**kwargs):
        assert kwargs["company_id"] == apple_company.id

        record = make_metric_record()

        # FY2025 must have a reporting period ending in 2025.
        record["start_date"] = date(2025, 1, 1)
        record["end_date"] = date(2025, 12, 31)
        record["period_label"] = "FY2025"

        return [record]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    period = query_service.resolve_fiscal_year_period(
        company="AAPL",
        metric="Revenue",
        fiscal_year="FY2025",
    )

    assert period is not None
    assert period["period_label"] == "FY2025"
    assert period["start_date"] == date(2025, 1, 1)
    assert period["end_date"] == date(2025, 12, 31)



def test_metric_retrieval_is_not_called_for_ambiguous_period_company(
    db,
    monkeypatch,
):
    first = create_or_get_company(
        db,
        canonical_name="Example Holdings One",
        cik="0000000001",
    )

    second = create_or_get_company(
        db,
        canonical_name="Example Holdings Two",
        cik="0000000002",
    )

    add_company_alias(db, first.id, "Example Group")
    add_company_alias(db, second.id, "Example Group")

    db.commit()

    def unexpected_database_call(**kwargs):
        pytest.fail(
            "Metric retrieval should not happen for an ambiguous company."
        )

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        unexpected_database_call,
    )

    with pytest.raises(ValueError, match="could not be resolved safely"):
        query_service.get_available_reporting_periods(
            company="Example Group",
            metric="Revenue",
        )




def test_resolve_q3_fiscal_period_standalone(
    db,
    apple_company,
    monkeypatch,
):
    def fake_get_financial_metrics(**kwargs):
        assert kwargs["company_id"] == apple_company.id

        record = make_metric_record(
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="standalone",
        )

        record["start_date"] = date(2026, 3, 29)
        record["end_date"] = date(2026, 6, 27)
        record["period_label"] = "Q3 FY2026"

        return [record]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    result = query_service.resolve_fiscal_quarter_period(
        company="Apple",
        metric="Revenue",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="standalone",
    )

    assert result is not None
    assert result["fiscal_year"] == 2026
    assert result["fiscal_period"] == "Q3"
    assert result["period_scope"] == "standalone"
    assert result["start_date"] == date(2026, 3, 29)
    assert result["end_date"] == date(2026, 6, 27)


def test_resolve_q3_fiscal_period_ytd(
    db,
    apple_company,
    monkeypatch,
):
    def fake_get_financial_metrics(**kwargs):
        record = make_metric_record(
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="ytd",
        )

        record["start_date"] = date(2025, 9, 28)
        record["end_date"] = date(2026, 6, 27)
        record["period_label"] = "Q3 FY2026 YTD"

        return [record]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    result = query_service.resolve_fiscal_quarter_period(
        company="AAPL",
        metric="Revenue",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope="ytd",
    )

    assert result is not None
    assert result["fiscal_year"] == 2026
    assert result["fiscal_period"] == "Q3"
    assert result["period_scope"] == "ytd"
    assert result["start_date"] == date(2025, 9, 28)
    assert result["end_date"] == date(2026, 6, 27)


def test_resolve_missing_fiscal_quarter_returns_none(
    db,
    apple_company,
    monkeypatch,
):
    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        lambda **kwargs: [],
    )

    result = query_service.resolve_fiscal_quarter_period(
        company="Apple",
        metric="Revenue",
        fiscal_year=2026,
        fiscal_period="Q4",
        period_scope="standalone",
    )

    assert result is None






@pytest.mark.parametrize(
    ("period_scope", "expected_value"),
    [
        ("standalone", Decimal("109417000000")),
        ("ytd", Decimal("364357000000")),
    ],
)
def test_resolve_q3_fiscal_revenue_without_mixing_period_scopes(
    db,
    apple_company,
    monkeypatch,
    period_scope,
    expected_value,
):
    def fake_get_financial_metrics(**kwargs):
        assert kwargs["company_id"] == apple_company.id

        standalone = make_metric_record(
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="standalone",
        )
        standalone["value"] = Decimal("109417000000")
        standalone["start_date"] = date(2026, 3, 29)
        standalone["end_date"] = date(2026, 6, 27)
        standalone["period_label"] = "Q3 FY2026"

        ytd = make_metric_record(
            fiscal_year=2026,
            fiscal_period="Q3",
            period_scope="ytd",
        )
        ytd["value"] = Decimal("364357000000")
        ytd["start_date"] = date(2025, 9, 28)
        ytd["end_date"] = date(2026, 6, 27)
        ytd["period_label"] = "Q3 FY2026 YTD"

        return [standalone, ytd]

    monkeypatch.setattr(
        query_service,
        "get_financial_metrics",
        fake_get_financial_metrics,
    )

    request = FactSelectionRequest(
        metric="Revenue",
        company="AAPL",
        fiscal_year=2026,
        fiscal_period="Q3",
        period_scope=period_scope,
        currency="USD",
        unit="USD",
    )

    result = query_service.resolve_metric_from_database(request)

    assert result.status == "resolved"
    assert result.selected is not None
    assert result.selected.value == expected_value
    assert result.selected.period.fiscal_year == 2026
    assert result.selected.period.fiscal_period == "Q3"
    assert result.selected.period.period_scope == period_scope
