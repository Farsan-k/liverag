
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from app.embeddings import generate_embedding
from qdrant_client.models import PointStruct, SearchParams


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



def store_embedding(text: str, document_id: int, chunk_index: int):
    client = QdrantClient(path="./qdrant_data")

    try:
        vector = generate_embedding(text)

        point = PointStruct(
            id=document_id * 100000 + chunk_index,
            vector=vector,
            payload={
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": text,
            },
        )

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point],
        )

        print("Embedding stored successfully")

    finally:
        client.close()



def search_embeddings(query: str, limit: int = 3):
    client = QdrantClient(path="./qdrant_data")

    try:
        query_vector = generate_embedding(query)

        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,
        ).points

        for result in results:
            print(f"Score: {result.score:.4f}")
            print(f"Text: {result.payload.get('text', '')}")
            print(f"Document ID: {result.payload.get('document_id')}")
            print("-" * 40)

        return results

    finally:
        client.close()





if __name__ == "__main__":
    create_collection()

    store_embedding(
        text="The company reported strong revenue growth.",
        document_id=999,
        chunk_index=0,
    )

    search_embeddings(
        query="How did the company's revenue perform?"
    )
