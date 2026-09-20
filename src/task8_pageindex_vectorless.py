"""Task 8 — PageIndex vectorless fallback with cached cloud document IDs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .contracts import validate_search_results
from .task4_chunking_indexing import load_documents


load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
PAGEINDEX_API_URL = os.getenv("PAGEINDEX_API_URL", "https://api.pageindex.ai").rstrip("/")
UPLOAD_DIR = Path(__file__).parent.parent / "data" / "pageindex_uploads"
CACHE_PATH = Path(__file__).parent.parent / "data" / "pageindex_document_ids.json"
REQUEST_TIMEOUT = (10, 120)
PROCESSING_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 5

_CITATION_PATTERN = re.compile(
    r'<(?:cite|doc)\s+doc="(?P<doc>[^"]+)"\s+page="(?P<page>\d+)"'
    r'(?:\s+block="(?P<block>[^"]+)")?\s*/?>',
    re.IGNORECASE,
)


def _api_key() -> str:
    key = os.getenv("PAGEINDEX_API_KEY", PAGEINDEX_API_KEY).strip()
    if not key:
        raise RuntimeError("PAGEINDEX_API_KEY is not configured")
    return key


def _headers() -> dict[str, str]:
    return {"api_key": _api_key()}


def _load_cache() -> dict[str, dict[str, Any]]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(f"Invalid PageIndex cache: {CACHE_PATH}") from error
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) and isinstance(value, dict) for key, value in payload.items()
    ):
        raise RuntimeError(f"Invalid PageIndex cache schema: {CACHE_PATH}")
    return payload


def _save_cache(cache: dict[str, dict[str, Any]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(CACHE_PATH)


def _font_path() -> Path:
    windows_dir = Path(os.getenv("WINDIR", "C:/Windows"))
    candidates = (
        windows_dir / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if path.exists():
            return path
    raise RuntimeError("No Unicode TrueType font found for PageIndex PDF conversion")


def _render_pdf(document: dict, output: Path) -> None:
    from fpdf import FPDF

    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("Unicode", fname=str(_font_path()))
    pdf.set_font("Unicode", size=10)
    pdf.add_page()
    for line in document["content"].splitlines() or [document["content"]]:
        pdf.multi_cell(0, 5, line or " ", new_x="LMARGIN", new_y="NEXT", wrapmode="CHAR")
    pdf.output(str(output))


def _document_hash(document: dict) -> str:
    payload = json.dumps(
        {
            "id": document["id"],
            "content": document["content"],
            "metadata": document["metadata"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _wait_until_ready(doc_id: str) -> None:
    deadline = time.monotonic() + PROCESSING_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = requests.get(
            f"{PAGEINDEX_API_URL}/doc/{doc_id}/metadata",
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        status = str(response.json().get("status", "")).lower()
        if status == "completed":
            return
        if status == "failed":
            raise RuntimeError(f"PageIndex processing failed for {doc_id}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"PageIndex processing timed out for {doc_id}")


def upload_documents() -> None:
    """Upload changed documents and atomically cache source-to-document IDs."""
    cache = _load_cache()
    documents = load_documents()
    current_ids = {document["id"] for document in documents}

    for document in documents:
        document_id = document["id"]
        content_hash = _document_hash(document)
        cached = cache.get(document_id, {})
        if cached.get("sha256") == content_hash and cached.get("doc_id"):
            continue

        pdf_path = UPLOAD_DIR / f"{document_id}.pdf"
        _render_pdf(document, pdf_path)
        with pdf_path.open("rb") as pdf_file:
            response = requests.post(
                f"{PAGEINDEX_API_URL}/doc/",
                headers=_headers(),
                files={"file": (pdf_path.name, pdf_file, "application/pdf")},
                timeout=REQUEST_TIMEOUT,
            )
        response.raise_for_status()
        payload = response.json()
        pageindex_id = payload.get("doc_id") or payload.get("id")
        if not isinstance(pageindex_id, str) or not pageindex_id:
            raise RuntimeError(f"PageIndex upload returned no doc_id for {document_id}")
        _wait_until_ready(pageindex_id)

        cache[document_id] = {
            "doc_id": pageindex_id,
            "filename": pdf_path.name,
            "sha256": content_hash,
            "metadata": document["metadata"],
        }
        _save_cache(cache)

    stale_ids = set(cache) - current_ids
    if stale_ids:
        cache = {key: value for key, value in cache.items() if key in current_ids}
        _save_cache(cache)


def _citation_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    choices = payload.get("choices") or []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    citations = payload.get("citations") or message.get("citations") or []
    if isinstance(citations, list) and citations:
        return [citation for citation in citations if isinstance(citation, dict)]

    content = message.get("content", "") if isinstance(message, dict) else ""
    return [match.groupdict() for match in _CITATION_PATTERN.finditer(str(content))]


def _resolve_content(
    citation: dict[str, Any],
    doc_id: str,
    page_cache: dict[str, list[dict[str, Any]]],
) -> str:
    direct = citation.get("text") or citation.get("content") or citation.get("markdown")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    block_id = citation.get("block") or citation.get("block_id")
    if isinstance(block_id, str) and block_id:
        response = requests.get(
            f"{PAGEINDEX_API_URL}/doc/{doc_id}/block/{block_id}/",
            headers=_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.ok:
            text = response.json().get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

    if doc_id not in page_cache:
        response = requests.get(
            f"{PAGEINDEX_API_URL}/doc/{doc_id}/",
            headers=_headers(),
            params={"type": "ocr", "format": "page"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        page_cache[doc_id] = result if isinstance(result, list) else []
    page_number = citation.get("page") or citation.get("page_index")
    for page in page_cache[doc_id]:
        if str(page.get("page_index")) == str(page_number):
            markdown = page.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                return markdown.strip()
    return ""


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Query cached PageIndex documents and return cited evidence as SearchResult."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0:
        raise ValueError("top_k must be a non-negative integer")
    if top_k == 0:
        return []

    cache = _load_cache()
    usable = {key: value for key, value in cache.items() if value.get("doc_id")}
    if not usable:
        raise RuntimeError("No cached PageIndex document IDs; run upload_documents() first")

    response = requests.post(
        f"{PAGEINDEX_API_URL}/chat/completions",
        headers={**_headers(), "Content-Type": "application/json"},
        json={
            "doc_id": [entry["doc_id"] for entry in usable.values()],
            "messages": [{"role": "user", "content": query.strip()}],
            "stream": False,
            "enable_citations": True,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    citations = _citation_records(response.json())
    by_doc_id = {entry["doc_id"]: (source_id, entry) for source_id, entry in usable.items()}
    by_filename = {entry.get("filename"): (source_id, entry) for source_id, entry in usable.items()}
    page_cache: dict[str, list[dict[str, Any]]] = {}
    results: list[dict] = []
    seen_ids: set[str] = set()

    for citation in citations:
        citation_doc_id = citation.get("doc_id") or citation.get("document_id")
        document_name = citation.get("doc") or citation.get("filename") or citation.get("document")
        source = by_doc_id.get(citation_doc_id) or by_filename.get(document_name)
        if source is None:
            continue
        source_id, entry = source
        doc_id = entry["doc_id"]
        content = _resolve_content(citation, doc_id, page_cache)
        if not content:
            continue
        page = citation.get("page") or citation.get("page_index") or 0
        block = citation.get("block") or citation.get("block_id") or "page"
        result_id = f"pageindex::{source_id}::p{page}::{block}"
        if result_id in seen_ids:
            continue
        seen_ids.add(result_id)
        metadata = dict(entry.get("metadata") or {})
        metadata["chunk_index"] = max(int(page or 1) - 1, 0)
        results.append(
            {
                "id": result_id,
                "content": content,
                "score": 1.0 / (len(results) + 1),
                "metadata": metadata,
                "retrieval_method": "pageindex",
            }
        )
        if len(results) >= top_k:
            break

    validate_search_results(results, top_k=top_k, expected_method="pageindex")
    return results


if __name__ == "__main__":
    upload_documents()
