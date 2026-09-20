"""
Task 3 — Chuẩn hóa dữ liệu sang Markdown.

Hướng dẫn:
    1. Dùng MarkItDown để convert PDF/DOCX.
    2. Đọc JSON và giữ metadata ở đầu file Markdown.
    3. Giữ cấu trúc thư mục legal/ và news/.
    4. Không tạo file rỗng hoặc file trùng khi chạy lại.

Cài đặt:
    Dependency MarkItDown đã được khai báo trong pyproject.toml.
    
-> Hoặc dùng công cụ nào bạn quen khác Markitdown
"""

import json
from pathlib import Path

from markitdown import MarkItDown


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def convert_legal_docs() -> None:
    """Convert every landing policy file while preserving a source URL when known."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    converter = MarkItDown()
    for path in sorted(legal_dir.iterdir() if legal_dir.exists() else []):
        if path.suffix.lower() not in {".pdf", ".doc", ".docx"}:
            continue
        text = converter.convert(str(path)).text_content.strip()
        if not text:
            raise ValueError(f"Conversion produced no text: {path}")
        header = f"# {path.stem.replace('_', ' ')}\n\n**Source:** {path.name}\n\n---\n\n"
        (output_dir / f"{path.stem}.md").write_text(header + text + "\n", encoding="utf-8")


def convert_news_articles() -> None:
    """Convert crawled article JSON into Markdown with auditable metadata."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    required = {"url", "title", "date_crawled", "content_markdown"}
    for path in sorted(news_dir.glob("*.json") if news_dir.exists() else []):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = required - data.keys()
        if missing or not all(str(data[key]).strip() for key in required):
            raise ValueError(f"Invalid article metadata in {path.name}: {sorted(missing)}")
        header = (
            f"# {data['title'].strip()}\n\n**Source:** {data['url'].strip()}\n\n"
            f"**Crawled:** {data['date_crawled'].strip()}\n\n---\n\n"
        )
        content = str(data["content_markdown"]).strip()
        (output_dir / f"{path.stem}.md").write_text(header + content + "\n", encoding="utf-8")


def convert_all() -> None:
    """Convert toàn bộ dữ liệu landing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
