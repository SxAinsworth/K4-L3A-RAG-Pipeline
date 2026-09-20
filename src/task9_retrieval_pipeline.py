"""Task 9: orchestrate dense, lexical, hybrid, and fallback retrieval."""

from __future__ import annotations

from typing import Any

from .contracts import validate_search_results
from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search

SCORE_THRESHOLD = 0.3
DEFAULT_TOP_K = 5


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict[str, Any]]:
    """Retrieve evidence and use PageIndex only for a weak dense match.

    The fallback decision deliberately uses the original dense similarity,
    because an RRF score has a different scale and cannot be compared with a
    dense-score threshold.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if top_k <= 0:
        return []

    candidate_k = top_k * 2
    dense_results = semantic_search(query, top_k=candidate_k)
    sparse_results = lexical_search(query, top_k=candidate_k)

    if use_reranking:
        combined = rerank_rrf([dense_results, sparse_results], top_k=top_k)
        expected_method = "hybrid"
    else:
        combined = [
            {**item, "metadata": dict(item["metadata"])}
            for item in dense_results[:top_k]
        ]
        expected_method = "dense"

    best_dense_score = float(dense_results[0]["score"]) if dense_results else 0.0
    if best_dense_score < score_threshold:
        try:
            fallback = pageindex_search(query, top_k=top_k)
            if fallback:
                fallback = fallback[:top_k]
                validate_search_results(
                    fallback, top_k=top_k, expected_method="pageindex"
                )
                return fallback
        except Exception:
            # PageIndex is optional. Its outage must not discard local evidence.
            pass

    validate_search_results(
        combined, top_k=top_k, expected_method=expected_method
    )
    return combined
