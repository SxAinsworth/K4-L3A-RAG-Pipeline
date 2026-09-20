"""
Task 7 — Reciprocal Rank Fusion.

RRF gộp nhiều bảng xếp hạng mà không cộng trực tiếp cosine score với BM25
score. Công thức: RRF(d) = sum(1 / (k + rank)), rank bắt đầu từ 1.

Lưu ý: RRF score chỉ phản ánh thứ hạng, không dùng để quyết định fallback.

-> Dùng Jina hoặc self host hoặc bất cứ công cụ nào bạn quen
"""

from .contracts import validate_search_results


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Fuse nhiều ranked lists và trả hybrid SearchResult."""
    if not isinstance(ranked_lists, list) or any(
        not isinstance(ranked_list, list) for ranked_list in ranked_lists
    ):
        raise TypeError("ranked_lists must be a list of ranked result lists")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0:
        raise ValueError("top_k must be a non-negative integer")
    if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        raise ValueError("k must be a positive integer")
    if top_k == 0:
        return []

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    first_seen: dict[str, int] = {}
    encounter_index = 0
    for ranked_list in ranked_lists:
        seen_in_list: set[str] = set()
        for rank, item in enumerate(ranked_list, 1):
            if not isinstance(item, dict):
                raise ValueError("each ranked item must be a dict")
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError("each ranked item must have a non-empty id")
            if item_id in seen_in_list:
                continue
            seen_in_list.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            if item_id not in items:
                items[item_id] = item
                first_seen[item_id] = encounter_index
                encounter_index += 1

    ranked_ids = sorted(scores, key=lambda item_id: (-scores[item_id], first_seen[item_id]))
    results: list[dict] = []
    for item_id in ranked_ids[:top_k]:
        result = items[item_id].copy()
        result["score"] = scores[item_id]
        result["retrieval_method"] = "hybrid"
        results.append(result)
    validate_search_results(results, top_k=top_k, expected_method="hybrid")
    return results


if __name__ == "__main__":
    print("Run tests/test_contracts.py to verify rerank_rrf().")
