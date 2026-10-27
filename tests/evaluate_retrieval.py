
from app.vector_store import search_embeddings


EVALUATION_CASES = [
    {
        "question": "What was the monthly revenue in March 2026?",
        "expected_document_ids": [55],
    },
    {
        "question": "What was the net profit in March 2026?",
        "expected_document_ids": [55],
    },
    {
        "question": "What drove Apple's revenue growth?",
        "expected_document_ids": [84],
    },
    {
        "question": "What did Apple report about quarterly earnings?",
        "expected_document_ids": [8, 43],
    },
    {
        "question": "What was the company's cash flow in March 2026?",
        "expected_document_ids": [],
    },
    {
        "question": "What was the monthly revenue in April 2026?",
        "expected_document_ids": [],
    },
    {
        "question": "What was Apple's net profit in March 2026?",
        "expected_document_ids": [],
    },
    {
        "question": "Which products drove Apple's revenue growth?",
        "expected_document_ids": [84],
    },
    {
        "question": "What earnings outlook did Apple provide for next quarter?",
        "expected_document_ids": [43],
    },
    {
        "question": "What was Apple's revenue in March 2026?",
        "expected_document_ids": [],
    },
]

def evaluate_retrieval():
    hit_at_1 = 0
    recall_at_5 = 0
    reciprocal_ranks = []
    unsupported_queries = 0
    unsupported_queries_without_hits = 0

    print("\n=== LiveRAG Retrieval Evaluation ===\n")

    for case in EVALUATION_CASES:
        question = case["question"]
        expected_ids = case["expected_document_ids"]

        results = search_embeddings(
            query=question,
            limit=5,
            score_threshold=0.30,
        )

        ranked_ids = [
            result.payload.get("document_id")
            for result in results
        ]

        if not expected_ids:
            unsupported_queries += 1
            no_hits = len(ranked_ids) == 0

            if no_hits:
                unsupported_queries_without_hits += 1

            print(f"Question: {question}")
            print("Expected relevant documents: None")
            print(f"Retrieved documents: {ranked_ids}")
            print(f"No documents retrieved: {no_hits}")
            print("-" * 50)
            continue

        rank = next(
            (
                position
                for position, document_id in enumerate(
                    ranked_ids, start=1
                )
                if document_id in expected_ids
            ),
            None,
        )

        if rank == 1:
            hit_at_1 += 1

        if rank is not None:
            recall_at_5 += 1
            reciprocal_ranks.append(1 / rank)
        else:
            reciprocal_ranks.append(0)

        print(f"Question: {question}")
        print(f"Expected relevant documents: {expected_ids}")
        print(f"Retrieved documents: {ranked_ids}")
        print(f"First relevant rank: {rank}")
        print("-" * 50)

    supported_total = len(EVALUATION_CASES) - unsupported_queries

    print("\n=== Summary ===")
    print(f"Total queries: {len(EVALUATION_CASES)}")
    print(f"Supported queries: {supported_total}")

    if supported_total:
        print(f"Hit Rate@1: {hit_at_1 / supported_total:.2%}")
        print(f"Recall@5: {recall_at_5 / supported_total:.2%}")
        print(f"MRR: {sum(reciprocal_ranks) / supported_total:.3f}")

    print(f"Unsupported queries: {unsupported_queries}")
    print(
        "Unsupported queries with no retrieved documents: "
        f"{unsupported_queries_without_hits}/{unsupported_queries}"
    )


if __name__ == "__main__":
    evaluate_retrieval()
