# Retrieval Evaluation and Engineering Report

**Project:** Finova AI / LiveRAG
**Report Type:** Retrieval Evaluation, Document Extraction and System Validation
**Status:** Completed
**Date:** 18 November 2026

---

## 1. Objective

The objective of this development phase was to evaluate the existing document and chunk retrieval implementation, establish retrieval-quality baselines, experiment with similarity-score thresholds, validate financial document extraction, and improve the reliability of the PostgreSQL and Qdrant synchronization process.

The work focused on measuring retrieval performance, identifying limitations, validating extraction functionality, and ensuring that existing application features continued to work correctly.

## 2. Evaluation Scope and Limitations

The evaluation covered:

- Document-level retrieval.
- Chunk-level retrieval.
- Precision@K, Recall@K, Mean Reciprocal Rank (MRR), and Hit Rate@K.
- Correct abstentions, false-positive queries, and abstention rate.
- Similarity-threshold experiments.
- PDF text extraction and financial statement validation.
- SEC XBRL data extraction and validation.
- Qdrant synchronization and retrieval functionality.
- Automated regression testing.

**Important limitation:** The current retrieval evaluation corpus is small and consists mostly of synthetic/test content. The chunk inventory contains seven chunks, and the evaluation set contains eight queries.

The Apple FY2025 10-K PDF was validated for text extraction, but its extracted financial facts are not represented in the indexed chunks used for this retrieval evaluation.

Therefore, these results represent preliminary engineering measurements rather than a representative production benchmark.

Queries labelled unsupported mean that their expected evidence was absent from the currently indexed evaluation chunks. They must not be interpreted as facts absent from the actual Apple 10-K.

## 3. Document-Level Retrieval Evaluation

The document-level retrieval baseline used a similarity threshold of `0.30`.

| Metric | Result |
|---|---:|
| Precision@5 | 0.233 |
| Recall@5 | 1.000 |
| MRR | 1.000 |
| Hit Rate@5 | 100% |
| Correct abstentions | 0/4 |

### Similarity Threshold Experiment

| Threshold | Precision@5 | Recall@5 | MRR | Hit Rate@5 | Correct Abstentions |
|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.233 | 1.000 | 1.000 | 100% | 0/4 |
| 0.40 | 0.233 | 1.000 | 1.000 | 100% | 0/4 |
| 0.50 | 0.233 | 1.000 | 1.000 | 100% | 0/4 |
| 0.60 | 0.167 | 0.667 | 0.667 | 66.67% | 2/4 |

**Findings:**

Increasing the threshold to `0.60` reduced retrieval of irrelevant results in some cases, but also reduced recall and hit rate. Lower thresholds did not improve abstention behavior.

## 4. Chunk-Level Retrieval Evaluation

Chunk-level evaluation disables document deduplication so multiple relevant chunks from the same document can be retrieved.

The baseline similarity threshold was `0.30`.

| Metric | Result |
|---|---:|
| Precision@5 | 0.320 |
| Recall@5 | 1.000 |
| MRR | 1.000 |
| Hit Rate@5 | 100% |
| Correct abstentions | 0/3 |
| False-positive rate | 100% |
| Abstention rate | 0% |

The evaluation contains five supported queries and three queries whose expected evidence is absent from the currently indexed evaluation chunks.

### Chunk-Level Similarity Threshold Experiment

| Threshold | Precision@5 | Recall@5 | MRR | Hit Rate@5 | Correct Abstentions | False-positive Rate | Abstention Rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.320 | 1.000 | 1.000 | 100% | 0/3 | 100% | 0% |
| 0.40 | Not recorded | Not recorded | Not recorded | Not recorded | Not recorded | Not recorded | Not recorded |
| 0.50 | 0.240 | 0.800 | 1.000 | 100% | 0/3 | 100% | 0% |
| 0.60 | 0.120 | 0.300 | 0.600 | 60% | 1/3 | 66.67% | 33.33% |
| 0.70 | 0.120 | 0.300 | 0.600 | 60% | 2/3 | 33.33% | 66.67% |
| 0.80 | 0.040 | 0.100 | 0.200 | 20% | 3/3 | 0% | 100% |

**Note:** The retained experiment output did not include a complete metric summary for threshold `0.40`. It is marked as not recorded rather than inferred.

### Findings

- At `0.30`, supported queries were retrieved successfully, but all three currently unsupported queries still received results.
- At `0.50`, recall decreased while the false-positive rate remained unchanged.
- At `0.60` and `0.70`, abstention improved, but retrieval quality for supported queries deteriorated.
- At `0.80`, all three unsupported queries were correctly abstained from, but supported-query retrieval fell substantially.

A single global similarity threshold did not provide a satisfactory balance between retrieval coverage and abstention for this small evaluation corpus.

## 5. Retrieval Implementation and Improvements

The retrieval implementation supports:

- Configurable result limits.
- Optional similarity-score filtering.
- Retrieval of additional candidates before applying the final result limit.
- Document-level deduplication by default.
- Chunk-level retrieval using `deduplicate_documents=False`.
- Descending similarity-score ordering.

Retrieval-quality tests validate:

1. At most one chunk per document when document deduplication is enabled.
2. Filtering of results below the configured threshold.
3. Retrieval of additional candidates.
4. Descending similarity-score ordering.

All four retrieval-quality tests passed in the final full test run.

## 6. PDF Document Extraction and Validation

The Apple FY2025 10-K PDF was processed using the project's PyMuPDF-based extraction implementation.

### Extraction Results

| Validation | Result |
|---|---:|
| PDF pages | 80 |
| Extracted characters | 273,701 |
| Pages containing text | 80 |
| Empty pages | 0 |
| Text coverage | 100% |

The following financial statement areas were inspected:

- Consolidated statements of operations.
- Consolidated balance sheets.
- Consolidated statements of cash flows.
- Revenue breakdown by product.

Text extraction passed the PDF extraction tests.

However, table extraction is not yet considered production-ready. Some table values appear as merged or split strings. Financial table parsing therefore requires additional validation rather than assuming that successful text extraction guarantees reliable structured financial data.

## 7. SEC XBRL Extraction and Validation

The SEC extraction implementation was tested against Apple FY2025 and Microsoft FY2025 filing structures.

Validation covered:

- SEC company identifier (CIK) validation.
- XBRL context extraction.
- Reporting period validation.
- Unit and currency validation.
- Decimal numeric value normalization.
- Scale and sign handling.
- Revenue fact extraction.
- Duplicate fact handling.
- Revenue breakdown reconciliation.

The extraction implementation includes validation of reporting periods, company identifiers, concepts, units, dimensions, and numeric values.

### Focused SEC Extraction Test Results

| Result | Count |
|---|---:|
| Tests passed | 76 |
| Tests failed | 0 |

These tests validate the supported filing structures and extraction scenarios. They do not establish compatibility with every SEC filing or every possible XBRL transformation.

## 8. Database and Vector Synchronization

The PostgreSQL-to-Qdrant synchronization implementation was reviewed and corrected.

The missing `store_embedding()` functionality used by the synchronization process was restored.

The retrieval implementation and synchronization behavior were tested to verify:

- Embedding storage.
- Vector insertion and updates.
- Chunk synchronization.
- Content hash handling.
- Document update behavior.
- Retrieval of updated content.

The previously failing synchronization and document-update tests passed after the correction.

## 9. Regression Testing

A complete automated regression test run was performed after the implementation and validation changes.

### Final Test Results

| Result | Count |
|---|---:|
| Tests collected | 118 |
| Passed | 118 |
| Failed | 0 |
| Warnings | 1 |
| Runtime | 30.58 seconds |

The single warning was a Starlette deprecation warning concerning the `anyio.abc.BlockingPortal` alias. It did not cause a test failure.

The complete test suite finished successfully.

## 10. Key Findings and Recommendations

Based on the evaluation and implementation work, the following findings were identified:

1. Keep `0.30` as the provisional retrieval evaluation baseline, not as a production-validated threshold.
2. Do not adopt `0.70` or `0.80` as global production thresholds based on the current experiment, as they substantially reduce supported-query retrieval.
3. Treat similarity scores as ranking signals, not proof that retrieved evidence answers a question.
4. Retain answer/evidence validation and safe fallback behavior. A separate answerability or grounding check should be evaluated before relying on similarity scores to decide whether to answer.
5. Expand the evaluation dataset with real extracted financial-report chunks and manually verified expected chunk IDs.
6. Include more companies, reporting periods, question types, and genuinely unanswerable questions.
7. Improve structured financial-table extraction and validate numeric financial facts independently.
8. Validate SEC extraction against additional filing structures and XBRL variations.

## 11. Completion Summary

- [x] Document-level retrieval baseline measured.
- [x] Chunk-level retrieval baseline measured.
- [x] Precision@K, Recall@K, MRR, and Hit Rate@K evaluated.
- [x] False-positive and abstention metrics added.
- [x] Similarity-threshold experiments completed.
- [x] Retrieval implementation reviewed and tested.
- [x] PDF extraction quality validated.
- [x] Financial statement pages inspected.
- [x] SEC XBRL extraction and validation tested.
- [x] PostgreSQL-to-Qdrant synchronization corrected and tested.
- [x] Full regression suite passed: 118/118.
- [x] Evaluation findings and limitations documented.

---


## 12. Retrieval Improvements — 19 November 2026

The retrieval implementation was extended with PostgreSQL
full-text keyword search and hybrid retrieval.

### Implemented Improvements

- Added PostgreSQL full-text keyword search using `plainto_tsquery`.
- Added relevance ranking using `ts_rank_cd`.
- Added document metadata retrieval for matching chunks.
- Combined Qdrant semantic retrieval and PostgreSQL keyword
  retrieval using Reciprocal Rank Fusion (RRF).
- Added deterministic ranking for equal relevance scores.
- Added automated tests for keyword and hybrid retrieval.

### Test Results

| Validation | Result |
|---|---:|
| Hybrid search tests | 5 passed |
| Keyword search tests | 4 passed |
| Complete regression suite | 130 passed |
| Failed tests | 0 |
| Warnings | 1 |

The remaining warning concerns the deprecated
`anyio.abc.BlockingPortal` alias in Starlette.

### Current Limitation

The hybrid retrieval implementation has passed automated
tests, but its retrieval-quality improvement has not yet
been established through a sufficiently large, manually
verified financial-document benchmark.

A comparative evaluation of semantic-only, keyword-only,
and hybrid retrieval remains necessary.


---

## Conclusion

The retrieval implementation, document extraction functionality, SEC XBRL validation, and PostgreSQL-to-Qdrant synchronization have been evaluated and tested.

The current implementation has a passing automated test suite, documented retrieval baselines, and validated PDF and SEC extraction scenarios.

The evaluation also identified important limitations in retrieval abstention, corpus size, and structured financial-table extraction.

Further validation using a larger collection of real financial reports and manually verified retrieval evidence is necessary before treating the current retrieval performance as production-ready.
