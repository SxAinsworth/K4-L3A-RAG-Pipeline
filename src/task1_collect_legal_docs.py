"""Task 1 — collect public scholarship policy documents."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
MANIFEST_PATH = DATA_DIR / "sources.json"
TIMEZONE = timezone(timedelta(hours=7))

LEGAL_SOURCES = [
    {
        "id": "hust-scholarship-regulation-2018",
        "filename": "hust_scholarship_regulation_2018.pdf",
        "title": "Quy định xét cấp học bổng cho sinh viên Đại học Bách khoa Hà Nội",
        "source": "Đại học Bách khoa Hà Nội",
        "url": "https://hust.edu.vn/uploads/sys/sinh-vien/2019/03/20190301-dhbk-ha-noi-hoc-bong.375663.15135.pdf",
    },
    {
        "id": "hust-phd-scholarship-regulation-2026",
        "filename": "hust_phd_scholarship_regulation_2026.pdf",
        "title": "Quy định học bổng đối với nghiên cứu sinh tại Đại học Bách khoa Hà Nội",
        "source": "Đại học Bách khoa Hà Nội",
        "url": "https://sdh.hust.edu.vn/Upload/19/Files/Quyche/2026/Quyet_dinh_hoc_bong_NCS.pdf",
    },
    {
        "id": "hunre-scholarship-and-student-aid-regulation-2025",
        "filename": "hunre_scholarship_and_student_aid_regulation_2025.pdf",
        "title": "Quy định học bổng khuyến khích học tập, trợ cấp xã hội và hỗ trợ chi phí học tập",
        "source": "Trường Đại học Tài nguyên và Môi trường Hà Nội",
        "url": "https://hunre.edu.vn/download/news/2025/07/04/142718_1872--%3Dpl__30062025103244_signed.pdf",
    },
]


def setup_directory() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def _is_pdf(content: bytes, content_type: str) -> bool:
    return content.startswith(b"%PDF-") and (
        "pdf" in content_type.lower() or "octet-stream" in content_type.lower()
    )


def _load_previous_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def download_documents() -> None:
    """Download all sources, validate them, then atomically update the corpus."""
    setup_directory()
    previous = _load_previous_manifest()
    previous_by_id = {item.get("id"): item for item in previous}
    now = datetime.now(TIMEZONE).isoformat(timespec="seconds")
    headers = {"User-Agent": "K4-L3A-RAG-Pipeline/1.0 (educational corpus)"}
    downloads: list[tuple[dict, bytes]] = []

    # Download and validate everything before mutating files or the manifest.
    for source in LEGAL_SOURCES:
        response = requests.get(source["url"], headers=headers, timeout=60)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        content = response.content
        if not _is_pdf(content, content_type):
            raise ValueError(f"Expected PDF for {source['id']}, got {content_type!r}")
        if len(content) <= 1024:
            raise ValueError(f"Downloaded file is unexpectedly small: {source['id']}")
        downloads.append((source, content))

    manifest: list[dict[str, str | int]] = []
    for source, content in downloads:
        digest = hashlib.sha256(content).hexdigest()
        previous_item = previous_by_id.get(source["id"], {})
        retrieved_at = (
            previous_item.get("retrieved_at")
            if previous_item.get("sha256") == digest
            else now
        )
        destination = DATA_DIR / source["filename"]
        if not destination.exists() or destination.read_bytes() != content:
            destination.write_bytes(content)
        manifest.append(
            {
                **source,
                "retrieved_at": retrieved_at,
                "content_type": "application/pdf",
                "size_bytes": len(content),
                "sha256": digest,
            }
        )
        print(f"Saved: {destination.name} ({len(content)} bytes)")

    # Remove only files previously managed by this manifest and no longer selected.
    expected = {item["filename"] for item in LEGAL_SOURCES}
    for item in previous:
        stale_name = item.get("filename")
        if stale_name and stale_name not in expected:
            stale_path = DATA_DIR / stale_name
            if stale_path.is_file() and stale_path.parent == DATA_DIR:
                stale_path.unlink()

    temporary = MANIFEST_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(MANIFEST_PATH)
    print(f"Saved provenance: {MANIFEST_PATH}")


if __name__ == "__main__":
    download_documents()
