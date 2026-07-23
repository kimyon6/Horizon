"""Extract short, verbatim publisher excerpts for transparent alerts."""

import re
from typing import Optional

from bs4 import BeautifulSoup


_ARTICLE_SELECTORS = (
    "article",
    "[itemprop='articleBody']",
    "#artibody",
    "#article_content",
    ".article-content",
    ".article_content",
    ".article-body",
    ".post_body",
    ".post-content",
    ".news-content",
    "main",
)
_NOISE = re.compile(
    r"责任编辑|免责声明|风险提示|打开.{0,8}APP|扫码|相关阅读|"
    r"未经授权|版权归|投资有风险|本文仅代表|举报|广告"
)


def _clean_text(value: object) -> str:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_article_text(html: str) -> str:
    """Extract likely article paragraphs from a publisher HTML page."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select("script, style, nav, footer, header, aside, form, noscript"):
        element.decompose()

    container = None
    for selector in _ARTICLE_SELECTORS:
        candidate = soup.select_one(selector)
        if candidate and len(candidate.get_text(" ", strip=True)) >= 80:
            container = candidate
            break
    if container is None:
        container = soup.body or soup

    paragraphs = []
    seen = set()
    for paragraph in container.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if len(text) < 18 or _NOISE.search(text) or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)

    if paragraphs:
        return "\n".join(paragraphs)[:4000].strip()

    fallback = _clean_text(container.get_text(" ", strip=True))
    return fallback[:4000] if len(fallback) >= 80 else ""


def excerpt_from_feed_content(
    title: object,
    content: object,
    *,
    limit: int = 360,
) -> Optional[str]:
    """Return a useful source excerpt, rejecting title-only RSS boilerplate."""
    raw = str(content or "").split("--- Top Comments ---", 1)[0]
    raw = raw.split("--- From ", 1)[0]
    if not raw.strip():
        return None

    text = _clean_text(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True))
    title_text = _clean_text(title)
    normalized_text = re.sub(r"\W+", "", text).lower()
    normalized_title = re.sub(r"\W+", "", title_text).lower()

    if not text:
        return None
    if normalized_title and normalized_title in normalized_text:
        remainder = normalized_text.replace(normalized_title, "", 1)
        if len(remainder) < 24:
            return None
    if len(text) < 30:
        return None

    if len(text) > limit:
        text = text[:limit].rstrip("，,；;：:。.!！？? ") + "……"
    return text
