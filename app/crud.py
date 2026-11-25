from app.models import Document, DocumentChunk, FinancialDocument, FinancialMetricRecord
from app.database import SessionLocal
from sqlalchemy import select, func, delete
from sqlalchemy.dialects.postgresql import insert
from app.chunking import create_text_chunks
from app.hashing import calculate_content_hash
import re
from app.company_identity import resolve_company

def create_document(title, source, content):

    with SessionLocal() as session:

        document = Document(
            title=title,
            source=source,
            content=content,
            content_hash=calculate_content_hash(content),
        )

        session.add(document)
        session.commit()
        session.refresh(document)

    return document

def get_document(document_id):

    with SessionLocal() as session:

        query = select(Document).where(Document.id == document_id)

        result = session.execute(query)

        document = result.scalar_one_or_none()

    return document

def get_all_documents():
    with SessionLocal() as session:
        documents = session.execute(
            select(Document).order_by(Document.id)
        ).scalars().all()

        return [
            {
                "id": document.id,
                "title": document.title,
                "source": document.source,
                "content": document.content,
            }
            for document in documents
        ]

def update_document(document_id, title, source, content):
    with SessionLocal.begin() as session:
        query = select(Document).where(Document.id == document_id)
        document = session.execute(query).scalar_one_or_none()

        if not document:
            return None

        if title is not None:
            document.title = title

        if source is not None:
            document.source = source

        if content is not None:
            document.content = content
            document.content_hash = calculate_content_hash(content)

            new_chunks = create_text_chunks(
                document.content,
                document_id=document.id,
            )

            for chunk in new_chunks:
                chunk["content_hash"] = calculate_content_hash(
                    chunk["text"]
                )

            if new_chunks:
                statement = insert(DocumentChunk).values(new_chunks)

                statement = statement.on_conflict_do_update(
                    constraint="uq_document_chunk_index",
                    set_={
                        "text": statement.excluded.text,
                        "content_hash": statement.excluded.content_hash,
                    },
                    where=(
                        DocumentChunk.content_hash
                        != statement.excluded.content_hash
                    ),
                )

                session.execute(statement)

            new_chunk_count = len(new_chunks)

            session.query(DocumentChunk).filter(
                DocumentChunk.document_id == document.id,
                DocumentChunk.chunk_index >= new_chunk_count,
            ).delete(synchronize_session=False)

        session.flush()
        session.refresh(document)

        updated_document = {
            "id": document.id,
            "title": document.title,
            "source": document.source,
            "content": document.content,
        }

    return updated_document

def delete_document(document_id):
    with SessionLocal.begin() as session:
        query = select(Document).where(Document.id == document_id)
        document = session.execute(query).scalar_one_or_none()

        if not document:
            return False

        session.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete(synchronize_session=False)

        session.delete(document)

    return True

def save_document_chunks(chunks):
    if not chunks:
        return 0

    for chunk in chunks:
        chunk["content_hash"] = calculate_content_hash(chunk["text"])

    with SessionLocal() as session:
        statement = insert(DocumentChunk).values(chunks)

        statement = statement.on_conflict_do_update(
            constraint="uq_document_chunk_index",
            set_={
                "text": statement.excluded.text,
                "content_hash": statement.excluded.content_hash,
            },
            where=(
                DocumentChunk.content_hash
                != statement.excluded.content_hash
            ),
        ).returning(DocumentChunk.id)

        updated_or_inserted_ids = (
            session.execute(statement).scalars().all()
        )

        session.commit()

    return len(updated_or_inserted_ids)

def insert_chunks_in_session(session, chunks):
    if not chunks:
        return 0

    for chunk in chunks:
        chunk["content_hash"] = calculate_content_hash(chunk["text"])

    statement = insert(DocumentChunk).values(chunks)

    statement = statement.on_conflict_do_nothing(
        constraint="uq_document_chunk_index"
    ).returning(DocumentChunk.id)

    inserted_ids = session.execute(statement).scalars().all()

    return len(inserted_ids)


def create_document_with_chunks(title, source, content):
    content_hash = calculate_content_hash(content)

    with SessionLocal.begin() as session:
        # Insert only if this content hash does not already exist.
        statement = (
            insert(Document)
            .values(
                title=title,
                source=source,
                content=content,
                content_hash=content_hash,
            )
            .on_conflict_do_nothing(
                constraint="uq_documents_content_hash"
            )
            .returning(Document.id)
        )

        document_id = session.execute(statement).scalar_one_or_none()

        # Duplicate document: return the existing record.
        if document_id is None:
            document = session.execute(
                select(Document).where(
                    Document.content_hash == content_hash
                )
            ).scalar_one()

            result = {
                "id": document.id,
                "title": document.title,
                "source": document.source,
                "content": document.content,
                "content_hash": document.content_hash,
                "chunks_created": 0,
                "chunks_saved": 0,
                "duplicate": True,
            }

        else:
            # New document: create its chunks in the same transaction.
            document = session.get(Document, document_id)

            chunks = create_text_chunks(
                document.content,
                document_id=document.id,
            )

            saved_count = insert_chunks_in_session(session, chunks)

            result = {
                "id": document.id,
                "title": document.title,
                "source": document.source,
                "content": document.content,
                "content_hash": document.content_hash,
                "chunks_created": len(chunks),
                "chunks_saved": saved_count,
                "duplicate": False,
            }

    return result


def get_all_document_chunks():
    with SessionLocal() as session:
        chunks = session.execute(
            select(DocumentChunk)
        ).scalars().all()

        return [
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "content_hash": chunk.content_hash,
            }
            for chunk in chunks
        ]

def backfill_chunk_hashes():
    updated_count = 0

    with SessionLocal.begin() as session:
        chunks = session.execute(
            select(DocumentChunk)
        ).scalars().all()

        for chunk in chunks:
            current_hash = calculate_content_hash(chunk.text)

            if chunk.content_hash != current_hash:
                chunk.content_hash = current_hash
                updated_count += 1

    return updated_count


def search_keyword_chunks(query: str, limit: int = 5):
    """
    Search document chunks using PostgreSQL full-text search.

    Strategy:
    1. Try strict AND-based search.
    2. If no results are found, use OR-based fallback.
    3. Rank results using PostgreSQL relevance ranking.
    """

    if not query or not query.strip():
        return []

    if limit < 1:
        raise ValueError("Limit must be greater than zero")

    search_vector = func.to_tsvector(
        "english",
        DocumentChunk.text
    )

    with SessionLocal() as session:

        # Stage 1: Strict AND-based search
        strict_query = func.plainto_tsquery(
            "english",
            query.strip()
        )

        strict_rank = func.ts_rank_cd(
            search_vector,
            strict_query
        ).label("rank")

        base_statement = (
            select(
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.text,
                Document.title.label("document_title"),
                Document.source.label("document_source"),
            )
            .join(
                Document,
                Document.id == DocumentChunk.document_id
            )
        )

        strict_statement = (
            base_statement
            .add_columns(strict_rank)
            .where(search_vector.op("@@")(strict_query))
            .order_by(
                strict_rank.desc(),
                DocumentChunk.id.asc()
            )
            .limit(limit)
        )

        strict_results = (
            session.execute(strict_statement)
            .mappings()
            .all()
        )

        if strict_results:
            return [dict(result) for result in strict_results]

        # Stage 2: OR-based fallback
        stop_words = {
            "what", "which", "who", "how", "is", "was",
            "were", "the", "a", "an", "and", "or", "to",
            "for", "of", "in", "on", "did", "does", "do",
            "drove", "contributed"
        }

        terms = re.findall(r"[a-zA-Z0-9]+", query.lower())

        terms = list(dict.fromkeys(
            term for term in terms
            if term not in stop_words
        ))

        if not terms:
            return []

        or_query_text = " | ".join(terms)

        fallback_query = func.to_tsquery(
            "english",
            or_query_text
        )

        fallback_rank = func.ts_rank_cd(
            search_vector,
            fallback_query
        ).label("rank")

        fallback_statement = (
            base_statement
            .add_columns(fallback_rank)
            .where(search_vector.op("@@")(fallback_query))
            .order_by(
                fallback_rank.desc(),
                DocumentChunk.id.asc()
            )
            .limit(limit)
        )

        fallback_results = (
            session.execute(fallback_statement)
            .mappings()
            .all()
        )

        return [dict(result) for result in fallback_results]


def get_chunk_metadata(chunk_ids: list[int]):
    """
    Retrieve document metadata for a collection of chunk IDs.
    Returns a dictionary keyed by chunk_id.
    """

    if not chunk_ids:
        return {}

    statement = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            Document.title.label("document_title"),
            Document.source.label("document_source"),
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id
        )
        .where(DocumentChunk.id.in_(chunk_ids))
    )

    with SessionLocal() as session:
        results = session.execute(statement).mappings().all()

        return {
            result["chunk_id"]: dict(result)
            for result in results
        }




def _financial_document_to_dict(document, duplicate=False):
    return {
        "id": document.id,
        "document_id": document.document_id,
        "original_filename": document.original_filename,
        "storage_path": document.storage_path,
        "file_type": document.file_type,
        "file_hash": document.file_hash,
        "company": document.company,
        "expected_cik": document.expected_cik,
        "extraction_status": document.extraction_status,
        "created_at": document.created_at,
        "duplicate": duplicate,
    }



def create_financial_document(
    original_filename,
    storage_path,
    file_type,
    file_hash,
    document_id=None,
    company=None,
    expected_cik=None,
):
    with SessionLocal.begin() as session:

        statement = (
            insert(FinancialDocument)
            .values(
                original_filename=original_filename,
                storage_path=storage_path,
                file_type=file_type,
                file_hash=file_hash,
                document_id=document_id,
                company=company,
                expected_cik=expected_cik,
                extraction_status="pending",
            )
            .on_conflict_do_nothing(
                constraint="uq_financial_documents_file_hash"
            )
            .returning(FinancialDocument.id)
        )

        financial_document_id = (
            session.execute(statement).scalar_one_or_none()
        )

        if financial_document_id is None:
            document = session.execute(
                select(FinancialDocument).where(
                    FinancialDocument.file_hash == file_hash
                )
            ).scalar_one()

            result = _financial_document_to_dict(
                document,
                duplicate=True,
            )

        else:
            document = session.get(
                FinancialDocument,
                financial_document_id,
            )

            # Resolve the company using its authoritative SEC CIK.
            if expected_cik:
                identity = resolve_company(
                    session,
                    name=company,
                    cik=expected_cik,
                )

                if identity["status"] == "resolved":
                    document.company_id = identity["company"].id

                elif identity["status"] == "identity_conflict":
                    raise ValueError(
                        "Company name does not match the registered CIK."
                    )

            session.flush()

            result = _financial_document_to_dict(
                document,
                duplicate=False,
            )

    return result


def get_financial_document(financial_document_id):
    with SessionLocal() as session:

        document = session.execute(
            select(FinancialDocument).where(
                FinancialDocument.id == financial_document_id
            )
        ).scalar_one_or_none()

        if document is None:
            return None

        return _financial_document_to_dict(document)


def get_financial_document_by_hash(file_hash):
    with SessionLocal() as session:

        document = session.execute(
            select(FinancialDocument).where(
                FinancialDocument.file_hash == file_hash
            )
        ).scalar_one_or_none()

        if document is None:
            return None

        return _financial_document_to_dict(document)





def update_financial_document_extraction_status(
    financial_document_id: int,
    status: str,
) -> dict | None:
    """
    Update the extraction status of a financial document.

    Supported statuses:
    pending, processing, completed, failed.
    """

    allowed_statuses = {
        "pending",
        "processing",
        "completed",
        "failed",
    }

    if status not in allowed_statuses:
        raise ValueError(
            f"Invalid extraction status: {status}"
        )

    with SessionLocal.begin() as session:
        document = session.get(
            FinancialDocument,
            financial_document_id,
        )

        if document is None:
            return None

        document.extraction_status = status

        session.flush()

        return _financial_document_to_dict(document)





from decimal import Decimal




def create_financial_metrics(
    source_document_id: int,
    metrics: list,
) -> list[dict]:
    """
    Replace previously extracted metrics for a source document.

    Deletion and insertion happen in one transaction.
    If insertion fails, previous records are preserved.

    Financial metrics inherit the verified company_id
    from their source financial document.
    """

    records = []

    with SessionLocal.begin() as session:
        source_document = session.get(
            FinancialDocument,
            source_document_id,
        )

        if source_document is None:
            raise ValueError(
                f"Financial document {source_document_id} not found."
            )

        # Remove previous extraction results atomically.
        session.execute(
            delete(FinancialMetricRecord).where(
                FinancialMetricRecord.source_document_id
                == source_document_id
            )
        )

        for metric in metrics:
            # Validate metric provenance.
            if metric.source.source_document_id is not None:
                if (
                    str(metric.source.source_document_id)
                    != str(source_document_id)
                ):
                    raise ValueError(
                        "Metric provenance does not match source document."
                    )

            period = metric.period

            record = FinancialMetricRecord(
                source_document_id=source_document_id,

                # Inherit verified company identity.
                company_id=source_document.company_id,

                # Preserve the existing company text.
                company=metric.company or source_document.company,

                metric=metric.metric,
                value=Decimal(str(metric.value)),
                unit=metric.unit,
                currency=metric.currency,

                # Reporting period
                period_type=period.period_type,
                period_label=period.label,
                start_date=period.start_date,
                end_date=period.end_date,
                instant_date=period.instant_date,

                # Fiscal reporting identity
                fiscal_year=period.fiscal_year,
                fiscal_period=period.fiscal_period,
                period_scope=period.period_scope,

                # Source information
                source_type=metric.source.source_type,
                provenance=metric.source.model_dump(mode="json"),
                evidence=metric.evidence.model_dump(mode="json"),
                dimensions=metric.dimensions,
                confidence=metric.confidence,
            )

            session.add(record)
            records.append(record)

        session.flush()

        return [
            _financial_metric_to_dict(record)
            for record in records
        ]





def _financial_metric_to_dict(record) -> dict:
    return {
        "id": record.id,
        "source_document_id": record.source_document_id,
        "company_id": record.company_id,
        "company": record.company,
        "metric": record.metric,
        "value": record.value,
        "unit": record.unit,
        "currency": record.currency,

        "period_type": record.period_type,
        "period_label": record.period_label,
        "start_date": record.start_date,
        "end_date": record.end_date,
        "instant_date": record.instant_date,

        # Fiscal reporting identity
        "fiscal_year": record.fiscal_year,
        "fiscal_period": record.fiscal_period,
        "period_scope": record.period_scope,

        "source_type": record.source_type,
        "provenance": record.provenance,
        "evidence": record.evidence,
        "dimensions": record.dimensions,
        "confidence": record.confidence,
        "created_at": record.created_at,
    }

def get_financial_metrics(
    company: str | None = None,
    metric: str | None = None,
    source_document_id: int | None = None,
    company_id: int | None = None,
) -> list[dict]:
    """
    Retrieve financial metrics using optional filters.

    company_id is the preferred filter when company identity
    has already been resolved.
    """

    if company_id is not None and company is not None:
        raise ValueError(
            "Provide company_id or company, not both."
        )

    statement = select(FinancialMetricRecord)

    if company_id is not None:
        statement = statement.where(
            FinancialMetricRecord.company_id == company_id
        )

    elif company is not None:
        statement = statement.where(
            FinancialMetricRecord.company.ilike(company)
        )

    if metric is not None:
        statement = statement.where(
            FinancialMetricRecord.metric.ilike(metric)
        )

    if source_document_id is not None:
        statement = statement.where(
            FinancialMetricRecord.source_document_id
            == source_document_id
        )

    statement = statement.order_by(
        FinancialMetricRecord.id
    )

    with SessionLocal() as session:
        records = session.execute(
            statement
        ).scalars().all()

        return [
            _financial_metric_to_dict(record)
            for record in records
        ]



def get_financial_metrics(
    company: str | None = None,
    metric: str | None = None,
    source_document_id: int | None = None,
    company_id: int | None = None,
) -> list[dict]:
    """
    Retrieve financial metrics using optional filters.

    company_id is the preferred filter when company identity
    has already been resolved.

    Args:
        company: Company name to filter by.
        metric: Financial metric name to filter by.
        source_document_id: Source financial document ID.
        company_id: Verified company ID.

    Returns:
        A list of financial metric records.
    """

    # Prevent conflicting company filters.
    if company_id is not None and company is not None:
        raise ValueError(
            "Provide company_id or company, not both."
        )

    statement = select(FinancialMetricRecord)

    # Filter using verified company identity.
    if company_id is not None:
        statement = statement.where(
            FinancialMetricRecord.company_id == company_id
        )

    # Backward-compatible company-name filtering.
    elif company is not None:
        statement = statement.where(
            FinancialMetricRecord.company.ilike(company)
        )

    # Filter by financial metric.
    if metric is not None:
        statement = statement.where(
            FinancialMetricRecord.metric.ilike(metric)
        )

    # Filter by source document.
    if source_document_id is not None:
        statement = statement.where(
            FinancialMetricRecord.source_document_id
            == source_document_id
        )

    statement = statement.order_by(
        FinancialMetricRecord.id
    )

    with SessionLocal() as session:
        records = session.execute(
            statement
        ).scalars().all()

        return [
            _financial_metric_to_dict(record)
            for record in records
        ]

