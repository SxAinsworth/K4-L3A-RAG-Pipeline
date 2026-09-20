"""Task 2 — crawl public scholarship articles into reproducible JSON files."""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests
from bs4 import BeautifulSoup


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
MANIFEST_PATH = DATA_DIR / ".sources.json"
LEGACY_MANIFEST_PATH = DATA_DIR / "sources.json"
TIMEZONE = timezone(timedelta(hours=7))

ARTICLE_SOURCES = [
    {"id": "ou-need-based-scholarship", "url": "https://ou.edu.vn/hocbong/hbvk/"},
    {"id": "ou-back-to-school-scholarship", "url": "https://ou.edu.vn/hocbong/hbtsdtrg/"},
    {"id": "ou-merit-scholarship", "url": "https://ou.edu.vn/hocbong/hbkhhtdhcq/"},
    {
        "id": "ou-need-based-application-2025-2026",
        "url": "https://ou.edu.vn/tin_tuc/thong-bao-ve-viec-tiep-nhan-ho-so-xet-cap-hoc-bong-vuot-kho-hoc-tap-hoc-ky-2-nam-hoc-2025-2026/",
    },
    {
        "id": "ou-scholarship-application-portal",
        "url": "https://ou.edu.vn/hocbong/xet-tructuyen/",
    },
]
ARTICLE_URLS = [item["url"] for item in ARTICLE_SOURCES]


class _MarkdownExtractor(HTMLParser):
    """Render an already-scoped article fragment as lightweight Markdown."""

    BLOCK_TAGS = {"p", "div", "section", "article", "main", "tr", "table"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCK_TAGS or tag == "br":
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.BLOCK_TAGS or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text + " ")

    def result(self) -> str:
        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in "".join(self.parts).splitlines()
        ]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(x for x in lines if x)).strip()


def _without_accents(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFD", value)
        if unicodedata.category(character) != "Mn"
    )


def _trim_related_content(markdown: str) -> str:
    """Stop at a related-news heading that belongs to the surrounding page."""
    kept: list[str] = []
    for line in markdown.splitlines():
        normalized = _without_accents(line).upper().strip("# ")
        if normalized == "TIN LIEN QUAN":
            break
        kept.append(line)
    return "\n".join(kept).strip()


def _extract_article(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one('meta[property="og:title"]')
    title = (title_node.get("content", "").strip() if title_node else "")
    if not title:
        heading = soup.find("h1")
        title = heading.get_text(" ", strip=True) if heading else "Không có tiêu đề"

    selectors = [
        "[itemprop='articleBody']",
        ".entry-content",
        ".post-content",
        ".td-post-content",
        "article",
        "main",
        ".container-wrap",
        ".main-content",
    ]
    root = next((soup.select_one(selector) for selector in selectors if soup.select_one(selector)), None)
    if root is None:
        heading = soup.find("h1")
        if heading is not None:
            root = next(
                (
                    parent
                    for parent in heading.parents
                    if parent.name not in {"body", "html"}
                    and len(parent.get_text(" ", strip=True)) >= 200
                ),
                None,
            )
    if root is None:
        raise ValueError("Could not locate the article body")
    for selector in (
        "script, style, nav, header, footer, aside, form, svg",
        ".related-posts, .post-related, .td_block_related_posts, .sharedaddy",
        ".social-share, .comments, .comment-respond, .author-box, .breadcrumbs",
    ):
        for node in root.select(selector):
            node.decompose()
    parser = _MarkdownExtractor()
    parser.feed(str(root))
    return title, _trim_related_content(parser.result())


def _crawl_article_sync(source: dict[str, str]) -> dict[str, str]:
    response = requests.get(
        source["url"],
        headers={"User-Agent": "K4-L3A-RAG-Pipeline/1.0 (educational corpus)"},
        timeout=60,
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        raise ValueError(f"Expected HTML from {source['url']}, got {content_type!r}")
    # These official OU pages declare UTF-8 in their HTML. Decoding strictly
    # avoids apparent-encoding guesses that turn Vietnamese into mojibake.
    html = response.content.decode("utf-8")
    title, markdown = _extract_article(html)
    if len(markdown) < 200:
        raise ValueError(f"Article too short ({len(markdown)} chars): {source['url']}")
    return {"id": source["id"], "url": source["url"], "title": title, "content_markdown": markdown}


async def crawl_article(url: str) -> dict[str, str]:
    """Compatibility interface required by the assignment."""
    source = next((item for item in ARTICLE_SOURCES if item["url"] == url), None)
    if source is None:
        raise ValueError(f"URL is not declared in ARTICLE_SOURCES: {url}")
    return await asyncio.to_thread(_crawl_article_sync, source)


async def crawl_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TIMEZONE).isoformat(timespec="seconds")
    pending: list[tuple[Path, dict[str, str]]] = []
    failures: list[str] = []

    for source in ARTICLE_SOURCES:
        output = DATA_DIR / f"{source['id']}.json"
        try:
            article = await crawl_article(source["url"])
            old = {}
            if output.exists():
                try:
                    old = json.loads(output.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
            unchanged = (
                old.get("url") == article["url"]
                and old.get("title") == article["title"]
                and old.get("content_markdown") == article["content_markdown"]
            )
            article["date_crawled"] = old.get("date_crawled", now) if unchanged else now
            pending.append((output, article))
        except Exception as error:
            failures.append(f"{source['url']}: {error}")
    if failures:
        raise RuntimeError("Could not crawl all sources:\n" + "\n".join(failures))

    for output, article in pending:
        output.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {output.name} — {len(article['content_markdown'])} chars")

    expected = {output.name for output, _ in pending}
    previous_files: set[str] = set()
    if MANIFEST_PATH.exists():
        try:
            previous_files = set(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    previous_files.update(path.name for path in DATA_DIR.glob("article_*.json"))
    for stale_name in previous_files - expected:
        stale = DATA_DIR / stale_name
        if stale.is_file() and stale.parent == DATA_DIR:
            stale.unlink()
    MANIFEST_PATH.write_text(json.dumps(sorted(expected), indent=2), encoding="utf-8")
    if LEGACY_MANIFEST_PATH.is_file():
        LEGACY_MANIFEST_PATH.unlink()


if __name__ == "__main__":
    asyncio.run(crawl_all())
