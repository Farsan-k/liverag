
from sqlalchemy import select, func

from app.database import SessionLocal
from app.models import Document, DocumentChunk






def search_keyword_fallback(query, limit=5):
    from app.crud import search_keyword_chunks

    # Stage 1: strict AND search
    strict_results = search_keyword_chunks(query, limit)

    if strict_results:
        return "strict", strict_results

    # Stage 2: OR-based fallback
    fallback_results = search_keyword_or(query, limit)

    return "fallback", fallback_results




def search_keyword_or(query, limit=5):
    if not query or not query.strip():
        return []

    terms = query.lower().replace("?", "").replace("'", "").split()
    stop_words = {
        "what", "which", "who", "how", "is", "was", "were",
        "the", "a", "an", "and", "or", "to", "for", "of",
        "in", "on", "did", "does", "do", "drove"
    }

    terms = list(dict.fromkeys(
        term for term in terms if term not in stop_words
    ))

    if not terms:
        return []

    ts_query = func.to_tsquery(
        "english",
        " | ".join(terms)
    )

    search_vector = func.to_tsvector(
        "english", DocumentChunk.text
    )

    rank = func.ts_rank_cd(
        search_vector, ts_query
    ).label("rank")

    statement = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.text,
            rank,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(search_vector.op("@@")(ts_query))
        .order_by(rank.desc(), DocumentChunk.id.asc())
        .limit(limit)
    )

    with SessionLocal() as session:
        return [
            dict(row)
            for row in session.execute(statement).mappings().all()
        ]


queries = [
    "What drove Apple's revenue growth?",
    "Which products and services contributed to Apple's growth?",
    "What is Apple's growth outlook for next quarter?",
]


for query in queries:
    print("\nQuery:", query)

    search_type, results = search_keyword_fallback(query)

    print("Search strategy:", search_type)

    for result in results:
        print(
            "Chunk:", result["chunk_id"],
            "| Rank:", round(float(result["rank"]), 4),
            "| Text:", result["text"][:120],
        )

    if not results:
        print("No matches")