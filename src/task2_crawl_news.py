"""
Task 2 — Crawl bài viết/thông báo.

Hướng dẫn:
    1. Điền tối thiểu 5 URL công khai vào ARTICLE_URLS.
    2. Crawl từng URL bằng Crawl4AI.
    3. Lưu mỗi bài thành một JSON trong data/landing/news/.
    4. Giữ đủ url, title, date_crawled và content_markdown.

Cài browser trước khi chạy:
    python -m playwright install chromium
    
-> Dùng Firecrawl or bất cứ công cụ nào bạn quen    
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://hotro.ueh.edu.vn/bai-viet/hoc-bong-khuyen-khich-hoc-tap-76?utm_source=chatgpt.com",
    "https://hotro.ueh.edu.vn/bai-viet/hoc-bong-ho-tro-hoc-tap-77?utm_source=chatgpt.com",
    "https://hotro.ueh.edu.vn/bai-viet/dang-ky-hoc-phan-281?utm_source=chatgpt.com",
    "https://hotro.ueh.edu.vn/bai-viet/dong-hoc-phi-35?utm_source=chatgpt.com",
    "https://hotro.ueh.edu.vn/bai-viet/mien-giam-hoc-phi-1867?utm_source=chatgpt.com",
]


async def crawl_article(url: str) -> dict:
    """Crawl một URL và trả về dữ liệu bài viết theo landing schema."""
    run_config = CrawlerRunConfig(
        page_timeout=90_000,
        max_retries=2,
        verbose=False,
    )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=run_config)

    if not result.success:
        reason = result.error_message or f"HTTP status {result.status_code}"
        raise RuntimeError(f"Crawl failed: {reason}")

    markdown_result = result.markdown
    content_markdown = (
        markdown_result.raw_markdown
        if hasattr(markdown_result, "raw_markdown")
        else str(markdown_result or "")
    ).strip()
    if not content_markdown:
        raise ValueError("Crawled page has no Markdown content")

    metadata = result.metadata or {}
    markdown_title = next(
        (
            line.removeprefix("# ").strip()
            for line in content_markdown.splitlines()
            if line.startswith("# ")
        ),
        "",
    )
    title = markdown_title or str(metadata.get("title") or "Unknown").strip()
    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": content_markdown,
    }


async def crawl_all() -> None:
    """Crawl và lưu từng bài thành một file JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for index, url in enumerate(ARTICLE_URLS, 1):
        try:
            article = await crawl_article(url)
            output = DATA_DIR / f"article_{index:02d}.json"
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved: {output}")
        except Exception as error:
            print(f"Failed: {url} — {error}")


if __name__ == "__main__":
    asyncio.run(crawl_all())
