
from qdrant_client import QdrantClient
from app.crud import get_all_document_chunks

COLLECTION_NAME = "financial_documents"


def audit_sync():
    postgres_chunks = get_all_document_chunks()

    client = QdrantClient(path="./qdrant_data")

    try:
        postgres_by_id = {
            chunk["id"]: chunk
            for chunk in postgres_chunks
        }

        qdrant_points = {}
        offset = None

        while True:
            points, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for point in points:
                qdrant_points[point.id] = point

            if next_offset is None:
                break

            offset = next_offset

        postgres_ids = set(postgres_by_id)
        qdrant_ids = set(qdrant_points)

        missing_ids = postgres_ids - qdrant_ids
        obsolete_ids = qdrant_ids - postgres_ids

        metadata_mismatches = []
        hash_mismatches = []

        for chunk_id in postgres_ids & qdrant_ids:
            pg = postgres_by_id[chunk_id]
            qdrant = qdrant_points[chunk_id]
            payload = qdrant.payload or {}

            expected_metadata = {
                "chunk_id": pg["id"],
                "document_id": pg["document_id"],
                "chunk_index": pg["chunk_index"],
            }

            for field, expected in expected_metadata.items():
                actual = payload.get(field)

                if actual != expected:
                    metadata_mismatches.append({
                        "chunk_id": chunk_id,
                        "field": field,
                        "postgres": expected,
                        "qdrant": actual,
                    })

            if payload.get("content_hash") != pg["content_hash"]:
                hash_mismatches.append(chunk_id)

            if payload.get("text") != pg["text"]:
                metadata_mismatches.append({
                    "chunk_id": chunk_id,
                    "field": "text",
                    "postgres": pg["text"][:100],
                    "qdrant": str(payload.get("text"))[:100],
                })

        print("\n========== QDRANT SYNC AUDIT ==========")
        print("PostgreSQL chunks:", len(postgres_ids))
        print("Qdrant points:", len(qdrant_ids))
        print("Missing in Qdrant:", missing_ids)
        print("Obsolete in Qdrant:", obsolete_ids)
        print("Metadata mismatches:", metadata_mismatches)
        print("Hash mismatches:", hash_mismatches)

        if (
            not missing_ids
            and not obsolete_ids
            and not metadata_mismatches
            and not hash_mismatches
        ):
            print("\nRESULT: SYNCHRONIZATION VERIFIED")
        else:
            print("\nRESULT: SYNCHRONIZATION ISSUES FOUND")

    finally:
        client.close()


if __name__ == "__main__":
    audit_sync()
