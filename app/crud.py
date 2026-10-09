from app.models import Document, DocumentChunk
from app.database import SessionLocal
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.chunking import create_text_chunks


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

    with SessionLocal() as session:

        query = select(Document).where(Document.id == document_id)

        result = session.execute(query)

        document = result.scalar_one_or_none()

        if not document:
            return None

        if title is not None:
            document.title = title

        if source is not None:
            document.source = source

        if content is not None:
            document.content = content


        session.commit()
        session.refresh(document)

    return document


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

    with SessionLocal() as session:
        statement = insert(DocumentChunk).values(chunks)

        statement = statement.on_conflict_do_nothing(
            constraint="uq_document_chunk_index"
        ).returning(DocumentChunk.id)

        inserted_ids = session.execute(statement).scalars().all()
        session.commit()

    return len(inserted_ids)



def insert_chunks_in_session(session, chunks):
    if not chunks:
        return 0

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
