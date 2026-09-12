from app.models import Document
from app.database import SessionLocal
from sqlalchemy import select


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
        

    