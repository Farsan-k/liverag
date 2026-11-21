
from app.vector_store import search_embeddings


K = 5

THRESHOLDS = [0.30, 0.40, 0.50, 0.60, 0.70]

EVALUATION_CASES = [
    {
        "query": "What drove Apple's revenue growth?",
        "expected_chunk_ids": [119, 120],
    },
    {
        "query": "Which products and services contributed to Apple's growth?",
        "expected_chunk_ids": [119, 120],
    },
    {
        "query": "What is Apple's growth outlook for next quarter?",
        "expected_chunk_ids": [13, 14],
    },
    {
        "query": "What was the monthly revenue in March 2026?",
        "expected_chunk_ids": [41],
    },
    {
        "query": "What was the net profit in March 2026?",
        "expected_chunk_ids": [41],
    },
    {
        "query": "What was Apple's cash flow in March 2026?",
        "expected_chunk_ids": [],
    },
    {
        "query": "What were Apple's FY2025 net sales?",
        "expected_chunk_ids": [],
    },
    {
        "query": "What was Apple's iPhone revenue amount?",
        "expected_chunk_ids": [],
    },
]


def evaluate_threshold(threshold):
    supported_precision = []
    supported_recall = []
    unsupported_results = 0
    relevant_retained = 0
    total_expected = 0

    print(f"\n{'=' * 75}")
    print(f"THRESHOLD: {threshold}")
    print("=" * 75)

    for case in EVALUATION_CASES:
        query = case["query"]
        expected_ids = set(case["expected_chunk_ids"])

        results = search_embeddings(
            query=query,
            limit=K,
            score_threshold=threshold,
            deduplicate_documents=False,
        )

        retrieved_ids = [
            int(result.payload.get("chunk_id", result.id))
            for result in results
        ]

        relevant_ids = expected_ids.intersection(retrieved_ids)

        if not expected_ids:
            if retrieved_ids:
                unsupported_results += 1

            print(f"\nQuery: {query}")
            print(f"Retrieved: {retrieved_ids}")
            print(f"Unsupported query returned results: {bool(retrieved_ids)}")
            continue

        precision = len(relevant_ids) / K
        recall = len(relevant_ids) / len(expected_ids)

        supported_precision.append(precision)
        supported_recall.append(recall)

        relevant_retained += len(relevant_ids)
        total_expected += len(expected_ids)

        print(f"\nQuery: {query}")
        print(f"Expected: {sorted(expected_ids)}")
        print(f"Retrieved: {retrieved_ids}")
        print(f"Precision@{K}: {precision:.3f}")
        print(f"Recall@{K}: {recall:.3f}")

    avg_precision = (
        sum(supported_precision) / len(supported_precision)
        if supported_precision else 0
    )

    avg_recall = (
        sum(supported_recall) / len(supported_recall)
        if supported_recall else 0
    )

    return {
        "threshold": threshold,
        "precision": avg_precision,
        "recall": avg_recall,
        "relevant_retained": relevant_retained,
        "total_expected": total_expected,
        "unsupported_results": unsupported_results,
    }


def main():
    results = []

    for threshold in THRESHOLDS:
        results.append(evaluate_threshold(threshold))

    print("\n\n")
    print("=" * 100)
    print("RETRIEVAL THRESHOLD COMPARISON")
    print("=" * 100)

    print(
        f"{'Threshold':<12}"
        f"{'Precision@5':<16}"
        f"{'Recall@5':<12}"
        f"{'Relevant':<15}"
        f"{'Unsupported':<15}"
    )

    for result in results:
        retained = (
            f"{result['relevant_retained']}/"
            f"{result['total_expected']}"
        )

        print(
            f"{result['threshold']:<12.2f}"
            f"{result['precision']:<16.3f}"
            f"{result['recall']:<12.3f}"
            f"{retained:<15}"
            f"{result['unsupported_results']:<15}"
        )


if __name__ == "__main__":
    main()
