
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


def evaluate_retrieval(k=5, threshold=0.30):
    if k < 1:
        raise ValueError("k must be at least 1")

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    precision_scores = []
    recall_scores = []
    reciprocal_ranks = []
    hit_count = 0

    unsupported_total = 0
    unsupported_no_results = 0

    print("\n=== LiveRAG Retrieval Evaluation ===\n")

    for case in EVALUATION_CASES:
        question = case["question"]
        expected_ids = set(case["expected_document_ids"])

        results = search_embeddings(
            query=question,
            limit=k,
            score_threshold=threshold,
        )

        ranked_ids = [
            result.payload.get("document_id")
            for result in results
            if result.payload
        ]

        if not expected_ids:
            unsupported_total += 1

            no_results = len(ranked_ids) == 0

            if no_results:
                unsupported_no_results += 1

            print(f"Question: {question}")
            print("Expected: No relevant documents")
            print(f"Retrieved: {ranked_ids}")
            print(f"Correct abstention: {no_results}")
            print("-" * 50)
            continue

        retrieved_relevant = (
            set(ranked_ids[:k]) & expected_ids
        )

        precision = len(retrieved_relevant) / k
        recall = len(retrieved_relevant) / len(expected_ids)

        rank = next(
            (
                position
                for position, document_id
                in enumerate(ranked_ids[:k], start=1)
                if document_id in expected_ids
            ),
            None,
        )

        reciprocal_rank = 1 / rank if rank else 0

        precision_scores.append(precision)
        recall_scores.append(recall)
        reciprocal_ranks.append(reciprocal_rank)

        if rank is not None:
            hit_count += 1

        print(f"Question: {question}")
        print(f"Expected: {sorted(expected_ids)}")
        print(f"Retrieved: {ranked_ids}")
        print(f"Precision@{k}: {precision:.3f}")
        print(f"Recall@{k}: {recall:.3f}")
        print(f"First relevant rank: {rank}")
        print("-" * 50)

    supported_total = len(precision_scores)

    print("\n========== FINAL BASELINE ==========")

    if supported_total:
        print(
            f"Precision@{k}: "
            f"{sum(precision_scores) / supported_total:.3f}"
        )
        print(
            f"Recall@{k}: "
            f"{sum(recall_scores) / supported_total:.3f}"
        )
        print(
            f"MRR: "
            f"{sum(reciprocal_ranks) / supported_total:.3f}"
        )
        print(
            f"Hit Rate@{k}: "
            f"{hit_count / supported_total:.2%}"
        )

    print(f"\nSupported queries: {supported_total}")
    print(f"Unsupported queries: {unsupported_total}")
    print(
        "Correct abstentions: "
        f"{unsupported_no_results}/{unsupported_total}"
    )


if __name__ == "__main__":
    for threshold in [0.30, 0.40, 0.50, 0.60]:
        print(f"\n\n{'=' * 20}")
        print(f"THRESHOLD EXPERIMENT: {threshold}")
        print(f"{'=' * 20}")

        evaluate_retrieval(threshold=threshold)