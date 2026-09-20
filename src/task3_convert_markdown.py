"""Task 3 — standardize legal PDFs and crawled JSON as Markdown."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"
GENERATED_MANIFEST = OUTPUT_DIR / "generated_files.json"


def _yaml_value(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _frontmatter(metadata: dict[str, object]) -> str:
    return "\n".join(["---", *(f"{k}: {_yaml_value(v)}" for k, v in metadata.items()), "---", ""])


def _clean_markdown(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def _render_legal() -> dict[Path, str]:
    from markitdown import MarkItDown

    legal_dir = LANDING_DIR / "legal"
    manifest_path = legal_dir / "sources.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Run task1_collect_legal_docs before Task 3")
    sources = json.loads(manifest_path.read_text(encoding="utf-8"))
    converter = MarkItDown()
    rendered: dict[Path, str] = {}
    for source in sources:
        path = legal_dir / source["filename"]
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Checksum mismatch for {path.name}; rerun Task 1")
        body = _clean_markdown(converter.convert(str(path)).text_content)
        if len(body) < 200:
            raise ValueError(f"Converted legal document is too short: {path.name}")
        metadata = {
            "id": source["id"], "title": source["title"], "doc_type": "legal",
            "source": source["source"], "url": source["url"],
            "date_crawled": source["retrieved_at"], "sha256": digest,
        }
        rendered[Path("legal") / f"{source['id']}.md"] = _frontmatter(metadata) + "\n" + body + "\n"
    return rendered


def _render_news() -> dict[Path, str]:
    news_dir = LANDING_DIR / "news"
    files = sorted(path for path in news_dir.glob("*.json") if not path.name.startswith("."))
    if not files:
        raise FileNotFoundError("Run task2_crawl_news before Task 3")
    rendered: dict[Path, str] = {}
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"id", "url", "title", "date_crawled", "content_markdown"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"{path.name} is missing fields: {sorted(missing)}")
        body = _clean_markdown(data["content_markdown"])
        if len(body) < 200:
            raise ValueError(f"Converted article is too short: {path.name}")
        metadata = {
            "id": data["id"], "title": data["title"], "doc_type": "news",
            "source": data["url"].split("/", 3)[2], "url": data["url"],
            "date_crawled": data["date_crawled"],
        }
        rendered[Path("news") / f"{data['id']}.md"] = _frontmatter(metadata) + "\n" + body + "\n"
    return rendered


def convert_legal_docs() -> None:
    rendered = _render_legal()
    for relative, content in rendered.items():
        destination = OUTPUT_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        print(f"Saved: {destination.name} — {len(content)} chars")


def convert_news_articles() -> None:
    rendered = _render_news()
    for relative, content in rendered.items():
        destination = OUTPUT_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        print(f"Saved: {destination.name} — {len(content)} chars")


def convert_all() -> None:
    """Render all inputs first, then update outputs and remove managed stale files."""
    rendered = {**_render_legal(), **_render_news()}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for relative, content in rendered.items():
        destination = OUTPUT_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        print(f"Saved: {relative.as_posix()} — {len(content)} chars")

    previous: set[str] = set()
    if GENERATED_MANIFEST.exists():
        try:
            previous = set(json.loads(GENERATED_MANIFEST.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    current = {path.as_posix() for path in rendered}
    for stale_name in previous - current:
        stale = OUTPUT_DIR / stale_name
        if stale.is_file() and stale.resolve().is_relative_to(OUTPUT_DIR.resolve()):
            stale.unlink()
    GENERATED_MANIFEST.write_text(json.dumps(sorted(current), indent=2), encoding="utf-8")
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
