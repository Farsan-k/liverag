
from app.vector_store import search_embeddings
from app.crud import search_keyword_chunks

query = "What drove Apple's revenue growth?"

semantic_results = search_embeddings(
    query=query,
    limit=25,
    deduplicate_documents=False,
)

keyword_results = search_keyword_chunks(
    query=query,
    limit=25,
)

rrf_k = 60

scores = {}

for rank, result in enumerate(semantic_results, start=1):
    chunk_id = result.payload.get("chunk_id", result.id)

    scores.setdefault(chunk_id, {
        "semantic_rank": None,
        "keyword_rank": None,
        "rrf_score": 0.0,
    })

    scores[chunk_id]["semantic_rank"] = rank
    scores[chunk_id]["rrf_score"] += 1 / (rrf_k + rank)

for rank, result in enumerate(keyword_results, start=1):
    chunk_id = result["chunk_id"]

    scores.setdefault(chunk_id, {
        "semantic_rank": None,
        "keyword_rank": None,
        "rrf_score": 0.0,
    })

    scores[chunk_id]["keyword_rank"] = rank
    scores[chunk_id]["rrf_score"] += 1 / (rrf_k + rank)

ranked = sorted(
    scores.items(),
    key=lambda item: (-item[1]["rrf_score"], item[0]),
)

print("\nRRF CONTRIBUTION ANALYSIS")
print("=" * 75)

for chunk_id, details in ranked:
    print(
        f"Chunk: {chunk_id} | "
        f"Semantic rank: {details['semantic_rank']} | "
        f"Keyword rank: {details['keyword_rank']} | "
        f"RRF score: {details['rrf_score']:.6f}"
    )
