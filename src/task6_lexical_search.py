"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""


CORPUS: list[dict] = []


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    from rank_bm25 import BM25Okapi
    return BM25Okapi([item["content"].lower().split() for item in corpus])


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    import numpy as np
    global CORPUS
    if not CORPUS:
        from .task4_chunking_indexing import chunk_documents, load_documents
        CORPUS = chunk_documents(load_documents())
    if not query.strip() or top_k <= 0 or not CORPUS:
        return []
    query_tokens = query.lower().split()
    scores = build_bm25_index(CORPUS).get_scores(query_tokens)
    # BM25Okapi can assign zero IDF to every term in a tiny corpus. Preserve
    # deterministic lexical retrieval for that edge case without replacing BM25
    # on a normal corpus.
    if not np.any(scores > 0):
        query_terms = set(query_tokens)
        scores = np.array([
            float(len(query_terms.intersection(item["content"].lower().split())))
            for item in CORPUS
        ])
    results = []
    for index in np.argsort(scores)[::-1]:
        if scores[index] <= 0 or len(results) >= top_k:
            continue
        item = CORPUS[int(index)]
        results.append({**item, "score": float(scores[index]), "retrieval_method": "bm25"})
    return results


if __name__ == "__main__":
    for result in lexical_search("test query", top_k=3):
        print(result)
