"""Task 6 - BM25 lexical search over the same chunks used by dense search."""

import hashlib
import re

from .contracts import validate_search_results


CORPUS: list[dict] = []
_BM25_INDEX = None
_BM25_SIGNATURE: tuple[str, ...] | None = None


def _tokenize(text: str) -> list[str]:
    """Unicode-aware tokenizer suitable for Vietnamese and document codes."""
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def _searchable_text(item: dict) -> str:
    metadata = item.get("metadata", {})
    return " ".join(
        (
            str(metadata.get("title", "")),
            str(metadata.get("source", "")),
            str(item.get("content", "")),
        )
    )


def build_bm25_index(corpus: list[dict]):
    """Build BM25 over title, source filename, and chunk content."""
    from rank_bm25 import BM25L

    if not corpus:
        raise ValueError("cannot build a BM25 index from an empty corpus")
    tokenized: list[list[str]] = []
    for item in corpus:
        tokens = _tokenize(_searchable_text(item))
        if not tokens:
            tokens = ["__empty__"]
        tokenized.append(tokens)
    # BM25L keeps useful positive discrimination on very small corpora where
    # Okapi's IDF can become zero or negative for a term present in half of the
    # documents. It remains a BM25-family lexical ranker.
    return BM25L(tokenized)


def _load_shared_corpus() -> list[dict]:
    from .task4_chunking_indexing import chunk_documents, load_documents

    return chunk_documents(load_documents())


def _current_index(corpus: list[dict]):
    global _BM25_INDEX, _BM25_SIGNATURE
    signature = tuple(
        f"{item['id']}:{hashlib.sha256(_searchable_text(item).encode('utf-8')).hexdigest()}"
        for item in corpus
    )
    if _BM25_INDEX is None or signature != _BM25_SIGNATURE:
        _BM25_INDEX = build_bm25_index(corpus)
        _BM25_SIGNATURE = signature
    return _BM25_INDEX


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Return unique BM25 SearchResults sorted by descending BM25 score."""
    global CORPUS
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if top_k <= 0:
        return []
    if not CORPUS:
        CORPUS = _load_shared_corpus()
    if not CORPUS:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    scores = _current_index(CORPUS).get_scores(query_tokens)
    ranked_indices = sorted(
        range(len(CORPUS)),
        key=lambda index: (-float(scores[index]), CORPUS[index]["id"]),
    )

    results: list[dict] = []
    seen: set[str] = set()
    query_token_set = set(query_tokens)
    for index in ranked_indices:
        score = float(scores[index])
        if len(results) >= top_k:
            break
        item = CORPUS[index]
        # Never return arbitrary unmatched chunks merely to fill top_k.
        if score <= 0 and not query_token_set.intersection(
            _tokenize(_searchable_text(item))
        ):
            continue
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": score,
                "metadata": dict(item["metadata"]),
                "retrieval_method": "bm25",
            }
        )

    validate_search_results(results, top_k=top_k, expected_method="bm25")
    return results


if __name__ == "__main__":
    for result in lexical_search("Quyết định 5445 QĐ ĐHBK", top_k=3):
        print(result["score"], result["metadata"]["source"], result["content"][:160])
