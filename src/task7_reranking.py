"""Task 7: rank fusion with Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from typing import Any

from .contracts import validate_document, validate_search_results


def rerank_rrf(
    ranked_lists: list[list[dict[str, Any]]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse ranked result lists using rank only, not incomparable raw scores.

    A document contributes at most once per input list. The representative
    payload is copied from its first occurrence so callers are never mutated.
    """
    if top_k <= 0:
        return []
    if k < 0:
        raise ValueError("k must be non-negative")

    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}
    first_seen: dict[str, int] = {}
    seen_order = 0

    for ranked_list in ranked_lists:
        seen_in_list: set[str] = set()
        for rank, item in enumerate(ranked_list, start=1):
            validate_document(item, require_chunk=True)
            item_id = item["id"]
            if item_id in seen_in_list:
                continue
            seen_in_list.add(item_id)

            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            if item_id not in items:
                items[item_id] = {
                    "id": item_id,
                    "content": item["content"],
                    "metadata": dict(item["metadata"]),
                }
                first_seen[item_id] = seen_order
                seen_order += 1

    ordered_ids = sorted(
        scores,
        key=lambda item_id: (-scores[item_id], first_seen[item_id], item_id),
    )[:top_k]

    results = [
        {
            **items[item_id],
            "score": scores[item_id],
            "retrieval_method": "hybrid",
        }
        for item_id in ordered_ids
    ]
    validate_search_results(results, top_k=top_k, expected_method="hybrid")
    return results
