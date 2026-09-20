"""
Task 1 — Thu thập tài liệu chính sách/quy định.

Hướng dẫn:
    1. Chọn chủ đề của nhóm.
    2. Tìm tối thiểu 3 tài liệu PDF/DOCX từ nguồn công khai.
    3. Lưu file gốc vào data/landing/legal/.
    4. Đặt tên không dấu và thể hiện đúng nội dung.

Ví dụ tài liệu: học phí, học bổng, ký túc xá, quy trình đăng ký.
Nếu website chặn crawler, hãy chọn nguồn công khai khác; không vượt WAF.
"""

from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
SOURCE_MANIFEST = DATA_DIR.parent / "SOURCES.md"
LEGAL_EXTENSIONS = {".pdf", ".doc", ".docx"}


def setup_directory() -> None:
    """Tạo thư mục lưu tài liệu gốc."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def download_documents() -> None:
    """Validate the legal documents that were downloaded into the landing area.

    The group supplied these files manually, so this step deliberately does not
    redownload or overwrite them. Public origin URLs are recorded in SOURCES.md.
    """
    documents = sorted(
        path
        for path in DATA_DIR.iterdir()
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() in LEGAL_EXTENSIONS
    )
    if len(documents) < 3:
        raise ValueError(
            f"Expected at least 3 legal documents in {DATA_DIR}, found {len(documents)}"
        )
    too_small = [path.name for path in documents if path.stat().st_size <= 1024]
    if too_small:
        raise ValueError(f"Legal documents look empty or incomplete: {too_small}")
    if not SOURCE_MANIFEST.is_file():
        raise FileNotFoundError(f"Missing source manifest: {SOURCE_MANIFEST}")

    for path in documents:
        print(f"Ready: {path.name} ({path.stat().st_size:,} bytes)")
    print(f"Sources: {SOURCE_MANIFEST}")


if __name__ == "__main__":
    setup_directory()
    download_documents()
