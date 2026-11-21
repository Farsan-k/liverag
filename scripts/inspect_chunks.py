
from app.crud import get_all_document_chunks

chunks = get_all_document_chunks()

print(f"\nTotal chunks: {len(chunks)}\n")

for chunk in chunks:
    print(f"Chunk ID: {chunk['id']}")
    print(f"Document ID: {chunk['document_id']}")
    print(f"Chunk Index: {chunk['chunk_index']}")
    print(f"Text: {chunk['text'][:150]}")
    print("-" * 70)
