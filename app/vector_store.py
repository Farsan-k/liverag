
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.embeddings import generate_embedding
from qdrant_client.models import PointStruct
from app.crud import get_all_document_chunks, search_keyword_chunks, get_chunk_metadata
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


def search_embeddings(
    query: str,
    limit: int = 3,
    score_threshold: float | None = None,
    deduplicate_documents: bool = True,
):
    """Search Qdrant using semantic similarity."""

    # 1. Validate inputs
    if not query or not query.strip():
        return []

    if limit < 1:
        raise ValueError("limit must be at least 1")

    if (
        score_threshold is not None
        and not -1 <= score_threshold <= 1
    ):
        raise ValueError(
            "score_threshold must be between -1 and 1"
        )

    # 2. Initialize Qdrant client
    client = QdrantClient(path="./qdrant_data")

    try:
        # 3. Generate query embedding
        query_vector = generate_embedding(query)

        # 4. Retrieve additional candidates
        candidate_limit = max(limit * 5, 20)

        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=candidate_limit,
            with_payload=True,
        ).points

        # 5. Apply similarity threshold
        if score_threshold is not None:
            results = [
                result
                for result in results
                if result.score >= score_threshold
            ]

        # 6. Sort by descending similarity score
        results.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        # 7. Deduplicate only when document IDs exist
        if deduplicate_documents:
            selected_results = []
            seen_document_ids = set()

            for result in results:
                payload = result.payload or {}
                document_id = payload.get("document_id")

                # Missing document IDs cannot be safely
                # deduplicated, so retain those results.
                if document_id is not None:
                    if document_id in seen_document_ids:
                        continue

                    seen_document_ids.add(document_id)

                selected_results.append(result)

                if len(selected_results) >= limit:
                    break

        else:
            selected_results = results[:limit]

        # 8. Display retrieval information
        print(f"\nQuery: {query}")
        print(f"Retrieved chunks: {len(selected_results)}")

        for result in selected_results:
            payload = result.payload or {}

            print("-" * 70)
            print(f"Score: {result.score:.4f}")
            print(f"Chunk ID: {payload.get('chunk_id')}")
            print(f"Document ID: {payload.get('document_id')}")
            print(f"Chunk Index: {payload.get('chunk_index')}")
            print(f"Text: {payload.get('text')}")

        return selected_results

    finally:
        client.close()


def store_embedding(
    text: str,
    chunk_id: int,
    document_id: int,
    chunk_index: int,
    content_hash: str | None = None,
    client=None,
):
    # Create a client only when one is not supplied
    owns_client = client is None

    if owns_client:
        client = QdrantClient(path="./qdrant_data")

    try:
        # Generate embedding
        vector = generate_embedding(text)

        # Calculate content hash if not provided
        if content_hash is None:
            content_hash = calculate_content_hash(text)

        # Prepare Qdrant point
        point = PointStruct(
            id=chunk_id,
            vector=vector,
            payload={
                "chunk_id": chunk_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": text,
                "content_hash": content_hash,
            },
        )

        # Insert or update the vector
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point],
            wait=True,
        )

        print(f"Stored embedding for chunk: {chunk_id}")

        return point

    finally:
        if owns_client:
            client.close()





def delete_document_embeddings(document_id: int):
    client = QdrantClient(path="./qdrant_data")

    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
            wait=True,
        )

        print(
            f"Deleted Qdrant embeddings for document: {document_id}"
        )

    finally:
        client.close()





def sync_postgres_chunks_to_qdrant():
    chunks = get_all_document_chunks()

    print(f"Found {len(chunks)} PostgreSQL chunks")

    client = QdrantClient(path="./qdrant_data")

    try:
        # 1. Read existing Qdrant points
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

        postgres_chunk_ids = {chunk["id"] for chunk in chunks}

        # 2. Protect against accidental deletion
        if not chunks and qdrant_point_ids:
            raise RuntimeError(
                "PostgreSQL returned zero chunks, but Qdrant "
                "contains data. Synchronization stopped to "
                "prevent accidental deletion."
            )

        # 3. Remove obsolete Qdrant points
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

        # 4. Retrieve existing Qdrant payloads
        existing_points = []

        for start in range(0, len(chunks), 100):
            batch = chunks[start:start + 100]

            existing_points.extend(
                client.retrieve(
                    collection_name=COLLECTION_NAME,
                    ids=[chunk["id"] for chunk in batch],
                    with_payload=True,
                    with_vectors=False,
                )
            )

        existing_payloads = {
            point.id: (point.payload or {})
            for point in existing_points
        }

        # 5. Compare content and metadata
        new_count = 0
        skipped_count = 0

        for chunk in chunks:
            chunk_id = chunk["id"]
            payload = existing_payloads.get(chunk_id)

            expected_payload = {
                "chunk_id": chunk["id"],
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "content_hash": chunk["content_hash"],
            }

            if payload == expected_payload:
                skipped_count += 1
                continue

            store_embedding(
                text=chunk["text"],
                chunk_id=chunk["id"],
                document_id=chunk["document_id"],
                chunk_index=chunk["chunk_index"],
                content_hash=chunk["content_hash"],
                client=client,
            )

            new_count += 1

        print(f"Embeddings created or updated: {new_count}")
        print(f"Unchanged chunks skipped: {skipped_count}")
        print("PostgreSQL to Qdrant synchronization completed")

    finally:
        client.close()


if __name__ == "__main__":
    create_collection()
    sync_postgres_chunks_to_qdrant()

    search_embeddings(
        query="How did Apple's revenue and earnings perform?"
    )


def hybrid_search(
    query: str,
    limit: int = 5,
    rrf_k: int = 60,
):
    """
    Combine Qdrant semantic search and PostgreSQL keyword search
    using Reciprocal Rank Fusion (RRF).
    """

    # 1. Validate inputs.
    if not query or not query.strip():
        return []

    if limit < 1:
        raise ValueError("limit must be at least 1")

    if rrf_k < 1:
        raise ValueError("rrf_k must be at least 1")

    candidate_limit = max(limit * 5, 20)

    # 2. Retrieve semantic candidates from Qdrant.
    semantic_results = search_embeddings(
        query=query,
        limit=candidate_limit,
        deduplicate_documents=False,
    )

    # 3. Retrieve keyword candidates from PostgreSQL.
    keyword_results = search_keyword_chunks(
        query=query,
        limit=candidate_limit,
    )

    # 4. Merge candidates using chunk IDs.
    fused_results = {}

    for rank, result in enumerate(semantic_results, start=1):
        payload = result.payload or {}
        chunk_id = payload.get("chunk_id", result.id)

        item = fused_results.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "document_id": payload.get("document_id"),
                "chunk_index": payload.get("chunk_index"),
                "text": payload.get("text"),
                "semantic_rank": None,
                "keyword_rank": None,
                "semantic_score": None,
                "keyword_score": None,
                "rrf_score": 0.0,
            },
        )

        item["semantic_rank"] = rank
        item["semantic_score"] = result.score
        item["rrf_score"] += 1 / (rrf_k + rank)

    for rank, result in enumerate(keyword_results, start=1):
        chunk_id = result["chunk_id"]

        item = fused_results.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "document_id": result["document_id"],
                "chunk_index": result["chunk_index"],
                "text": result["text"],
                "semantic_rank": None,
                "keyword_rank": None,
                "semantic_score": None,
                "keyword_score": None,
                "rrf_score": 0.0,
            },
        )

        item["keyword_rank"] = rank
        item["keyword_score"] = result["rank"]
        item["rrf_score"] += 1 / (rrf_k + rank)

    # 5. Retrieve document metadata.
    metadata = get_chunk_metadata(list(fused_results.keys()))

    for chunk_id, item in fused_results.items():
        item.update(metadata.get(chunk_id, {}))

    # 6. Sort by RRF score.
    # Use chunk_id as a deterministic tie-breaker.
    ranked_results = sorted(
        fused_results.values(),
        key=lambda item: (
            -item["rrf_score"],
            item["chunk_id"],
        ),
    )

    # 7. Return the top results.
    return ranked_results[:limit]
