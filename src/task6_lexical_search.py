"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""

import re

from .contracts import validate_search_results
from .task4_chunking_indexing import chunk_documents, load_documents


CORPUS: list[dict] = []


def _tokenize(text: str) -> list[str]:
    """Tokenize Unicode, giữ chữ/số trong mã và tiếng Việt."""
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    from rank_bm25 import BM25Okapi

    if not corpus:
        raise ValueError("Cannot build a BM25 index from an empty corpus")
    return BM25Okapi([_tokenize(item["content"]) for item in corpus])


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    if top_k <= 0:
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    corpus = CORPUS if CORPUS else chunk_documents(load_documents())
    if not corpus:
        return []
    bm25 = build_bm25_index(corpus)
    scores = bm25.get_scores(query_tokens)
    query_terms = set(query_tokens)
    ranked_indices = sorted(
        range(len(corpus)),
        key=lambda index: (-float(scores[index]), index),
    )

    results = []
    seen_ids = set()
    for index in ranked_indices:
        item = corpus[index]
        item_id = item["id"]
        if item_id in seen_ids:
            continue
        if float(scores[index]) <= 0 and not (
            query_terms & set(_tokenize(item["content"]))
        ):
            continue
        results.append(
            {
                "id": item_id,
                "content": item["content"],
                "score": float(scores[index]),
                "metadata": dict(item["metadata"]),
                "retrieval_method": "bm25",
            }
        )
        seen_ids.add(item_id)
        if len(results) == top_k:
            break

    validate_search_results(results, top_k=top_k, expected_method="bm25")
    return results


if __name__ == "__main__":
    for result in lexical_search(
        "điều kiện nhận học bổng hỗ trợ học tập",
        top_k=3,
    ):
        print(result)
