
from app.crud import backfill_chunk_hashes, get_all_document_chunks
from app.hashing import calculate_content_hash
from app.database import SessionLocal
from app.models import DocumentChunk
from sqlalchemy import select


def main():
    updated_count = backfill_chunk_hashes()
    print(f"Chunks updated with hashes: {updated_count}")

    with SessionLocal() as session:
        chunks = session.execute(
            select(DocumentChunk)
        ).scalars().all()

        for chunk in chunks:
            expected_hash = calculate_content_hash(chunk.text)

            assert chunk.content_hash == expected_hash
            print(f"Chunk {chunk.id}: hash verified")

    print("Hash backfill test passed!")


if __name__ == "__main__":
    main()
