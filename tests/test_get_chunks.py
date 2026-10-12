
from app.crud import get_all_document_chunks


def main():
    chunks = get_all_document_chunks()

    print(f"Total chunks retrieved: {len(chunks)}")

    for chunk in chunks[:5]:
        print("-" * 40)
        print(f"Chunk ID: {chunk['id']}")
        print(f"Document ID: {chunk['document_id']}")
        print(f"Chunk Index: {chunk['chunk_index']}")
        print(f"Text: {chunk['text'][:150]}")
        print(f"Content Hash: {chunk['content_hash']}")


if __name__ == "__main__":
    main()
