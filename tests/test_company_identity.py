
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.company_identity import (
    add_company_alias,
    create_or_get_company,
    normalize_cik,
    normalize_company_name,
    resolve_company,
)


@pytest.fixture
def db():
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

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_normalize_company_name():
    assert normalize_company_name("Apple Inc.") == "apple"
    assert normalize_company_name("APPLE") == "apple"
    assert normalize_company_name("Microsoft Corporation") == "microsoft"


def test_normalize_cik():
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("0000320193") == "0000320193"


def test_normalize_cik_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_cik("ABC")


def test_create_company_with_cik(db):
    company = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    db.commit()

    assert company.id is not None
    assert company.canonical_name == "Apple Inc."
    assert company.cik == "0000320193"
    assert company.normalized_name == "apple"


def test_create_or_get_company_is_idempotent_by_cik(db):
    first = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    second = create_or_get_company(
        db,
        canonical_name="Apple Incorporated",
        cik="0000320193",
    )

    assert first.id == second.id


def test_create_or_get_company_without_cik(db):
    first = create_or_get_company(
        db,
        canonical_name="Example Technologies",
    )

    second = create_or_get_company(
        db,
        canonical_name="EXAMPLE TECHNOLOGIES",
    )

    assert first.id == second.id


def test_add_company_alias(db):
    company = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    alias = add_company_alias(
        db,
        company_id=company.id,
        alias="Apple",
    )

    assert alias.company_id == company.id
    assert alias.normalized_alias == "apple"


def test_add_same_alias_is_idempotent(db):
    company = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    first = add_company_alias(db, company.id, "Apple")
    second = add_company_alias(db, company.id, "APPLE")

    assert first.id == second.id


def test_resolve_company_by_cik(db):
    company = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    result = resolve_company(
        db,
        name="Apple Inc.",
        cik="0000320193",
    )

    assert result["status"] == "resolved"
    assert result["company"].id == company.id
    assert result["match_type"] == "cik"


def test_resolve_company_by_canonical_name(db):
    company = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    result = resolve_company(db, name="Apple")

    assert result["status"] == "resolved"
    assert result["company"].id == company.id


def test_resolve_company_by_alias(db):
    company = create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    add_company_alias(db, company.id, "AAPL")

    result = resolve_company(db, name="AAPL")

    assert result["status"] == "resolved"
    assert result["company"].id == company.id


def test_resolve_unknown_company(db):
    result = resolve_company(db, name="Unknown Company")

    assert result["status"] == "not_found"
    assert result["company"] is None


def test_unknown_cik_does_not_fall_back_to_name(db):
    create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    result = resolve_company(
        db,
        name="Apple Inc.",
        cik="9999999999",
    )

    assert result["status"] == "not_found"


def test_cik_and_name_conflict_is_rejected(db):
    create_or_get_company(
        db,
        canonical_name="Apple Inc.",
        cik="320193",
    )

    result = resolve_company(
        db,
        name="Microsoft",
        cik="320193",
    )

    assert result["status"] == "identity_conflict"
    assert result["company"] is None


def test_ambiguous_alias_is_not_silently_resolved(db):
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

    result = resolve_company(db, name="Example Group")

    assert result["status"] == "ambiguous"
    assert result["company"] is None
    assert len(result["candidates"]) == 2
