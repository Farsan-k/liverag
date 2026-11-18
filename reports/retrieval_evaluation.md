Retrieval Evaluation Report
Project: Finova AI / LiveRAG
Phase: Week 2 — Retrieval Quality Evaluation
Status: Evaluation and regression testing completed
Date: 18 November 2026
1. Objective
Week 2 focused on establishing a retrieval-quality baseline for the current document and chunk retrieval implementation, testing similarity-score thresholds, validating PDF text extraction, and checking that changes did not break existing functionality.

The goal was to measure the current behavior before making further retrieval changes.
2. Evaluation scope and limitations
The evaluation scripts cover:
- Document-level retrieval.
- Chunk-level retrieval.
- Precision@K, Recall@K, Mean Reciprocal Rank (MRR), and Hit Rate@K.
- Correct abstentions, false-positive queries, and abstention rate for queries whose expected evidence is absent from the currently indexed test corpus.
- Similarity-threshold experiments.
- Automated regression tests.
Important limitation: The current retrieval evaluation corpus is small and consists mostly of synthetic/test content. The chunk inventory contains seven chunks, and the evaluation set contains eight queries. The Apple FY2025 10-K PDF was validated for text extraction, but its extracted financial facts are not represented in the current indexed chunks used by this retrieval evaluation. Therefore, these results are preliminary engineering measurements, not a representative production benchmark.

Queries labelled unsupported mean unsupported by the currently indexed evaluation chunks. They must not be interpreted as facts absent from the actual Apple 10-K.
3. Document-level retrieval baseline
The document-level baseline used a similarity threshold of 0.30.
Metric	Result
Precision@5	0.233
Recall@5	1.000
MRR	1.000
Hit Rate@5	100%
Correct abstentions	0/4


A document-level threshold experiment was also performed:
Threshold	Precision@5	Recall@5	MRR	Hit Rate@5	Correct abstentions
0.30	0.233	1.000	1.000	100%	0/4
0.40	0.233	1.000	1.000	100%	0/4
0.50	0.233	1.000	1.000	100%	0/4
0.60	0.167	0.667	0.667	66.67%	2/4


Interpretation: Increasing the threshold to 0.60 reduced retrieval of irrelevant results in some cases, but also reduced recall and hit rate. The lower thresholds did not improve abstention behavior.
4. Chunk-level retrieval baseline
Chunk-level evaluation disables document deduplication so multiple relevant chunks from the same document can be retrieved. The baseline threshold was 0.30.
Metric	Result
Precision@5	0.320
Recall@5	1.000
MRR	1.000
Hit Rate@5	100%
Correct abstentions	0/3
False-positive rate	100%
Abstention rate	0%


The evaluation contains five supported queries and three queries whose expected evidence is absent from the currently indexed evaluation chunks.
5. Chunk-level threshold experiment
Threshold	Precision@5	Recall@5	MRR	Hit Rate@5	Correct abstentions	False-positive rate	Abstention rate
0.30	0.320	1.000	1.000	100%	0/3	100%	0%
0.40	Not recorded in the retained summary	Not recorded	Not recorded	Not recorded	Not recorded	Not recorded	Not recorded
0.50	0.240	0.800	1.000	100%	0/3	100%	0%
0.60	0.120	0.300	0.600	60%	1/3	66.67%	33.33%
0.70	0.120	0.300	0.600	60%	2/3	33.33%	66.67%
0.80	0.040	0.100	0.200	20%	3/3	0%	100%


Note on threshold 0.40: The retained experiment output did not include a complete metric summary for this threshold. It is intentionally marked as not recorded rather than inferred.
Interpretation
- At 0.30, supported queries were retrieved successfully, but all three currently unsupported queries still received results.
- At 0.50, recall decreased while the false-positive rate remained unchanged.
- At 0.60 and 0.70, abstention improved, but retrieval quality for supported queries deteriorated.
- At 0.80, all three unsupported queries were correctly abstained from, but supported-query retrieval fell substantially.
A single global similarity threshold does not provide a satisfactory balance between retrieval coverage and abstention for this small test corpus.
6. Retrieval implementation and tests
The retrieval implementation supports:
- Configurable result limits.
- Optional similarity-score filtering.
- Retrieval of additional candidates before applying the final result limit.
- Document-level deduplication by default.
- Chunk-level retrieval when deduplicate_documents=False.
- Descending similarity-score ordering.
The retrieval-quality tests verify:
1. At most one chunk per document when document deduplication is enabled.
2. Filtering of results below the configured threshold.
3. Retrieval of extra candidates.
4. Descending score order.
All four retrieval-quality tests passed in the final full test run.
7. PDF extraction validation
The Apple FY2025 10-K PDF was checked using the project's PyMuPDF-based extraction implementation.
Validation	Result
PDF pages	80
Extracted characters	273,701
Empty pages	0


The following financial statement areas were inspected:
- Statements of operations.
- Balance sheet.
- Cash flow statement.
- Revenue by product.
Text extraction passed the existing PDF extraction tests. However, table extraction is not yet considered production-ready: some table values appear as merged or split strings. Financial table parsing should be treated as a separate improvement rather than assuming that successful text extraction guarantees reliable structured table extraction.
8. Regression testing
After restoring the missing store_embedding() function used by PostgreSQL-to-Qdrant synchronization, the previously failing synchronization and document-update tests passed.

Final full-suite result:
Result	Count
Tests collected	118
Passed	118
Failed	0
Warnings	1
Runtime	27.07 seconds


The single warning was a Starlette deprecation warning concerning the anyio.abc.BlockingPortal alias. It did not cause a test failure.
9. Decisions and recommendations
1. Keep 0.30 as the provisional evaluation baseline, not as a production-validated threshold.
2. Do not adopt 0.70 or 0.80 as a global production threshold based on this experiment; they substantially reduce supported-query retrieval.
3. Treat similarity as a ranking signal, not proof that the retrieved evidence answers the question.
4. Retain answer/evidence validation and safe fallback behavior. A separate answerability or grounding check should be evaluated before relying on retrieval scores to decide whether to answer.
5. Expand the evaluation set with real extracted financial-report chunks and manually verified expected chunk IDs before drawing production conclusions.
6. Include more companies, reporting periods, question types, and genuinely unanswerable questions in the next evaluation dataset.
7. Improve structured financial-table extraction and validate numeric facts independently.
10. Week 2 completion checklist
- [x] Document-level retrieval baseline measured.
- [x] Chunk-level retrieval baseline measured.
- [x] Precision@K, Recall@K, MRR, and Hit Rate@K evaluated.
- [x] False-positive and abstention metrics added.
- [x] Similarity-threshold experiments completed.
- [x] PDF extraction quality validated.
- [x] Retrieval-quality tests passed.
- [x] Qdrant synchronization and document-update tests passed.
- [x] Full regression suite passed: 118/118.
- [x] Evaluation findings and limitations documented.
Conclusion: Week 2 evaluation and regression testing are complete. The current implementation has a passing automated test suite and a documented preliminary retrieval baseline. Production retrieval quality remains to be validated against a larger corpus of real, indexed financial-report content.