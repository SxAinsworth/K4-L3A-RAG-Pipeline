"""
Task 7 — Reciprocal Rank Fusion.

RRF gộp nhiều bảng xếp hạng mà không cộng trực tiếp cosine score với BM25
score. Công thức: RRF(d) = sum(1 / (k + rank)), rank bắt đầu từ 1.

Lưu ý: RRF score chỉ phản ánh thứ hạng, không dùng để quyết định fallback.

-> Dùng Jina hoặc self host hoặc bất cứ công cụ nào bạn quen
"""

from copy import deepcopy

from .contracts import validate_search_results


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Fuse nhiều ranked lists và trả hybrid SearchResult."""
    if top_k <= 0:
        return []
    if k < 0:
        raise ValueError("RRF k must be non-negative")

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    first_seen: dict[str, int] = {}
    discovery_order = 0

    for ranked_list in ranked_lists:
        seen_in_list = set()
        for rank, item in enumerate(ranked_list, 1):
            item_id = item["id"]
            if item_id in seen_in_list:
                continue
            seen_in_list.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            if item_id not in items:
                items[item_id] = deepcopy(item)
                first_seen[item_id] = discovery_order
                discovery_order += 1

    ranked_ids = sorted(
        scores,
        key=lambda item_id: (-scores[item_id], first_seen[item_id]),
    )
    results = []
    for item_id in ranked_ids[:top_k]:
        result = items[item_id]
        result["score"] = scores[item_id]
        result["retrieval_method"] = "hybrid"
        results.append(result)

    validate_search_results(results, top_k=top_k, expected_method="hybrid")
    return results


if __name__ == "__main__":
    dense = [
        {"id": "a", "content": "A", "score": 0.9, "metadata": {
            "source": "a.md", "title": "A", "doc_type": "legal",
            "url": None, "chunk_index": 0,
        }, "retrieval_method": "dense"},
        {"id": "b", "content": "B", "score": 0.8, "metadata": {
            "source": "b.md", "title": "B", "doc_type": "news",
            "url": "https://example.com", "chunk_index": 0,
        }, "retrieval_method": "dense"},
    ]
    bm25 = [dense[1], dense[0]]
    for result in rerank_rrf([dense, bm25], top_k=2):
        print(result)
