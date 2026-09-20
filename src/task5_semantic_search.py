"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.
"""

from .task4_chunking_indexing import embed_texts, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về dense SearchResult theo score giảm dần."""
    if not query.strip() or top_k <= 0:
        return []
    collection = get_collection()
    # Avoid loading a potentially large embedding model when indexing has not
    # happened yet. The hasattr guard keeps the public query-only collection
    # interface usable in contract tests and alternative backends.
    if hasattr(collection, "count") and collection.count() == 0:
        return []
    try:
        response = collection.query(
            query_embeddings=[embed_texts([query])[0]], n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as error:
        if "empty" in str(error).lower() or "count" in str(error).lower():
            return []
        raise
    results = [
        {"id": item_id, "content": content, "score": max(0.0, 1.0 - float(distance)),
         "metadata": metadata, "retrieval_method": "dense"}
        for item_id, content, metadata, distance in zip(
            response["ids"][0], response["documents"][0], response["metadatas"][0], response["distances"][0]
        )
    ]
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    for result in semantic_search("test query", top_k=3):
        print(result)
