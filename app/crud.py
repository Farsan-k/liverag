from app.models import Document, DocumentChunk
from app.database import SessionLocal
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from app.chunking import create_text_chunks
from app.hashing import calculate_content_hash

def create_document(title, source, content):

    with SessionLocal() as session:

        document = Document(
            title=title,
            source=source,
            content=content
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
    with SessionLocal.begin() as session:
        document = Document(
            title=title,
            source=source,
            content=content
        )

        session.add(document)
        session.flush()

        chunks = create_text_chunks(
            document.content,
            document_id=document.id
        )

        saved_count = insert_chunks_in_session(session, chunks)

        result = {
            "id": document.id,
            "title": document.title,
            "source": document.source,
            "content": document.content,
            "chunks_created": len(chunks),
            "chunks_saved": saved_count
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
    Results are ordered by PostgreSQL relevance rank.
    """

    if not query or not query.strip():
        return []

    if limit < 1:
        raise ValueError("Limit must be greater than zero")

    search_query = func.plainto_tsquery("english", query.strip())

    search_vector = func.to_tsvector(
        "english",
        DocumentChunk.text
    )

    rank = func.ts_rank_cd(
        search_vector,
        search_query
    ).label("rank")

    statement = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            Document.title.label("document_title"),
            Document.source.label("document_source"),
            rank,
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id
        )
        .where(search_vector.op("@@")(search_query))
        .order_by(rank.desc(), DocumentChunk.id.asc(),)
        .limit(limit)
    )

    with SessionLocal() as session:
        results = session.execute(statement).mappings().all()

        return [dict(result) for result in results]




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
