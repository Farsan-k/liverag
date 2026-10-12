
from app.crud import get_all_document_chunks

chunks = get_all_document_chunks()

target_ids = {55, 56, 57, 58, 59}

for document_id in sorted(target_ids):
    document_chunks = sorted(
        [
            chunk for chunk in chunks
            if chunk["document_id"] == document_id
        ],
        key=lambda chunk: chunk["chunk_index"],
    )

    print(f"\nDocument ID: {document_id}")

    for chunk in document_chunks:
        print(f"  Chunk index: {chunk['chunk_index']}")
        print(f"  Text: {chunk['text']}")
        print(f"  Hash: {chunk['content_hash']}")
