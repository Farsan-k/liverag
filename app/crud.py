from app.models import Document, DocumentChunk
from app.database import SessionLocal
from sqlalchemy import select
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

            # Generate chunks from the updated document content.
            new_chunks = create_text_chunks(
                document.content,
                document_id=document.id,
            )

            # Update existing chunks or insert new chunks.
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

            # Remove old chunks beyond the new content's length.
            new_chunk_count = len(new_chunks)

            session.query(DocumentChunk).filter(
                DocumentChunk.document_id == document.id,
                DocumentChunk.chunk_index >= new_chunk_count,
            ).delete(synchronize_session=False)

        session.flush()
        session.refresh(document)

        # Copy the values before the session closes.
        updated_document = {
            "id": document.id,
            "title": document.title,
            "source": document.source,
            "content": document.content,
        }

    return updated_document



def delete_document(document_id):

    with SessionLocal() as session:

        query = select(Document).where(Document.id == document_id)
        result = session.execute(query)
        document = result.scalar_one_or_none()

        if not document:
            return False

        session.delete(document)
        session.commit()

    return True




def save_document_chunks(chunks):
    if not chunks:
        return 0

    # Calculate a SHA-256 hash for each chunk.
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
