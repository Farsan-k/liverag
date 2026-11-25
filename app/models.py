
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
    DateTime,
    Date,
    Numeric,
    Float,
    JSON,
    Index,
    func,
)

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    __table_args__ = (
        UniqueConstraint(
            "content_hash",
            name="uq_documents_content_hash",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    source = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunk_index",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=True)


class FinancialDocument(Base):
    __tablename__ = "financial_documents"

    __table_args__ = (
        UniqueConstraint(
            "file_hash",
            name="uq_financial_documents_file_hash",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Link to the existing text document after extraction
    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=True,
        index=True,
    )

    # Original file information
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    file_type = Column(String(30), nullable=False)
    file_hash = Column(String(64), nullable=False)

    # Financial identification
    company = Column(String(255), nullable=True)
    expected_cik = Column(String(10), nullable=True)

    # Canonical company identity
    company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=True,
        index=True,
    )

    # Extraction tracking
    extraction_status = Column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class FinancialMetricRecord(Base):
    """
    Stores normalized financial metrics extracted from financial documents.

    source_document_id references FinancialDocument.id.
    Multiple records can represent the same metric across
    different sources, periods and dimensions.
    """

    __tablename__ = "financial_metrics"

    __table_args__ = (
        Index(
            "ix_financial_metrics_company_metric",
            "company",
            "metric",
        ),
        Index(
            "ix_financial_metrics_period_end",
            "end_date",
        ),
        Index(
            "ix_financial_metrics_source_document",
            "source_document_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    source_document_id = Column(
        Integer,
        ForeignKey("financial_documents.id"),
        nullable=False,
    )

    # Canonical company identity
    company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=True,
        index=True,
    )

    company = Column(String(255), nullable=True)
    metric = Column(String(255), nullable=False)

    value = Column(Numeric(38, 12), nullable=False)
    unit = Column(String(100), nullable=False)
    currency = Column(String(10), nullable=True)

    # Reporting period
    period_type = Column(String(20), nullable=False)
    period_label = Column(String(100), nullable=True)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    instant_date = Column(Date, nullable=True)

    # Fiscal reporting identity
    fiscal_year = Column(Integer, nullable=True)
    fiscal_period = Column(String(10), nullable=True)

    # standalone, ytd, annual, or unknown
    period_scope = Column(
        String(20),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )

    # Source information
    source_type = Column(String(30), nullable=False)

    provenance = Column(JSON, nullable=False)
    evidence = Column(JSON, nullable=False)
    dimensions = Column(JSON, nullable=False, default=dict)

    confidence = Column(Float, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Company(Base):
    __tablename__ = "companies"

    __table_args__ = (
        UniqueConstraint(
            "cik",
            name="uq_companies_cik",
        ),
        UniqueConstraint(
            "normalized_name",
            name="uq_companies_normalized_name",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    cik = Column(String(10), nullable=True)

    canonical_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CompanyAlias(Base):
    __tablename__ = "company_aliases"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "normalized_alias",
            name="uq_company_alias_company_normalized",
        ),
        Index(
            "ix_company_aliases_normalized_alias",
            "normalized_alias",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    alias = Column(String(255), nullable=False)
    normalized_alias = Column(String(255), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
