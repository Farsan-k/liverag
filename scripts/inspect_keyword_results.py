
from app.crud import search_keyword_chunks

queries = [
    "Apple",
    "revenue",
    "growth",
    "Apple revenue",
    "revenue growth",
    "iPhone services",
    "Apple revenue growth",
    "What drove Apple's revenue growth?",
]

for query in queries:
    print(f"\nQuery: {query}")

    results = search_keyword_chunks(query, limit=10)

    if not results:
        print("No keyword matches")
        continue

    for result in results:
        print(
            f"Chunk ID: {result['chunk_id']} | "
            f"Rank: {result['rank']:.4f} | "
            f"Text: {result['text'][:100]}"
        )
