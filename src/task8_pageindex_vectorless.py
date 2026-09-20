"""Task 8: PageIndex vectorless fallback with persistent document IDs."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .contracts import validate_search_results
from .task4_chunking_indexing import load_documents


ROOT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = ROOT_DIR / "data" / "standardized"
CACHE_PATH = ROOT_DIR / "pageindex_doc_ids.json"
PDF_CACHE_DIR = ROOT_DIR / "pageindex_pdfs"

load_dotenv(ROOT_DIR / ".env")

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "").strip()
PAGEINDEX_BASE_URL = os.getenv(
    "PAGEINDEX_BASE_URL", "https://api.pageindex.ai"
).rstrip("/")
HTTP_TIMEOUT = float(os.getenv("PAGEINDEX_HTTP_TIMEOUT", "30"))
POLL_TIMEOUT = float(os.getenv("PAGEINDEX_POLL_TIMEOUT", "90"))
POLL_INTERVAL = float(os.getenv("PAGEINDEX_POLL_INTERVAL", "1"))
MAX_WORKERS = max(1, int(os.getenv("PAGEINDEX_MAX_WORKERS", "4")))
PDF_RENDER_VERSION = "2"

_LOGGER = logging.getLogger(__name__)
_FAILED_STATUSES = {"failed", "error", "cancelled", "canceled"}


class PageIndexProviderError(RuntimeError):
    """Raised for a malformed response or failed PageIndex request."""


class _PageIndexHTTPClient:
    """Small timeout-aware adapter for the endpoints exposed by SDK 0.2.8.

    The pinned SDK does not expose a request timeout. This adapter follows the
    same endpoint and response contract while ensuring a provider outage cannot
    leave the fallback request hanging indefinitely.
    """

    def __init__(self, api_key: str):
        self._session = requests.Session()
        self._session.headers.update({"api_key": api_key})

    def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._session.request(
                method,
                f"{PAGEINDEX_BASE_URL}{path}",
                timeout=HTTP_TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise PageIndexProviderError(f"PageIndex request failed: {exc}") from exc
        if not 200 <= response.status_code < 300:
            detail = response.text.strip()[:500]
            raise PageIndexProviderError(
                f"PageIndex returned HTTP {response.status_code}: {detail}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise PageIndexProviderError("PageIndex returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise PageIndexProviderError("PageIndex response must be a JSON object")
        return payload

    def submit_document(self, file_path: str) -> dict[str, Any]:
        with Path(file_path).open("rb") as file_handle:
            return self._json(
                "POST",
                "/doc/",
                files={"file": (Path(file_path).name, file_handle, "application/pdf")},
                data={"if_retrieval": True},
            )

    def submit_query(self, doc_id: str, query: str) -> dict[str, Any]:
        return self._json(
            "POST",
            "/retrieval/",
            json={"doc_id": doc_id, "query": query, "thinking": False},
        )

    def get_retrieval(self, retrieval_id: str) -> dict[str, Any]:
        return self._json("GET", f"/retrieval/{retrieval_id}/")


def _make_client(api_key: str) -> _PageIndexHTTPClient:
    return _PageIndexHTTPClient(api_key)


def _configured_api_key() -> str:
    return os.getenv("PAGEINDEX_API_KEY", PAGEINDEX_API_KEY).strip()


def _fingerprint(document: dict[str, Any]) -> str:
    payload = f"pageindex-pdf-v{PDF_RENDER_VERSION}\0{document['content']}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        return {"version": 1, "documents": {}}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid PageIndex cache: {CACHE_PATH}") from exc

    if isinstance(payload, dict) and isinstance(payload.get("documents"), dict):
        return payload

    # Read the starter/legacy ``source -> doc_id`` cache if it already exists.
    if isinstance(payload, dict) and all(isinstance(value, str) for value in payload.values()):
        return {
            "version": 1,
            "documents": {
                source: {"doc_id": doc_id, "source": source}
                for source, doc_id in payload.items()
            },
        }
    raise RuntimeError(f"Invalid PageIndex cache schema: {CACHE_PATH}")


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(CACHE_PATH)


def _font_path() -> Path:
    configured = os.getenv("PAGEINDEX_PDF_FONT", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    raise RuntimeError(
        "No Unicode font found for Markdown-to-PDF conversion. Set "
        "PAGEINDEX_PDF_FONT to a .ttf font path."
    )


def _pdf_safe_text(text: str) -> str:
    # Keep newlines and tabs, but remove control/surrogate characters that PDF
    # renderers cannot encode reliably.
    normalized = text.translate(
        {
            # Common mathematical dot absent from Arial/Segoe UI. The middle
            # dot preserves the meaning and is available in both fonts.
            ord("⋅"): ord("·"),
        }
    )
    return "".join(
        character
        for character in normalized
        if character in "\n\t"
        or (ord(character) >= 32 and not 0xD800 <= ord(character) <= 0xDFFF)
    )


def _prepare_upload_pdf(document: dict[str, Any]) -> Path:
    """Convert standardized Markdown to a deterministic, Unicode PDF."""
    from fpdf import FPDF

    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    source_digest = hashlib.sha256(document["id"].encode("utf-8")).hexdigest()[:12]
    content_digest = _fingerprint(document)[:12]
    output_path = PDF_CACHE_DIR / f"{source_digest}-{content_digest}.pdf"
    if output_path.is_file() and output_path.stat().st_size > 0:
        return output_path

    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("CorpusUnicode", fname=str(_font_path()))
    pdf.add_page()
    pdf.set_font("CorpusUnicode", size=11)

    text = _pdf_safe_text(document["content"])
    for line in text.splitlines():
        pdf.set_x(pdf.l_margin)
        if line.strip():
            pdf.multi_cell(0, 6, line)
        else:
            pdf.ln(3)
    pdf.output(str(output_path))
    return output_path


def upload_documents() -> None:
    """Upload changed corpus documents and persist ``source -> doc_id`` data."""
    api_key = _configured_api_key()
    if not api_key:
        raise RuntimeError("PAGEINDEX_API_KEY is not configured")

    documents = load_documents()
    cache = _load_cache()
    cached_documents = cache.setdefault("documents", {})
    active_sources = {document["metadata"]["source"] for document in documents}
    cache_changed = False
    for stale_source in set(cached_documents) - active_sources:
        del cached_documents[stale_source]
        cache_changed = True
    if cache_changed:
        _save_cache(cache)
    client = _make_client(api_key)
    failures: list[str] = []

    for document in documents:
        source = document["metadata"]["source"]
        fingerprint = _fingerprint(document)
        cached = cached_documents.get(source, {})
        if cached.get("doc_id") and cached.get("sha256") == fingerprint:
            continue

        try:
            pdf_path = _prepare_upload_pdf(document)
            response = client.submit_document(str(pdf_path))
            doc_id = response.get("doc_id")
            if not isinstance(doc_id, str) or not doc_id.strip():
                raise PageIndexProviderError("Upload response has no doc_id")
        except Exception as exc:
            failures.append(f"{source}: {exc}")
            continue

        metadata = document["metadata"]
        cached_documents[source] = {
            "doc_id": doc_id.strip(),
            "sha256": fingerprint,
            "source": source,
            "title": metadata["title"],
            "doc_type": metadata["doc_type"],
            "url": metadata.get("url"),
        }
        # Save after every successful upload so an interrupted batch can resume.
        _save_cache(cache)

    if failures:
        raise RuntimeError("Some PageIndex uploads failed: " + " | ".join(failures))


def _metadata_catalog() -> dict[str, dict[str, Any]]:
    try:
        return {
            document["metadata"]["source"]: dict(document["metadata"])
            for document in load_documents()
        }
    except (FileNotFoundError, ValueError):
        return {}


def _poll_retrieval(
    client: Any, doc_id: str, query: str
) -> dict[str, Any]:
    submitted = client.submit_query(doc_id, query)
    retrieval_id = submitted.get("retrieval_id")
    if not isinstance(retrieval_id, str) or not retrieval_id.strip():
        raise PageIndexProviderError("Query response has no retrieval_id")

    deadline = time.monotonic() + max(POLL_TIMEOUT, 0.0)
    while True:
        result = client.get_retrieval(retrieval_id)
        status = str(result.get("status", "")).casefold()
        if status == "completed":
            return result
        if status in _FAILED_STATUSES:
            raise PageIndexProviderError(
                f"PageIndex retrieval {retrieval_id} ended with status={status}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(f"PageIndex retrieval timed out for document {doc_id}")
        time.sleep(max(POLL_INTERVAL, 0.05))


def _content_text(item: Any) -> tuple[str, int | None]:
    if isinstance(item, str):
        return item.strip(), None
    if not isinstance(item, dict):
        return "", None
    text = item.get("relevant_content") or item.get("content") or item.get("text")
    page_index = item.get("page_index")
    if not isinstance(page_index, int) or isinstance(page_index, bool):
        page_index = None
    return str(text or "").strip(), page_index


def _parse_retrieval(
    response: dict[str, Any],
    cache_entry: dict[str, Any],
    document_order: int,
) -> list[dict[str, Any]]:
    nodes = response.get("retrieved_nodes", [])
    if not isinstance(nodes, list):
        raise PageIndexProviderError("retrieved_nodes must be a list")

    doc_id = str(cache_entry["doc_id"])
    source = str(cache_entry["source"])
    parsed: list[dict[str, Any]] = []
    for node_rank, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or f"node-{node_rank}")
        node_title = str(node.get("title") or cache_entry.get("title") or source)
        contents = node.get("relevant_contents", [])
        if isinstance(contents, (str, dict)):
            contents = [contents]
        if not isinstance(contents, list):
            continue

        for content_rank, content_item in enumerate(contents):
            text, page_index = _content_text(content_item)
            if not text:
                continue
            identity = "\0".join((doc_id, node_id, str(page_index), text))
            result_id = "pageindex::" + hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:24]
            metadata = {
                "source": source,
                "title": str(cache_entry.get("title") or source),
                "doc_type": str(cache_entry.get("doc_type") or "legal"),
                "url": cache_entry.get("url"),
                "chunk_index": max(page_index or 0, 0),
                "section_title": node_title,
            }
            if page_index is not None:
                metadata["page_index"] = page_index
            parsed.append(
                {
                    "id": result_id,
                    "content": text,
                    "metadata": metadata,
                    "provider_rank": node_rank,
                    "content_rank": content_rank,
                    "document_order": document_order,
                }
            )
    return parsed


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Query cached PageIndex documents and return ranked SearchResults."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if top_k <= 0:
        return []
    api_key = _configured_api_key()
    if not api_key or not CACHE_PATH.is_file():
        return []

    cache = _load_cache()
    catalog = _metadata_catalog()
    entries: list[dict[str, Any]] = []
    for source, raw_entry in sorted(cache.get("documents", {}).items()):
        if not isinstance(raw_entry, dict) or not raw_entry.get("doc_id"):
            continue
        entry = dict(catalog.get(source, {}))
        entry.update(raw_entry)
        entry.setdefault("source", source)
        entry.setdefault("title", Path(source).stem)
        entry.setdefault("doc_type", source.split("/", 1)[0] or "legal")
        entry.setdefault("url", None)
        entries.append(entry)
    if not entries:
        return []

    candidates: list[dict[str, Any]] = []

    def search_one(order: int, entry: dict[str, Any]) -> list[dict[str, Any]]:
        client = _make_client(api_key)
        response = _poll_retrieval(client, str(entry["doc_id"]), query.strip())
        return _parse_retrieval(response, entry, order)

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(entries))) as executor:
        futures = {
            executor.submit(search_one, order, entry): entry
            for order, entry in enumerate(entries)
        }
        for future in as_completed(futures):
            try:
                candidates.extend(future.result())
            except Exception as exc:
                _LOGGER.warning(
                    "PageIndex fallback skipped %s: %s",
                    futures[future].get("source"),
                    exc,
                )

    candidates.sort(
        key=lambda item: (
            item["provider_rank"],
            item["document_order"],
            item["content_rank"],
            item["id"],
        )
    )
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        rank = len(results) + 1
        results.append(
            {
                "id": candidate["id"],
                "content": candidate["content"],
                "metadata": candidate["metadata"],
                # Retrieval API 0.2.8 does not expose a comparable score.
                "score": 1.0 / rank,
                "retrieval_method": "pageindex",
            }
        )
        if len(results) >= top_k:
            break

    validate_search_results(results, top_k=top_k, expected_method="pageindex")
    return results


if __name__ == "__main__":
    upload_documents()
