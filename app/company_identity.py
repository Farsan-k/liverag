
import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Company,
    CompanyAlias,
    FinancialDocument,
    FinancialMetricRecord,
)


LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "company",
    "co",
    "limited",
    "ltd",
    "llc",
    "plc",
}


def normalize_company_name(name: str) -> str:
    """
    Normalize a company name for exact identity matching.

    Examples:
        Apple Inc.       -> apple
        APPLE            -> apple
        Microsoft Corp.  -> microsoft
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Company name must be a non-empty string.")

    normalized = name.casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    parts = normalized.split()

    while parts and parts[-1] in LEGAL_SUFFIXES:
        parts.pop()

    if not parts:
        raise ValueError("Company name is invalid after normalization.")

    return " ".join(parts)


def normalize_cik(cik: str | None) -> str | None:
    """Normalize an SEC CIK to its ten-digit representation."""
    if cik is None:
        return None

    digits = re.sub(r"\D", "", str(cik))

    if not digits:
        raise ValueError("CIK must contain digits.")

    if len(digits) > 10:
        raise ValueError("CIK cannot contain more than 10 digits.")

    return digits.zfill(10)


def create_or_get_company(
    db: Session,
    canonical_name: str,
    cik: str | None = None,
) -> Company:
    """
    Return an existing company or create a new one.

    CIK is authoritative when supplied. A name-only lookup uses
    the exact normalized canonical name.
    """
    if not isinstance(canonical_name, str) or not canonical_name.strip():
        raise ValueError("Canonical company name is required.")

    normalized_name = normalize_company_name(canonical_name)
    normalized_cik = normalize_cik(cik)

    if normalized_cik:
        company = db.execute(
            select(Company).where(Company.cik == normalized_cik)
        ).scalar_one_or_none()

        if company is not None:
            return company

    else:
        company = db.execute(
            select(Company).where(
                Company.normalized_name == normalized_name
            )
        ).scalar_one_or_none()

        if company is not None:
            return company

    company = Company(
        cik=normalized_cik,
        canonical_name=canonical_name.strip(),
        normalized_name=normalized_name,
    )

    db.add(company)
    db.flush()

    return company


def add_company_alias(
    db: Session,
    company_id: int,
    alias: str,
) -> CompanyAlias:
    """Register an alternate company name."""
    if not isinstance(alias, str) or not alias.strip():
        raise ValueError("Alias must be a non-empty string.")

    company = db.get(Company, company_id)

    if company is None:
        raise ValueError(f"Company {company_id} does not exist.")

    normalized_alias = normalize_company_name(alias)

    existing = db.execute(
        select(CompanyAlias).where(
            CompanyAlias.company_id == company_id,
            CompanyAlias.normalized_alias == normalized_alias,
        )
    ).scalar_one_or_none()

    if existing is not None:
        return existing

    company_alias = CompanyAlias(
        company_id=company_id,
        alias=alias.strip(),
        normalized_alias=normalized_alias,
    )

    db.add(company_alias)
    db.flush()

    return company_alias


def resolve_company(
    db: Session,
    name: str | None = None,
    cik: str | None = None,
) -> dict[str, Any]:
    """
    Resolve a company using an exact CIK, canonical name, or alias.

    If a CIK is supplied, it is authoritative. The resolver will
    not fall back to a name match when that CIK is unknown.

    Returns:
        {
            "status": "resolved" | "ambiguous" | "not_found"
                       | "identity_conflict",
            "company": Company | None,
            "candidates": list[Company],
            "match_type": str | None,
        }
    """
    normalized_cik = normalize_cik(cik)

    if normalized_cik:
        company = db.execute(
            select(Company).where(Company.cik == normalized_cik)
        ).scalar_one_or_none()

        if company is None:
            return {
                "status": "not_found",
                "company": None,
                "candidates": [],
                "match_type": None,
            }

        if name:
            normalized_name = normalize_company_name(name)

            name_matches_company = (
                normalized_name == company.normalized_name
            )

            if not name_matches_company:
                alias_match = db.execute(
                    select(CompanyAlias.id).where(
                        CompanyAlias.company_id == company.id,
                        CompanyAlias.normalized_alias == normalized_name,
                    )
                ).first()

                name_matches_company = alias_match is not None

            if not name_matches_company:
                return {
                    "status": "identity_conflict",
                    "company": None,
                    "candidates": [company],
                    "match_type": "cik_name_conflict",
                }

        return {
            "status": "resolved",
            "company": company,
            "candidates": [company],
            "match_type": "cik",
        }

    if not name:
        raise ValueError("Provide either a company name or a CIK.")

    normalized_name = normalize_company_name(name)

    statement = (
        select(Company)
        .outerjoin(
            CompanyAlias,
            CompanyAlias.company_id == Company.id,
        )
        .where(
            or_(
                Company.normalized_name == normalized_name,
                CompanyAlias.normalized_alias == normalized_name,
            )
        )
        .distinct()
        .order_by(Company.id)
    )

    candidates = list(db.execute(statement).scalars().all())

    if not candidates:
        return {
            "status": "not_found",
            "company": None,
            "candidates": [],
            "match_type": None,
        }

    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "company": None,
            "candidates": candidates,
            "match_type": "name_or_alias",
        }

    company = candidates[0]

    return {
        "status": "resolved",
        "company": company,
        "candidates": [company],
        "match_type": "name_or_alias",
    }


def link_financial_document_to_company(
    db: Session,
    financial_document_id: int,
) -> Company:
    """
    Link a financial document and its metrics to a verified company.

    The document must contain an expected CIK. Its company name
    must match the canonical company name or a registered alias.
    Existing company text fields are preserved.
    """
    document = db.get(FinancialDocument, financial_document_id)

    if document is None:
        raise ValueError(
            f"Financial document {financial_document_id} does not exist."
        )

    if not document.expected_cik:
        raise ValueError(
            "Cannot link financial document without an expected CIK."
        )

    result = resolve_company(
        db,
        name=document.company,
        cik=document.expected_cik,
    )

    if result["status"] != "resolved":
        raise ValueError(
            f"Company identity could not be verified: {result['status']}"
        )

    company = result["company"]

    document.company_id = company.id

    db.query(FinancialMetricRecord).filter(
        FinancialMetricRecord.source_document_id == document.id
    ).update(
        {"company_id": company.id},
        synchronize_session="fetch",
    )

    db.flush()

    return company
