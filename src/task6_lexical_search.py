"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""

import math
import re

from .contracts import validate_search_results


CORPUS: list[dict] = []


class _BM25Index:
    def __init__(self, corpus: list[dict]):
        self.corpus = corpus
        self.tokenized = [self._tokenize(item.get("content", "")) for item in corpus]
        self.doc_count = len(self.tokenized)
        self.doc_lengths = [len(tokens) for tokens in self.tokenized]
        self.avgdl = sum(self.doc_lengths) / self.doc_count if self.doc_count else 0.0
        self.df = self._document_frequency()
        self.k1 = 1.5
        self.b = 0.75

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token.lower() for token in re.findall(r"\w+", str(text)) if token]

    def _document_frequency(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tokens in self.tokenized:
            seen: set[str] = set()
            for token in tokens:
                if token in seen:
                    continue
                seen.add(token)
                counts[token] = counts.get(token, 0) + 1
        return counts

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        if not self.corpus:
            return []
        unique_query = []
        seen: set[str] = set()
        for token in query_tokens:
            if token not in seen:
                seen.add(token)
                unique_query.append(token)

        scores = [0.0 for _ in self.corpus]
        for idx, tokens in enumerate(self.tokenized):
            doc_len = self.doc_lengths[idx]
            for term in unique_query:
                if term not in self.df:
                    continue
                tf = tokens.count(term)
                if tf == 0:
                    continue
                idf = math.log((self.doc_count - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * doc_len / self.avgdl) if self.avgdl else tf + self.k1
                scores[idx] += idf * ((self.k1 + 1.0) * tf) / denominator
        return scores


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    if not isinstance(corpus, list):
        raise TypeError("corpus must be a list of documents")
    return _BM25Index(corpus)


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0:
        raise ValueError("top_k must be a non-negative integer")
    if top_k == 0:
        return []

    bm25 = build_bm25_index(CORPUS)
    query_tokens = [token.lower() for token in re.findall(r"\w+", query) if token]
    scores = bm25.get_scores(query_tokens)
    results: list[dict] = []
    for index, score in sorted(enumerate(scores), key=lambda item: item[1], reverse=True):
        if score <= 0:
            continue
        item = CORPUS[index]
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": float(score),
                "metadata": item["metadata"],
                "retrieval_method": "bm25",
            }
        )
        if len(results) >= top_k:
            break
    validate_search_results(results, top_k=top_k, expected_method="bm25")
    return results


if __name__ == "__main__":
    for result in lexical_search("test query", top_k=3):
        print(result)
