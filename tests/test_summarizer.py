"""Unit tests for daily summary rendering."""

import asyncio
from datetime import datetime, timezone

from src.ai.summarizer import DailySummarizer
from src.models import ContentItem, SourceType


def _run_async(coro):
    return asyncio.run(coro)


def _make_item(idx: int) -> ContentItem:
    item = ContentItem(
        id=f"rss:item-{idx}",
        source_type=SourceType.RSS,
        title=f"Important Item {idx}",
        url=f"https://example.com/items/{idx}",
        content="content",
        author="tester",
        published_at=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = f"Summary for item {idx}."
    item.ai_tags = ["AI", "News"]
    return item


def test_generate_webhook_overview_lists_items_without_full_details():
    summarizer = DailySummarizer()
    items = [_make_item(1), _make_item(2)]

    result = summarizer.generate_webhook_overview(
        items,
        date="2026-04-25",
        total_fetched=10,
        language="en",
    )

    assert "Selected 2 important items from 10 fetched items" in result
    assert "1. [Important Item 1](https://example.com/items/1)" in result
    assert "2. [Important Item 2](https://example.com/items/2)" in result
    assert "Summary for item 1." not in result


def test_generate_webhook_item_renders_single_item_detail():
    summarizer = DailySummarizer()

    result = summarizer.generate_webhook_item(
        _make_item(1),
        language="en",
        index=1,
        total=2,
    )

    assert result.startswith("Item 1/2")
    assert "## Original headline: [Important Item 1](https://example.com/items/1)" in result
    assert "**AI analysis (not original text)**: Summary for item 1." in result
    assert "**Original excerpt (publisher text)**" in result
    assert "**AI tags**" not in result
    assert "#AI" not in result


def test_chinese_alert_keeps_original_headline_and_labels_ai_text() -> None:
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.title = "华泰期货：焦炭首轮提降，价格先抑后扬"
    item.metadata.update(
        {
            "title_zh": "焦炭价格强势反弹",
            "original_excerpt": "昨日双焦主力合约先抑后扬，钢厂开启焦炭首轮提降。",
            "market_context_zh": (
                "“先抑后扬”指期货合约走势，不等于焦炭现货涨价。"
            ),
        }
    )

    result = summarizer.generate_webhook_item(item, "zh", 1, 1)

    assert "## 原文标题：[华泰期货：焦炭首轮提降，价格先抑后扬]" in result
    assert "焦炭价格强势反弹" not in result
    assert "**原文内容（媒体原话节选）**" in result
    assert "昨日双焦主力合约先抑后扬" in result
    assert "**行情口径（程序核对）**" in result
    assert "不等于焦炭现货涨价" in result
    assert "**AI 解读（非原文）**" in result
    assert "**原文来源**" in result
    assert "AI 标签" not in result
    assert result.index("原文内容（媒体原话节选）") < result.index("原文来源")
    assert result.index("原文来源") < result.index("AI 解读（非原文）")


def test_foreign_alert_hides_english_and_separates_translation_from_analysis() -> None:
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.title = "Australia iron ore exports disrupted by cyclone"
    item.content = "Port operations were suspended after a cyclone warning."
    item.metadata.update(
        {
            "title_zh": "澳大利亚铁矿石出口受气旋影响",
            "original_excerpt": "Port operations were suspended after a cyclone warning.",
            "source_excerpt_zh": "气旋预警发布后，港口暂停作业。",
            "detailed_summary_zh": "若停运持续，短期可能扰动中国到港节奏。",
            "feed_name": "Reuters Commodities",
        }
    )

    result = summarizer.generate_webhook_item(item, "zh", 1, 1)

    assert "Australia iron ore exports disrupted by cyclone" not in result
    assert "Port operations were suspended after a cyclone warning." not in result
    assert "## 国外新闻（AI 中文译题）：[澳大利亚铁矿石出口受气旋影响]" in result
    assert "**新闻内容（AI 中文翻译）**：气旋预警发布后，港口暂停作业。" in result
    assert "**国外原文来源**" in result
    assert "Reuters Commodities" in result
    assert "**AI 解读（非原文）**：若停运持续，短期可能扰动中国到港节奏。" in result
    assert result.index("新闻内容（AI 中文翻译）") < result.index("AI 解读（非原文）")


def test_generate_webhook_item_includes_discussion_link_when_distinct():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://news.ycombinator.com/item?id=1"

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "tester · Apr 25, 08:00 · [Discussion](https://news.ycombinator.com/item?id=1)" in result


def test_generate_webhook_item_omits_discussion_link_when_same_as_item_url():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = item.url

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "[Discussion](https://example.com/items/1)" not in result


def test_generate_webhook_item_uses_localized_discussion_label():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://www.reddit.com/r/python/comments/abc123/test/"

    result = summarizer.generate_webhook_item(
        item,
        language="zh",
        index=1,
        total=1,
    )

    assert "[社区讨论](https://www.reddit.com/r/python/comments/abc123/test/)" in result


def test_generate_summary_zh_uses_localized_selection_header_and_numeric_date():
    summarizer = DailySummarizer()
    item = _make_item(1)

    result = _run_async(
        summarizer.generate_summary(
            [item],
            date="2026-04-25",
            total_fetched=10,
            language="zh",
        )
    )

    assert "> 从 10 条内容中筛选出 1 条重要资讯。" in result
    assert "rss · tester · 4月25日 16:00 北京时间" in result
    assert "From 10 items" not in result
    assert "Apr 25, 08:00" not in result


def test_generate_empty_summary_zh_uses_localized_analyzed_line():
    summarizer = DailySummarizer()

    result = _run_async(
        summarizer.generate_summary(
            [],
            date="2026-04-25",
            total_fetched=10,
            language="zh",
        )
    )

    assert "> 已分析 10 条内容，但没有达到重要性阈值的条目。" in result
    assert "Analyzed 10 items" not in result


def test_generate_summary_escapes_untrusted_text_in_all_output_contexts():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.title = '<script>alert("title")</script> [click](javascript:alert(1))'
    item.ai_summary = '<img src=x onerror="alert(1)"> **summary**'
    item.author = '<svg onload="alert(1)">'
    item.ai_tags = ['tag`](javascript:alert(1))']
    item.metadata.update(
        {
            "feed_name": '<b onclick="alert(1)">feed</b>',
            "background": '<iframe src="data:text/html,bad"></iframe>',
            "community_discussion": '[bad](data:text/html,bad)',
            "sources": [{"title": '<img src=x onerror="alert(1)">', "url": "https://example.com/ref"}],
        }
    )

    result = _run_async(summarizer.generate_summary([item], "2026-04-25", 1))

    assert "<script>" not in result
    assert "<img src=x" not in result
    assert "<iframe" not in result
    assert "<b onclick" not in result
    assert "](javascript:" not in result
    assert "](data:text/html" not in result
    assert "&lt;script&gt;" in result
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in result


def test_generate_summary_rejects_unsafe_urls_and_quote_injection():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata.update(
        {
            "discussion_url": 'javascript:alert("discussion")',
            "sources": [
                {"title": 'Quoted "><script>alert(1)</script>', "url": 'https://example.com/\" onmouseover=\"alert(1)'},
                {"title": "JavaScript", "url": "javascript:alert(1)"},
                {"title": "Data", "url": "data:text/html,<script>alert(1)</script>"},
            ],
        }
    )

    result = _run_async(summarizer.generate_summary([item], "2026-04-25", 1))

    assert 'href="https://example.com/%22%20onmouseover=%22alert%281%29"' in result
    assert '<li>JavaScript</li>' in result
    assert '<li>Data</li>' in result
    assert 'href="javascript:' not in result
    assert 'href="data:' not in result
    assert '<script>' not in result


def test_generate_summary_preserves_normal_http_links():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata.update(
        {
            "discussion_url": "https://example.com/discuss?id=1#comments",
            "sources": [{"title": "Useful reference", "url": "https://docs.example.com/path?q=one&lang=en"}],
        }
    )

    result = _run_async(summarizer.generate_summary([item], "2026-04-25", 1))

    assert "[Important Item 1](https://example.com/items/1)" in result
    assert "[Discussion](https://example.com/discuss?id=1#comments)" in result
    assert 'href="https://docs.example.com/path?q=one&amp;lang=en"' in result


def test_google_news_item_uses_resolved_publisher_article_url():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.url = "https://news.google.com/rss/articles/wrapper-token?oc=5"
    item.metadata.update(
        {
            "resolved_url": "https://finance.sina.com.cn/article/123.shtml",
            "source_homepage": "https://finance.sina.com.cn",
        }
    )

    result = summarizer.generate_webhook_item(item, "zh", 1, 1)

    assert "https://finance.sina.com.cn/article/123.shtml" in result
    assert "news.google.com" not in result


def test_google_news_item_falls_back_to_publisher_homepage():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.url = "https://news.google.com/rss/articles/wrapper-token?oc=5"
    item.metadata["source_homepage"] = "https://finance.sina.com.cn"

    result = summarizer.generate_webhook_item(item, "zh", 1, 1)

    assert "[国外新闻（请点击查看英文原文）](https://finance.sina.com.cn)" in result
    assert "Important Item 1" not in result
    assert "news.google.com" not in result


def test_google_news_item_without_fallback_has_no_broken_link():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.url = "https://news.google.com/rss/articles/wrapper-token?oc=5"

    result = summarizer.generate_webhook_item(item, "zh", 1, 1)

    assert "## 国外新闻（AI 中文译题）：国外新闻（请点击查看英文原文）" in result
    assert "Important Item 1" not in result
    assert "news.google.com" not in result


def test_google_news_reference_links_are_omitted() -> None:
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.title = "力拓发布最新铁矿石运营消息"
    item.metadata["sources"] = [
        {
            "title": "Google wrapper",
            "url": "https://news.google.com/stories/wrapper-token",
        },
        {
            "title": "Direct publisher",
            "url": "https://www.riotinto.com/news/release",
        },
    ]

    result = summarizer.generate_webhook_item(item, "zh", 1, 1)

    assert "news.google.com" not in result
    assert "https://www.riotinto.com/news/release" in result
