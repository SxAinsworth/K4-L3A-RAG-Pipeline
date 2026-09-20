"""Task 5 - dense semantic search over the shared Chroma collection."""

from .contracts import validate_search_results
from .task4_chunking_indexing import embed_texts, get_collection


def _restore_metadata(metadata: dict) -> dict:
    restored = dict(metadata)
    if restored.get("url") == "":
        restored["url"] = None
    return restored


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Return unique dense SearchResults sorted by cosine similarity."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if top_k <= 0:
        return []

    collection = get_collection()
    available = collection.count() if hasattr(collection, "count") else top_k
    if available <= 0:
        return []

    query_vector = embed_texts([query.strip()])[0]
    response = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, available),
        include=["documents", "metadatas", "distances"],
    )

    rows = zip(
        response.get("ids", [[]])[0],
        response.get("documents", [[]])[0],
        response.get("metadatas", [[]])[0],
        response.get("distances", [[]])[0],
    )
    by_id: dict[str, dict] = {}
    for item_id, content, metadata, distance in rows:
        result = {
            "id": item_id,
            "content": content,
            "score": float(1.0 - float(distance)),
            "metadata": _restore_metadata(metadata),
            "retrieval_method": "dense",
        }
        previous = by_id.get(item_id)
        if previous is None or result["score"] > previous["score"]:
            by_id[item_id] = result

    results = sorted(
        by_id.values(), key=lambda item: (-item["score"], item["id"])
    )[:top_k]
    validate_search_results(results, top_k=top_k, expected_method="dense")
    return results


if __name__ == "__main__":
    for result in semantic_search(
        "Điều kiện để sinh viên được công nhận tốt nghiệp là gì?", top_k=3
    ):
        print(result["score"], result["metadata"]["source"], result["content"][:160])
