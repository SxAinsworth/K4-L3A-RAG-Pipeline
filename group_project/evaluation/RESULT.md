# RAG evaluation results

> Status: Tasks 1–10, the Streamlit integration, and all local contract tests are complete. A retrieval-only A/B diagnostic has been run on all 15 golden cases. The four generation metrics remain `N/A` because no generator or evaluator model/API key is configured; no metric has been fabricated.

## Run information

| Field | Value |
| --- | --- |
| Evaluation date | 2026-09-20 |
| Framework and version | Ragas 0.4.3 installed; full Ragas run not started |
| Evaluator model | Not configured |
| Generator model | Not configured |
| Embedding model | Local TF-IDF + LSA v1, L2-normalized, 384 dimensions |
| Corpus version/commit | Working tree based on `6a2a2d4`; 3 legal documents, 5 public pages, 1,134 indexed chunks |
| Golden dataset size | 15 grounded cases |
| `top_k` | 5 final results; hybrid retrieves 10 dense + 10 BM25 candidates |
| Fallback threshold and calibration | `0.3` starter value; not calibrated; PageIndex live API unavailable without key |

## Configurations

- **Config A — dense-only:** `semantic_search(question, top_k=5)` using the shared local LSA query embedding and Chroma cosine similarity.
- **Config B — hybrid + RRF:** dense top 10 plus BM25 top 10, fused exactly once with RRF `k=60`, returning top 5.

Both retrieval configurations used the same corpus, chunking, embedding space, questions and `top_k`. PageIndex fallback and generation were excluded from this diagnostic so that only retrieval strategy changed.

## Retrieval configuration

- Chunking method: recursive boundary-aware splitting implemented locally.
- Chunk size/overlap: 500/50 characters.
- Embedding: persisted TF-IDF + LSA model with 384-dimensional normalized vectors.
- Lexical retrieval: BM25L over title, source and chunk content.
- Fusion: Reciprocal Rank Fusion, `sum(1 / (60 + rank))`.
- Vector store: persistent ChromaDB cosine collection with stable `relative/path::chunk-XXXX` IDs.
- Rationale: the local embedding is reproducible and API-key-free, while BM25 provides exact matching for policy terms, document codes and names. Its main limitation is weaker multilingual semantic generalization than a pretrained embedding model.

## Retrieval-only A/B diagnostic

The expected document was derived from each golden case's `expected_context`. Source hit@5 only checks whether at least one chunk from that document appears in the top five; it does **not** prove that the exact supporting passage was retrieved.

| Diagnostic | Config A | Config B | Delta B−A |
| --- | ---: | ---: | ---: |
| Source hit@5 | 93.33% | 86.67% | −6.66 pp |
| Source MRR@5 | 0.7000 | 0.5678 | −0.1322 |
| Mean retrieval latency | 239.13 ms | 260.82 ms | +21.69 ms |
| P95 retrieval latency | 276.29 ms | 339.35 ms | +63.06 ms |

Latency was measured after warming both indexes, with three repetitions of all 15 questions on the same local machine. It is useful for comparison within this run, not as a production benchmark.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
| --- | ---: | ---: | ---: |
| Faithfulness | N/A | N/A | N/A |
| Answer relevance | N/A | N/A | N/A |
| Context recall | N/A | N/A | N/A |
| Context precision | N/A | N/A | N/A |
| **Average** | N/A | N/A | N/A |

These values require answers produced by the same configured generator and judged under the same evaluator settings. Neither model is currently available in `.env`.

## A/B comparison

- **Better configuration for this retrieval diagnostic:** Config A — dense-only.
- **Evidence:** dense-only found the expected source for 14/15 questions, while hybrid found it for 13/15. Dense-only also had higher MRR and lower warmed latency.
- **Interpretation:** this result does not establish that dense-only produces better final answers. The golden set is dominated by HCMUE questions, and source hit does not measure passage-level relevance or faithfulness.
- **Trade-off:** hybrid added about 9.1% mean latency in this local run and sometimes allowed several chunks from the same competing document to occupy the top five.

## Worst performers

| # | Question | Config | Observed result | Failure stage | Root cause |
| --: | --- | --- | --- | --- | --- |
| 1 | Sinh viên HCMUE vắng thi không có lý do chính đáng bị xử lý thế nào? | A and B | Expected HCMUE source absent from top 5 | Retrieval | Nearly identical clauses from Văn Lang, IUH, Đại Nam and Thăng Long ranked higher; the HCMUE acronym is not strongly represented in the source metadata/content |
| 2 | Các điều kiện chính để sinh viên HCMUE được công nhận tốt nghiệp là gì? | B | HCMUE was rank 4 in dense but removed from hybrid top 5 | Fusion/diversity | Three Văn Lang chunks occupied hybrid ranks 1–3, so RRF lacked document-level diversity |
| 3 | Đánh giá trực tuyến tại HCMUE được đóng góp tối đa bao nhiêu phần trăm? | A and B | Expected source appeared at ranks 4 and 5 | Retrieval | Relevant terminology is shared across multiple university regulations and the exact evidence is split across nearby chunks |

## Recommendations

| Priority | Action | Evidence | Expected impact | How to verify |
| --: | --- | --- | --- | --- |
| 1 | Configure one generator and evaluator, then implement the reproducible Ragas A/B runner | Four required generation metrics are still unavailable | Produces valid faithfulness, relevance, recall and precision scores | Run both configs over all 15 cases with identical prompt/model settings |
| 2 | Add institution aliases to metadata and introduce document-level diversity after RRF | Case 7 missed HCMUE; case 11 was crowded out by three Văn Lang chunks | Improves institution-specific retrieval and reduces duplicate-source top-k results | Re-run source hit@5/MRR and inspect cases 7 and 11 |
| 3 | Calibrate dense threshold and test live PageIndex fallback with in-domain/out-of-domain queries | Threshold remains the uncalibrated starter value and no PageIndex key is available | Reduces unnecessary fallback and unsupported answers | Sweep candidate thresholds, then verify fallback rate and answer refusal behavior |

## Bonus experiments

No bonus generation experiment has been run. Query expansion, cross-encoder reranking and conversation memory should be tested only after the reproducible generator/evaluator baseline exists.
