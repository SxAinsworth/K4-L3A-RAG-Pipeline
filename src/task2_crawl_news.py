"""Task 2 - crawl public university training-regulation pages.

Each source is stored as one deterministic JSON file in ``data/landing/news``.
Running the module again overwrites the same five files instead of creating
timestamped duplicates.
"""

import asyncio
import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://thanhnien.ntu.edu.vn/tin-tuc/ban-hanh-dao-tao-trinh-do-dai-hoc-cua-truong-dai-hoc-nha-trang-ap-dung-tu-nam-hoc",
    "https://tuyensinh.dainam.edu.vn/vi/tin-tuc/quy-dinh-dao-tao-dai-hoc-va-cao-dang-he-chinh-quy-theo-hoc-che-tin-chi",
    "https://staff.hnue.edu.vn/Daotao/DaotaoDaihoc/QuychedaotaoDaihoc.aspx",
    "https://pdt.iuh.edu.vn/quy-che-dao-tao",
    "https://vhub.vlu.edu.vn/quy-che-dao-tao",
]

# These pages use different CMS templates. Specific selectors keep menus,
# footers and unrelated news out of the corpus. Generic fallbacks allow the
# function to remain useful if a template is changed later.
CONTENT_SELECTORS = {
    "thanhnien.ntu.edu.vn": ("div.details",),
    "tuyensinh.dainam.edu.vn": ("div.content.new-content",),
    "staff.hnue.edu.vn": ("#dnn_ctr1710_HtmlModule_lblContent",),
    "pdt.iuh.edu.vn": ("article",),
    "vhub.vlu.edu.vn": ("div.regu-panel",),
}
TITLE_SELECTORS = {
    # IUH's og:title is the generic department name rather than article title.
    "pdt.iuh.edu.vn": "article h2",
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AcademicCorpusCollector/1.0; "
        "+https://github.com/)"
    ),
    "Accept-Language": "vi,en;q=0.8",
}


def _download_html(url: str) -> str:
    """Download a public HTML page, with a narrow fallback for IUH's TLS chain."""
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=45)
    except requests.exceptions.SSLError:
        # The IUH server currently omits an intermediate certificate that the
        # Python CA bundle needs. Restrict this fallback to that known host.
        if urlparse(url).hostname != "pdt.iuh.edu.vn":
            raise
        warnings.warn(
            "IUH certificate chain could not be verified; retrying this public "
            "read-only page without certificate verification.",
            RuntimeWarning,
            stacklevel=2,
        )
        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore", urllib3.exceptions.InsecureRequestWarning
            )
            response = requests.get(
                url, headers=REQUEST_HEADERS, timeout=45, verify=False
            )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def _page_title(soup: BeautifulSoup, url: str, content_node=None) -> str:
    site_heading = soup.select_one(
        TITLE_SELECTORS.get(urlparse(url).hostname or "", "__no_match__")
    )
    if site_heading and site_heading.get_text(" ", strip=True):
        return site_heading.get_text(" ", strip=True)
    for selector, attribute in (
        ("meta[property='og:title']", "content"),
        ("meta[name='twitter:title']", "content"),
    ):
        tag = soup.select_one(selector)
        if tag and tag.get(attribute):
            return str(tag[attribute]).strip()
    heading = soup.find("h1")
    if heading and heading.get_text(" ", strip=True):
        return heading.get_text(" ", strip=True)
    if content_node is not None:
        heading = content_node.find(["h1", "h2"])
        if heading and heading.get_text(" ", strip=True):
            return heading.get_text(" ", strip=True)
    if soup.title and soup.title.get_text(" ", strip=True):
        return soup.title.get_text(" ", strip=True)
    return urlparse(url).path.rsplit("/", 1)[-1] or url


def _content_node(soup: BeautifulSoup, url: str):
    host = urlparse(url).hostname or ""
    selectors = CONTENT_SELECTORS.get(host, ()) + (
        "article",
        "main",
        "[role='main']",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if node and len(node.get_text(" ", strip=True)) >= 200:
            return node
    return soup.body


def _clean_markdown(node, url: str) -> str:
    # Work on a copy because cleanup mutates the tree.
    fragment = BeautifulSoup(str(node), "lxml")
    for tag in fragment.select(
        "script, style, noscript, iframe, form, nav, footer, header, aside, "
        ".social-share, .related-news, .breadcrumb"
    ):
        tag.decompose()
    for link in fragment.find_all("a", href=True):
        link["href"] = urljoin(url, link["href"])

    markdown = html_to_markdown(
        str(fragment),
        heading_style="ATX",
        bullets="-",
        strip=["img"],
    )
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    if len(markdown) < 200:
        raise ValueError(f"Extracted content is too short ({len(markdown)} chars)")
    return markdown


async def crawl_article(url: str) -> dict:
    """Fetch one public page and return the required landing-data schema."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid public URL: {url!r}")

    html = await asyncio.to_thread(_download_html, url)
    soup = BeautifulSoup(html, "lxml")
    node = _content_node(soup, url)
    if node is None:
        raise ValueError("Page has no HTML body to extract")

    return {
        "url": url,
        "title": _page_title(soup, url, node),
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": _clean_markdown(node, url),
    }


async def crawl_all() -> None:
    """Crawl all configured pages and save one stable JSON file per URL."""
    if len(ARTICLE_URLS) < 5:
        raise ValueError("ARTICLE_URLS must contain at least five public URLs")
    if len(ARTICLE_URLS) != len(set(ARTICLE_URLS)):
        raise ValueError("ARTICLE_URLS contains duplicate URLs")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for index, url in enumerate(ARTICLE_URLS, 1):
        try:
            article = await crawl_article(url)
            output = DATA_DIR / f"article_{index:02d}.json"
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"Saved: {output} "
                f"({len(article['content_markdown'])} content chars)"
            )
        except Exception as error:  # keep collecting other independent sources
            failures.append(f"{url}: {error}")
            print(f"Failed: {url} - {error}")

    if failures:
        raise RuntimeError("Crawl failed for:\n- " + "\n- ".join(failures))


if __name__ == "__main__":
    asyncio.run(crawl_all())
