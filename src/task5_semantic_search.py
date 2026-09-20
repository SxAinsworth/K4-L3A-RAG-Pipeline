"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.
"""

from .task4_chunking_indexing import embed_texts, get_collection

from .contracts import validate_search_results


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về dense SearchResult theo score giảm dần."""
    if top_k <= 0 or not query.strip():
        return []

    collection = get_collection()
    result_count = collection.count() if hasattr(collection, "count") else top_k
    if result_count == 0:
        return []
    query_vector = embed_texts([query])[0]
    response = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, result_count),
        include=["documents", "metadatas", "distances"],
    )

    results_by_id = {}
    for item_id, content, metadata, distance in zip(
        response["ids"][0],
        response["documents"][0],
        response["metadatas"][0],
        response["distances"][0],
    ):
        normalized_metadata = dict(metadata)
        if normalized_metadata.get("url") == "":
            normalized_metadata["url"] = None
        result = {
            "id": item_id,
            "content": content,
            "score": max(0.0, 1.0 - float(distance)),
            "metadata": normalized_metadata,
            "retrieval_method": "dense",
        }
        previous = results_by_id.get(item_id)
        if previous is None or result["score"] > previous["score"]:
            results_by_id[item_id] = result

    results = sorted(
        results_by_id.values(),
        key=lambda item: (-item["score"], item["id"]),
    )[:top_k]
    validate_search_results(results, top_k=top_k, expected_method="dense")
    return results


if __name__ == "__main__":
    for result in semantic_search(
        "điều kiện nhận học bổng hỗ trợ học tập",
        top_k=3,
    ):
        print(result)
