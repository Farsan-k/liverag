
from app.vector_store import search_embeddings


K = 5
SCORE_THRESHOLD = 0.30


EVALUATION_CASES = [
    {
        "question": "What drove Apple's revenue growth?",
        "expected_chunk_ids": [119, 120],
    },
    {
        "question": "Which products and services contributed to Apple's revenue growth?",
        "expected_chunk_ids": [119, 120],
    },
    {
        "question": "What growth outlook did Apple give for next quarter?",
        "expected_chunk_ids": [13, 14],
    },
    {
        "question": "What was the monthly revenue in March 2026?",
        "expected_chunk_ids": [41],
    },
    {
        "question": "What was the net profit in March 2026?",
        "expected_chunk_ids": [41],
    },
    {
        "question": "What was Apple's cash flow in March 2026?",
        "expected_chunk_ids": [],
    },
    {
        "question": "What was Apple's FY2025 net sales?",
        "expected_chunk_ids": [],
    },
    {
        "question": "What was Apple's iPhone revenue amount?",
        "expected_chunk_ids": [],
    },
]



def evaluate_chunk_retrieval(k=K, threshold=SCORE_THRESHOLD):

    total_precision = 0
    total_recall = 0
    total_reciprocal_rank = 0

    supported_questions = 0
    hit_count = 0

    correct_abstentions = 0
    unsupported_questions = 0
    false_positive_queries = 0

    print("\n" + "=" * 75)
    print("CHUNK-LEVEL RETRIEVAL EVALUATION")
    print("=" * 75)

    for case in EVALUATION_CASES:

        question = case["question"]
        expected_ids = set(case["expected_chunk_ids"])

        retrieved_results = search_embeddings(
            query=question,
            limit=k,
            score_threshold=threshold,
            deduplicate_documents=False,
        )

        retrieved_ids = [
            result.payload.get("chunk_id")
            for result in retrieved_results
            if result.payload
        ]

        retrieved_relevant = [
            chunk_id
            for chunk_id in retrieved_ids
            if chunk_id in expected_ids
        ]

        print("\nQuestion:", question)
        print("Expected chunk IDs:", sorted(expected_ids))
        print("Retrieved chunk IDs:", retrieved_ids)

        if expected_ids:

            supported_questions += 1

            precision = len(retrieved_relevant) / k
            recall = len(retrieved_relevant) / len(expected_ids)

            reciprocal_rank = 0

            for rank, chunk_id in enumerate(retrieved_ids, start=1):
                if chunk_id in expected_ids:
                    reciprocal_rank = 1 / rank
                    break

            total_precision += precision
            total_recall += recall
            total_reciprocal_rank += reciprocal_rank

            if retrieved_relevant:
                hit_count += 1

            print(f"Precision@{k}: {precision:.3f}")
            print(f"Recall@{k}: {recall:.3f}")
            print(f"Reciprocal Rank: {reciprocal_rank:.3f}")

        else:

            unsupported_questions += 1

            if not retrieved_ids:
                correct_abstentions += 1
            else:
                false_positive_queries += 1

            print(
                "Correct abstention:",
                not retrieved_ids,
            )

    print("\n" + "=" * 75)
    print("FINAL CHUNK-LEVEL METRICS")
    print("=" * 75)

    if supported_questions:

        print(
            f"Precision@{k}: "
            f"{total_precision / supported_questions:.3f}"
        )

        print(
            f"Recall@{k}: "
            f"{total_recall / supported_questions:.3f}"
        )

        print(
            f"MRR: "
            f"{total_reciprocal_rank / supported_questions:.3f}"
        )

        print(
            f"Hit Rate@{k}: "
            f"{hit_count / supported_questions:.2%}"
        )

    print(
        f"Correct Abstentions: "
        f"{correct_abstentions}/{unsupported_questions}"
    )

    if unsupported_questions:

        false_positive_rate = (
            false_positive_queries / unsupported_questions
        )

        abstention_rate = (
            correct_abstentions / unsupported_questions
        )

        print(
            f"False Positive Rate: "
            f"{false_positive_rate:.2%}"
        )

        print(
            f"Abstention Rate: "
            f"{abstention_rate:.2%}"
        )

    print("=" * 75)


if __name__ == "__main__":

    thresholds = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]

    for threshold in thresholds:

        print("\n\n")
        print("#" * 75)
        print(f"RUNNING EVALUATION WITH THRESHOLD: {threshold}")
        print("#" * 75)

        evaluate_chunk_retrieval(
            k=K,
            threshold=threshold,
        )
