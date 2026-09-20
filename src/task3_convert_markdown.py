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
    """Convert PDF/DOCX trong landing/legal sang Markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    converter = MarkItDown()

    source_paths = sorted(
        path
        for path in legal_dir.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in {".pdf", ".doc", ".docx"}
    )
    for path in source_paths:
        result = converter.convert(str(path))
        content = result.text_content.strip()
        if not content:
            raise ValueError(f"Converted document is empty: {path}")

        output_path = output_dir / f"{path.stem}.md"
        output_path.write_text(f"{content}\n", encoding="utf-8")
        print(f"Converted: {path.name} -> {output_path.name}")


def convert_news_articles() -> None:
    """Chuẩn hóa JSON trong landing/news sang Markdown có metadata."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    required_fields = {"url", "title", "date_crawled", "content_markdown"}

    for path in sorted(news_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing_fields = required_fields - data.keys()
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"{path} is missing required fields: {missing}")

        values = {field: str(data[field]).strip() for field in required_fields}
        empty_fields = sorted(field for field, value in values.items() if not value)
        if empty_fields:
            empty = ", ".join(empty_fields)
            raise ValueError(f"{path} has empty required fields: {empty}")

        header = (
            f"# {values['title']}\n\n"
            f"**Source:** {values['url']}\n\n"
            f"**Crawled:** {values['date_crawled']}\n\n"
            "---\n\n"
        )
        output_path = output_dir / f"{path.stem}.md"
        output_path.write_text(
            f"{header}{values['content_markdown']}\n",
            encoding="utf-8",
        )
        print(f"Converted: {path.name} -> {output_path.name}")


def convert_all() -> None:
    """Convert toàn bộ dữ liệu landing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
