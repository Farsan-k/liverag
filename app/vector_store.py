
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from app.embeddings import generate_embedding
from qdrant_client.models import PointStruct
from app.crud import get_all_document_chunks
from app.hashing import calculate_content_hash


COLLECTION_NAME = "financial_documents"


def create_collection():
    client = QdrantClient(path="./qdrant_data")

    try:
        if not client.collection_exists(COLLECTION_NAME):
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE,
                ),
            )
            print("Collection created successfully")
        else:
            print("Collection already exists")

        print("Qdrant is ready for financial document embeddings")

    finally:
        client.close()


def store_embedding(
    text: str,
    chunk_id: int,
    document_id: int,
    chunk_index: int,
    content_hash: str | None = None,
    client: QdrantClient | None = None,
):
    owns_client = client is None

    if owns_client:
        client = QdrantClient(path="./qdrant_data")

    try:
        vector = generate_embedding(text)
        current_hash = content_hash or calculate_content_hash(text)

        point = PointStruct(
            id=chunk_id,
            vector=vector,
            payload={
                "chunk_id": chunk_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": text,
                "content_hash": current_hash,
            },
        )

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point],
        )

        print(f"Stored embedding for chunk ID: {chunk_id}")

    finally:
        if owns_client:
            client.close()



def sync_postgres_chunks_to_qdrant():
    chunks = get_all_document_chunks()

    print(f"Found {len(chunks)} PostgreSQL chunks")

    client = QdrantClient(path="./qdrant_data")

    try:
        # Get all existing Qdrant point IDs.
        qdrant_point_ids = set()
        offset = None

        while True:
            points, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )

            qdrant_point_ids.update(point.id for point in points)

            if next_offset is None:
                break

            offset = next_offset

        # Identify points that no longer exist in PostgreSQL.
        postgres_chunk_ids = {chunk["id"] for chunk in chunks}
        obsolete_ids = qdrant_point_ids - postgres_chunk_ids

        if obsolete_ids:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=list(obsolete_ids),
                wait=True,
            )
            print(f"Removed obsolete Qdrant vectors: {len(obsolete_ids)}")
        else:
            print("No obsolete Qdrant vectors found")

        # Retrieve existing points for current PostgreSQL chunks.
        existing_points = []

        for start in range(0, len(chunks), 100):
            batch = chunks[start:start + 100]

            if not batch:
                continue

            existing_points.extend(
                client.retrieve(
                    collection_name=COLLECTION_NAME,
                    ids=[chunk["id"] for chunk in batch],
                    with_payload=True,
                    with_vectors=False,
                )
            )

        existing_hashes = {
            point.id: (point.payload or {}).get("content_hash")
            for point in existing_points
        }

        new_count = 0
        skipped_count = 0

        for chunk in chunks:
            chunk_id = chunk["id"]
            postgres_hash = chunk["content_hash"]
            qdrant_hash = existing_hashes.get(chunk_id)

            if postgres_hash == qdrant_hash and qdrant_hash is not None:
                print(f"Skipped unchanged chunk: {chunk_id}")
                skipped_count += 1
                continue

            store_embedding(
                text=chunk["text"],
                chunk_id=chunk_id,
                document_id=chunk["document_id"],
                chunk_index=chunk["chunk_index"],
                content_hash=postgres_hash,
                client=client,
            )

            new_count += 1

        print(f"Embeddings created or updated: {new_count}")
        print(f"Unchanged chunks skipped: {skipped_count}")
        print("PostgreSQL to Qdrant synchronization completed")

    finally:
        client.close()





def search_embeddings(
    query: str,
    limit: int = 3,
    score_threshold: float | None = None,
):
    if limit < 1:
        raise ValueError("limit must be at least 1")

    client = QdrantClient(path="./qdrant_data")

    try:
        query_vector = generate_embedding(query)

        # Retrieve extra candidates before applying filters.
        candidate_limit = max(limit * 5, 20)

        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=candidate_limit,
            with_payload=True,
        ).points

        # Remove results below the requested similarity threshold.
        if score_threshold is not None:
            results = [
                result
                for result in results
                if result.score >= score_threshold
            ]

        # Keep the strongest matching chunk from each document first.
        results.sort(key=lambda result: result.score, reverse=True)

        selected_results = []
        seen_document_ids = set()

        for result in results:
            payload = result.payload or {}
            document_id = payload.get("document_id")

            if document_id in seen_document_ids:
                continue

            selected_results.append(result)
            seen_document_ids.add(document_id)

            if len(selected_results) >= limit:
                break

        for result in selected_results:
            payload = result.payload or {}
            print(f"Score: {result.score:.4f}")
            print(f"Text: {payload.get('text', '')}")
            print(f"Document ID: {payload.get('document_id')}")
            print("-" * 40)

        return selected_results

    finally:
        client.close()




if __name__ == "__main__":
    create_collection()
    sync_postgres_chunks_to_qdrant()

    search_embeddings(
        query="How did Apple's revenue and earnings perform?"
    )
