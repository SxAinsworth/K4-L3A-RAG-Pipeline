"""Task 3 - standardize legal documents and crawled pages as Markdown."""

import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"
LEGAL_EXTENSIONS = {".pdf", ".doc", ".docx"}
NEWS_FIELDS = ("url", "title", "date_crawled", "content_markdown")
OCR_CACHE_DIR = LANDING_DIR.parent / "_tmp_pdf"


def _write_nonempty(path: Path, content: str) -> None:
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        raise ValueError(f"Refusing to write empty output: {path}")
    path.write_text(normalized + "\n", encoding="utf-8")


def _safe_stem(stem: str) -> str:
    """Create a readable, stable ASCII filename for standardized output."""
    value = unicodedata.normalize("NFKD", stem)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("Đ", "D").replace("đ", "d")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value or "document"


def _find_tesseract() -> Path:
    configured = shutil.which("tesseract")
    candidates = [
        Path(configured) if configured else None,
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise RuntimeError(
        "This PDF is image-only and needs Tesseract OCR. Install Tesseract "
        "with Vietnamese language data, then run this command again."
    )


def _ocr_pdf(source: Path) -> str:
    """OCR an image-only Vietnamese PDF, keeping temporary images out of git."""
    import pdfplumber

    tesseract = _find_tesseract()
    custom_tessdata = OCR_CACHE_DIR / "tessdata"
    tessdata_args: list[str] = []
    if (custom_tessdata / "vie.traineddata").is_file():
        tessdata_args = ["--tessdata-dir", str(custom_tessdata.resolve())]

    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pages: list[str] = []
    with tempfile.TemporaryDirectory(dir=OCR_CACHE_DIR) as temporary:
        temporary_dir = Path(temporary)
        with pdfplumber.open(source) as pdf:
            for page_number, page in enumerate(pdf.pages, 1):
                image_path = temporary_dir / f"page-{page_number:03d}.png"
                page.to_image(resolution=220, antialias=True).save(image_path)
                command = [
                    str(tesseract),
                    str(image_path),
                    "stdout",
                    *tessdata_args,
                    "-l",
                    "vie+eng",
                    "--psm",
                    "3",
                ]
                result = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                text = result.stdout.strip()
                if text:
                    pages.append(f"## Page {page_number}\n\n{text}")
                print(f"OCR: {source.name} - page {page_number}/{len(pdf.pages)}")
    return "\n\n".join(pages)


def convert_legal_docs() -> None:
    """Convert each PDF/DOC/DOCX into ``standardized/legal/*.md``."""
    from markitdown import MarkItDown

    source_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in LEGAL_EXTENSIONS
    )
    if not sources:
        raise FileNotFoundError(f"No legal documents found in {source_dir}")

    converter = MarkItDown()
    output_names: set[str] = set()
    for source in sources:
        output_name = f"{_safe_stem(source.stem)}.md"
        if output_name.casefold() in output_names:
            raise ValueError(
                f"Standardized filename collision for {source.name}: {output_name}"
            )
        output_names.add(output_name.casefold())

        result = converter.convert(str(source))
        content = (result.text_content or "").strip()
        if len(content) < 200 and source.suffix.lower() == ".pdf":
            print(f"Image-only PDF detected; starting OCR: {source.name}")
            content = _ocr_pdf(source).strip()
        if len(content) < 200:
            raise ValueError(
                f"Conversion of {source.name} produced only {len(content)} chars"
            )
        output = output_dir / output_name
        _write_nonempty(output, content)
        print(f"Converted: {source.name} -> {output.name} ({len(content)} chars)")


def convert_news_articles() -> None:
    """Convert landing JSON files while preserving required source metadata."""
    source_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(
        path
        for path in source_dir.glob("*.json")
        if path.is_file() and not path.name.startswith(".")
    )
    if not sources:
        raise FileNotFoundError(f"No news/article JSON files found in {source_dir}")

    for source in sources:
        data = json.loads(source.read_text(encoding="utf-8"))
        missing = [
            field
            for field in NEWS_FIELDS
            if not isinstance(data.get(field), str) or not data[field].strip()
        ]
        if missing:
            raise ValueError(f"{source.name} has missing/empty fields: {missing}")

        header = (
            f"# {data['title'].strip()}\n\n"
            f"- **URL:** {data['url'].strip()}\n"
            f"- **Date crawled:** {data['date_crawled'].strip()}\n"
            f"- **Document type:** public article/page\n\n"
            "---\n\n"
        )
        output = output_dir / f"{source.stem}.md"
        _write_nonempty(output, header + data["content_markdown"])
        print(f"Converted: {source.name} -> {output.name}")


def convert_all() -> None:
    """Convert all landing data while preserving the legal/news structure."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
