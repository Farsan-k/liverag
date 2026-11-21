
from app.vector_store import search_embeddings
from app.crud import search_keyword_chunks


K = 5
CANDIDATE_LIMIT = 25
RRF_K = 60

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


def get_semantic_results(query):
    return search_embeddings(
        query=query,
        limit=CANDIDATE_LIMIT,
        deduplicate_documents=False,
    )


def get_keyword_results(query):
    return search_keyword_chunks(
        query=query,
        limit=CANDIDATE_LIMIT,
    )


def get_chunk_id(result, method):
    if method == "semantic":
        return int(result.payload.get("chunk_id", result.id))

    return int(result["chunk_id"])


def calculate_metrics(expected_ids, retrieved_ids):
    expected = set(expected_ids)
    retrieved = retrieved_ids[:K]

    relevant_count = sum(
        1 for chunk_id in retrieved
        if chunk_id in expected
    )

    precision = relevant_count / K

    recall = (
        relevant_count / len(expected)
        if expected else None
    )

    reciprocal_rank = 0.0

    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in expected:
            reciprocal_rank = 1 / rank
            break

    hit = int(relevant_count > 0)

    return precision, recall, reciprocal_rank, hit


def weighted_rrf(
    semantic_results,
    keyword_results,
    semantic_weight=0.5,
    keyword_weight=0.5,
):
    fused_results = {}

    for rank, result in enumerate(semantic_results, start=1):
        chunk_id = get_chunk_id(result, "semantic")

        item = fused_results.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "rrf_score": 0.0,
                "semantic_rank": None,
                "keyword_rank": None,
            },
        )

        item["semantic_rank"] = rank
        item["rrf_score"] += (
            semantic_weight / (RRF_K + rank)
        )

    for rank, result in enumerate(keyword_results, start=1):
        chunk_id = get_chunk_id(result, "keyword")

        item = fused_results.setdefault(
            chunk_id,
            {
                "chunk_id": chunk_id,
                "rrf_score": 0.0,
                "semantic_rank": None,
                "keyword_rank": None,
            },
        )

        item["keyword_rank"] = rank
        item["rrf_score"] += (
            keyword_weight / (RRF_K + rank)
        )

    ranked_results = sorted(
        fused_results.values(),
        key=lambda item: (
            -item["rrf_score"],
            item["chunk_id"],
        ),
    )

    return ranked_results[:K]


def evaluate_method(method_name, search_function):
    supported_metrics = []
    unsupported_results = 0
    retrieved_counts = []

    print(f"\n{'=' * 75}")
    print(f"{method_name.upper()} RESULTS")
    print("=" * 75)

    for case in EVALUATION_CASES:
        query = case["query"]
        expected_ids = case["expected_chunk_ids"]

        results = search_function(query)

        if method_name == "semantic":
            retrieved_ids = [
                get_chunk_id(result, "semantic")
                for result in results
            ]

        elif method_name == "keyword":
            retrieved_ids = [
                get_chunk_id(result, "keyword")
                for result in results
            ]

        else:
            retrieved_ids = [
                int(result["chunk_id"])
                for result in results
            ]

        retrieved_ids = retrieved_ids[:K]
        retrieved_counts.append(len(retrieved_ids))

        print(f"\nQuery: {query}")
        print(f"Retrieved: {retrieved_ids}")

        if not expected_ids:
            unsupported_results += int(bool(retrieved_ids))
            print("Expected: No relevant chunks")
            print(f"Returned results: {len(retrieved_ids)}")
            continue

        precision, recall, mrr, hit = calculate_metrics(
            expected_ids,
            retrieved_ids,
        )

        supported_metrics.append(
            (precision, recall, mrr, hit)
        )

        print(f"Expected: {expected_ids}")
        print(
            f"Precision@{K}: {precision:.3f} | "
            f"Recall@{K}: {recall:.3f} | "
            f"MRR: {mrr:.3f} | "
            f"Hit: {hit}"
        )

    count = len(supported_metrics)

    averages = [
        sum(metric[index] for metric in supported_metrics) / count
        if count else 0
        for index in range(4)
    ]

    return {
        "precision": averages[0],
        "recall": averages[1],
        "mrr": averages[2],
        "hit_rate": averages[3],
        "unsupported_results": unsupported_results,
        "average_results": (
            sum(retrieved_counts) / len(retrieved_counts)
            if retrieved_counts else 0
        ),
    }


def evaluate_rrf(
    semantic_weight,
    keyword_weight,
):
    name = f"weighted_rrf_{semantic_weight}_{keyword_weight}"

    return evaluate_method(
        name,
        lambda query: weighted_rrf(
            get_semantic_results(query),
            get_keyword_results(query),
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
        ),
    )


def print_summary(results):
    print("\n\n")
    print("=" * 115)
    print("COMPARATIVE RETRIEVAL EVALUATION")
    print("=" * 115)

    print(
        f"{'Method':<25}"
        f"{'Precision@5':<15}"
        f"{'Recall@5':<12}"
        f"{'MRR':<10}"
        f"{'Hit Rate':<12}"
        f"{'Avg Results':<13}"
        f"{'Unsupported':<12}"
    )

    for method_name, metrics in results.items():
        print(
            f"{method_name:<25}"
            f"{metrics['precision']:<15.3f}"
            f"{metrics['recall']:<12.3f}"
            f"{metrics['mrr']:<10.3f}"
            f"{metrics['hit_rate']:<12.3f}"
            f"{metrics['average_results']:<13.2f}"
            f"{metrics['unsupported_results']:<12}"
        )


def main():
    results = {}

    methods = {
        "semantic": get_semantic_results,
        "keyword": get_keyword_results,
    }

    for method_name, search_function in methods.items():
        results[method_name] = evaluate_method(
            method_name,
            search_function,
        )

    results["rrf_baseline"] = evaluate_rrf(0.5, 0.5)

    results["weighted_rrf_0.7_0.3"] = evaluate_rrf(0.7, 0.3)

    results["weighted_rrf_0.8_0.2"] = evaluate_rrf(0.8, 0.2)

    print_summary(results)


if __name__ == "__main__":
    main()
