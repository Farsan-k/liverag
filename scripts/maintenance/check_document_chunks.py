
from app.crud import get_all_document_chunks

chunks = get_all_document_chunks()

print(f"\nTotal chunks: {len(chunks)}")

for chunk in chunks:
    print("\n" + "=" * 70)
    print("Chunk ID:", chunk["id"])
    print("Document ID:", chunk["document_id"])
    print("Chunk Index:", chunk["chunk_index"])
    print("Character Count:", len(chunk["text"]))
    print("Text:", chunk["text"])
    print("Content Hash:", chunk["content_hash"])
