"""Daily summary generation — pure programmatic rendering."""

import html
import re
from datetime import timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import quote, urlsplit

from ..models import ContentItem
from ..google_news_urls import is_google_news_url
from .article_text import excerpt_from_feed_content


_CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_ASCII = r"[A-Za-z0-9]"
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#!|])")
_MARKDOWN_BLOCK_START = re.compile(r"(?m)^( {0,3})(>|[-+] |\d+[.)] )")
_URL_SAFE_CHARS = ":/?#[]@!$&'*,;=~%+"


def _escape_markdown(value: object) -> str:
    """Render untrusted text literally while retaining its readable content."""
    escaped = html.escape(str(value), quote=True)
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", escaped)
    return _MARKDOWN_BLOCK_START.sub(r"\1\\\2", escaped)


def _safe_url(value: object) -> Optional[str]:
    """Return an HTML/Markdown-safe HTTP(S) URL, or None for unsafe URLs."""
    raw = str(value).strip()
    if not raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        parsed.port
    except (TypeError, ValueError):
        return None
    encoded = quote(raw, safe=_URL_SAFE_CHARS)
    return html.escape(encoded, quote=True)


def _reader_url(item: ContentItem) -> Optional[str]:
    """Return a phone-friendly URL, never a Google News wrapper link."""
    item_url = str(item.url)
    if not is_google_news_url(item_url):
        return _safe_url(item_url)

    for candidate in (
        item.metadata.get("resolved_url"),
        item.metadata.get("source_homepage"),
    ):
        if candidate and not is_google_news_url(candidate):
            safe = _safe_url(candidate)
            if safe:
                return safe
    return None


def _pangu(text: str) -> str:
    """Insert a space between CJK and ASCII letters/digits (Pangu spacing)."""
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


def is_foreign_news(item: ContentItem, language: str = "zh") -> bool:
    """Return whether a Chinese alert would otherwise expose a foreign headline."""
    return language == "zh" and not re.search(_CJK, str(item.title))


def localized_title(item: ContentItem, language: str = "en") -> str:
    """Choose a safe display title without exposing English in Chinese alerts."""
    if is_foreign_news(item, language):
        translated = str(item.metadata.get("title_zh") or "").strip()
        return translated or "国外新闻（请点击查看英文原文）"
    return str(item.title)


def webhook_item_title(item: ContentItem, language: str = "en") -> str:
    """Build the short title shown by the webhook client."""
    title = localized_title(item, language)
    if is_foreign_news(item, language):
        return f"国外新闻｜{title}"
    return title


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "source": "Source",
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
        "original_title": "Original headline",
        "foreign_title": "Foreign news (AI Chinese translation)",
        "ai_translation": "AI translation (not original text)",
        "market_scope": "Market scope (rule-based check)",
        "ai_analysis": "AI analysis (not original text)",
        "original_source": "Original source",
        "foreign_source": "Foreign original source",
        "ai_background": "AI background (not original text)",
        "ai_tags": "AI tags",
        "original_content": "Original excerpt (publisher text)",
        "translated_content": "News content (AI Chinese translation)",
        "translated_unavailable": "The foreign source is in English. Open the headline link to read it.",
        "original_unavailable": "The source did not provide readable article text; open the headline link to read the original.",
        "selected_items": "From {total} items, {selected} important content pieces were selected",
        "empty_analyzed": "Analyzed {total} items, but none met the importance threshold.",
        "empty_body": (
            "No significant developments today. This might indicate:\n"
            "- A quiet day in your tracked sources\n"
            "- The AI score threshold is too high\n"
            "- Your information sources need expansion\n\n"
            "Consider:\n"
            "1. Lowering the `ai_score_threshold` in config.json\n"
            "2. Adding more diverse information sources\n"
            "3. Checking if the AI model is working correctly\n"
        ),
    },
    "zh": {
        "header": "Horizon 每日速递",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
        "original_title": "原文标题",
        "foreign_title": "国外新闻（AI 中文译题）",
        "ai_translation": "AI 中文译题（非原文）",
        "market_scope": "行情口径（程序核对）",
        "ai_analysis": "AI 解读（非原文）",
        "original_source": "原文来源",
        "foreign_source": "国外原文来源",
        "ai_background": "AI 背景（非原文）",
        "ai_tags": "AI 标签",
        "original_content": "原文内容（媒体原话节选）",
        "translated_content": "新闻内容（AI 中文翻译）",
        "translated_unavailable": "国外新闻原文为英文，暂未生成中文翻译，请点击标题查看原文。",
        "original_unavailable": "新闻源未提供可读取的正文，请点击原文标题查看。",
        "selected_items": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
        "empty_analyzed": "已分析 {total} 条内容，但没有达到重要性阈值的条目。",
        "empty_body": (
            "今日暂无重要动态，可能原因：\n"
            "- 今天关注的信息源较平静\n"
            "- AI 评分阈值设置过高\n"
            "- 信息源种类有待扩充\n\n"
            "建议：\n"
            "1. 在 config.json 中降低 `ai_score_threshold`\n"
            "2. 添加更多多样化的信息源\n"
            "3. 检查 AI 模型是否正常工作\n"
        ),
    },
}


class DailySummarizer:
    """Generates daily Markdown summaries from pre-analyzed content items."""

    def __init__(self):
        pass

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary in Markdown format.

        Items are rendered in score-descending order (already sorted by orchestrator).

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, either "en" or "zh"

        Returns:
            str: Markdown formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        header = (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['selected_items'].format(total=total_fetched, selected=len(items))}\n\n"
            "---\n\n"
        )

        # TOC
        toc_entries = []
        for i, item in enumerate(items):
            _t = webhook_item_title(item, language)
            t = _escape_markdown(_t)
            if language == "zh":
                t = _pangu(t)
            score = item.ai_score or "?"
            toc_entries.append(f"{i + 1}. [{t}](#item-{i + 1}) \u2b50\ufe0f {score}/10")
        toc = "\n".join(toc_entries) + "\n\n---\n\n"

        parts = [self._format_item(item, labels, language, i + 1) for i, item in enumerate(items)]

        return header + toc + "".join(parts)

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        if language == "zh":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 从 {total_fetched} 条内容中筛选出 {len(items)} 条重要资讯。\n\n"
                "下面会按新闻逐条发送详情，你可以只看感兴趣的标题。\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> Selected {len(items)} important items from {total_fetched} fetched items.\n\n"
                "Details will be sent item by item so you can read only the topics you care about.\n\n"
            )

        entries = []
        for i, item in enumerate(items, start=1):
            title = _escape_markdown(webhook_item_title(item, language))
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            url = _reader_url(item)
            title_link = f"[{title}]({url})" if url else title
            entries.append(f"{i}. {title_link} \u2b50\ufe0f {score}/10")

        return header + "\n".join(entries)

    def generate_webhook_item(
        self,
        item: ContentItem,
        language: str,
        index: int,
        total: int,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        prefix = f"第 {index}/{total} 条\n\n" if language == "zh" else f"Item {index}/{total}\n\n"
        return prefix + self._format_item(item, labels, language, index).rstrip("-\n ")

    def _format_item(self, item: ContentItem, labels: dict, language: str, index: int) -> str:
        """Format a single ContentItem into Markdown."""
        foreign_news = is_foreign_news(item, language)
        _title = localized_title(item, language)
        title = _escape_markdown(_title)
        raw_url = str(item.url)
        url = _reader_url(item)
        score = item.ai_score or "?"
        meta = item.metadata
        separator = "：" if language == "zh" else ": "
        original_excerpt = meta.get("original_excerpt") or excerpt_from_feed_content(
            item.title,
            item.content,
        )

        if foreign_news:
            summary = (
                meta.get("detailed_summary_zh")
                or "AI 中文解读暂未生成，请以国外原文来源为准。"
            )
            background = meta.get("background_zh") or ""
            discussion = meta.get("community_discussion_zh") or ""
        else:
            summary = (
                meta.get(f"detailed_summary_{language}")
                or meta.get("detailed_summary")
                or item.ai_summary
                or ""
            )
            background = meta.get(f"background_{language}") or meta.get("background") or ""
            discussion = (
                meta.get(f"community_discussion_{language}")
                or meta.get("community_discussion")
                or ""
            )

        summary = _escape_markdown(summary)
        background = _escape_markdown(background)
        discussion = _escape_markdown(discussion)

        if language == "zh":
            title = _pangu(title)
            summary = _pangu(summary)
            background = _pangu(background)
            discussion = _pangu(discussion)

        # Source line with parts joined by " · ", link appended at end
        source_type = item.source_type.value
        source_parts = [_escape_markdown(source_type)]
        if meta.get("subreddit"):
            source_parts.append(_escape_markdown(f"r/{meta['subreddit']}"))
        if meta.get("feed_name"):
            source_parts.append(_escape_markdown(meta["feed_name"]))
        else:
            source_parts.append(_escape_markdown(item.author or "unknown"))
        if meta.get("source_name") and meta.get("source_name") != meta.get("feed_name"):
            source_parts.append(_escape_markdown(meta["source_name"]))
        if item.published_at:
            if language == "zh":
                published_at = item.published_at
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
                published_at = published_at.astimezone(timezone(timedelta(hours=8)))
                source_parts.append(
                    f"{published_at.month}月{published_at.day}日 "
                    f"{published_at:%H:%M} 北京时间"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " \u00b7 ".join(source_parts)  # ·

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            safe_discussion_url = _safe_url(discussion_url)
            if safe_discussion_url and str(discussion_url) != raw_url:
                source_line += f' · [{labels["discussion"]}]({safe_discussion_url})'

        title_link = f"[{title}]({url})" if url else title

        lines = [
            f'<a id="item-{index}"></a>',
            (
                f"## {labels['foreign_title'] if foreign_news else labels['original_title']}"
                f"{separator}{title_link} \u2b50\ufe0f {score}/10"
            ),  # ⭐️
            "",
        ]

        if foreign_news:
            translated_excerpt = str(meta.get("source_excerpt_zh") or "").strip()
            if translated_excerpt:
                excerpt = _pangu(_escape_markdown(translated_excerpt))
                lines.append(f"**{labels['translated_content']}**{separator}{excerpt}")
            else:
                lines.append(
                    f"**{labels['translated_content']}**{separator}"
                    f"{labels['translated_unavailable']}"
                )
        elif original_excerpt:
            excerpt = _escape_markdown(original_excerpt)
            if language == "zh":
                excerpt = _pangu(excerpt)
            lines.append(f"**{labels['original_content']}**{separator}{excerpt}")
        else:
            lines.append(f"**{labels['original_content']}**{separator}{labels['original_unavailable']}")
        lines.append("")
        source_label = labels["foreign_source"] if foreign_news else labels["original_source"]
        lines.append(f"**{source_label}**{separator}{source_line}")
        lines.append("")

        market_context = meta.get("market_context_zh") if language == "zh" else ""
        if market_context:
            lines.append(
                f"**{labels['market_scope']}**{separator}{_pangu(_escape_markdown(market_context))}"
            )
            lines.append("")

        lines.extend(
            [
                f"**{labels['ai_analysis']}**{separator}{summary}",
            ]
        )

        if background:
            lines.append("")
            lines.append(f"**{labels['ai_background']}**{separator}{background}")

        sources = meta.get("sources") or []
        if sources and not foreign_news:
            reference_items = []
            for source in sources:
                reference_title = html.escape(str(source.get("title", "")), quote=True)
                raw_reference_url = source.get("url", "")
                if is_google_news_url(raw_reference_url):
                    continue
                reference_url = _safe_url(raw_reference_url)
                if reference_url:
                    reference_items.append(f'<li><a href="{reference_url}">{reference_title}</a></li>\n')
                else:
                    reference_items.append(f"<li>{reference_title}</li>\n")
            if reference_items:
                items_html = "".join(reference_items)
                lines += [
                    "",
                    f'<details><summary>{labels["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
                ]

        if discussion:
            lines.append("")
            lines.append(f"**{labels['discussion']}**: {discussion}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines) + "\n\n"

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['empty_analyzed'].format(total=total_fetched)}\n\n"
            + labels["empty_body"]
        )
