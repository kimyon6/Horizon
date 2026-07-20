from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from src.models import RSSSourceConfig
from src.scrapers.rss import RSSScraper

_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><title>Test</title>
  <item>
    <guid>entry-1</guid>
    <title>Item 1</title>
    <link>https://example.com/item-1</link>
    <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
    <description>Short summary from feed.</description>
  </item>
</channel></rss>
"""
_SINCE = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

_GOOGLE_STYLE_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><title>Google News</title>
  <item>
    <guid>google-entry-1</guid>
    <title>焦炭价格暂稳运行 首轮提降开启 - 新浪财经</title>
    <link>https://news.google.com/rss/articles/example-token?oc=5</link>
    <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
    <source url="https://finance.sina.com.cn">新浪财经</source>
  </item>
</channel></rss>
"""


def _make_feed_client(feed_text: str) -> AsyncMock:
    response = MagicMock()
    response.text = feed_text
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    return client


def test_rss_ids_are_deterministic() -> None:
    client = _make_feed_client(_FEED)
    source = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    scraper = RSSScraper([source], client)

    first = asyncio.run(scraper.fetch(_SINCE))[0].id
    second = asyncio.run(scraper.fetch(_SINCE))[0].id

    assert first == second
    assert first == "rss:example.com_feed.xml:5e2d5d1e58e94d76"


def _make_registry(name: str, extractor):
    registry = MagicMock()
    registry.get.side_effect = lambda n: extractor if n == name else None
    return registry


def test_content_extractor_replaces_feed_content() -> None:
    client = _make_feed_client(_FEED)
    extractor = AsyncMock()
    extractor.extract.return_value = "Full article text from extractor."

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", content_extractor="my-ext"
    )
    scraper = RSSScraper([source], client, extractors=_make_registry("my-ext", extractor))
    items = asyncio.run(scraper.fetch(_SINCE))

    assert len(items) == 1
    assert items[0].content == "Full article text from extractor."
    extractor.extract.assert_awaited_once_with("https://example.com/item-1", client)


def test_content_extractor_falls_back_on_none() -> None:
    client = _make_feed_client(_FEED)
    extractor = AsyncMock()
    extractor.extract.return_value = None  # extraction failed

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", content_extractor="my-ext"
    )
    scraper = RSSScraper([source], client, extractors=_make_registry("my-ext", extractor))
    items = asyncio.run(scraper.fetch(_SINCE))

    assert len(items) == 1
    assert items[0].content == "Short summary from feed."


def test_unknown_extractor_name_ignored() -> None:
    client = _make_feed_client(_FEED)
    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", content_extractor="nonexistent"
    )
    scraper = RSSScraper([source], client, extractors=_make_registry("other", AsyncMock()))
    items = asyncio.run(scraper.fetch(_SINCE))

    assert len(items) == 1
    assert items[0].content == "Short summary from feed."


def test_source_max_items_caps_feed_results() -> None:
    feed = _FEED.replace(
        "</channel></rss>",
        """
  <item>
    <guid>entry-2</guid>
    <title>Item 2</title>
    <link>https://example.com/item-2</link>
    <pubDate>Fri, 24 Apr 2026 13:00:00 GMT</pubDate>
    <description>Second item.</description>
  </item>
</channel></rss>""",
    )
    client = _make_feed_client(feed)
    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", max_items=1
    )
    scraper = RSSScraper([source], client)

    items = asyncio.run(scraper.fetch(_SINCE))

    assert len(items) == 1
    assert items[0].title == "Item 1"


def test_rss_preserves_publisher_name_and_homepage() -> None:
    client = _make_feed_client(_GOOGLE_STYLE_FEED)
    source = RSSSourceConfig(
        name="黑色原料新闻",
        url="https://news.google.com/rss/search?q=coke",
    )

    item = asyncio.run(RSSScraper([source], client).fetch(_SINCE))[0]

    assert item.metadata["source_name"] == "新浪财经"
    assert item.metadata["source_homepage"] == "https://finance.sina.com.cn"
