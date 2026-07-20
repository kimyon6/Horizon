from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from src.google_news_urls import (
    _parse_batch_response,
    is_google_news_url,
    resolve_google_news_url,
)


def _response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.raise_for_status.return_value = None
    return response


def test_is_google_news_url_is_hostname_specific() -> None:
    assert is_google_news_url("https://news.google.com/rss/articles/token?oc=5")
    assert not is_google_news_url("https://finance.sina.com.cn/article.shtml")
    assert not is_google_news_url("https://news.google.com.evil.example/article")


def test_parse_batch_response_extracts_original_article() -> None:
    decoded = json.dumps(
        ["garturlres", "https://finance.sina.com.cn/article/123.shtml"]
    )
    text = ")]}'\n\n" + json.dumps(
        [["wrb.fr", "Fbv4je", decoded], ["di", 1], ["af.httprm", 1]]
    )

    assert _parse_batch_response(text) == "https://finance.sina.com.cn/article/123.shtml"


def test_resolve_google_news_url_uses_google_batch_endpoint() -> None:
    params_html = (
        '<c-wiz><div jscontroller="abc" data-n-a-sg="signature" '
        'data-n-a-ts="123456"></div></c-wiz>'
    )
    decoded = json.dumps(
        ["garturlres", "https://finance.sina.com.cn/article/123.shtml"]
    )
    batch_text = ")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", decoded]])
    client = AsyncMock()
    client.get.return_value = _response(params_html)
    client.post.return_value = _response(batch_text)

    result = asyncio.run(
        resolve_google_news_url(
            "https://news.google.com/rss/articles/current-token?oc=5",
            client,
        )
    )

    assert result == "https://finance.sina.com.cn/article/123.shtml"
    client.get.assert_awaited_once()
    client.post.assert_awaited_once()


def test_resolve_google_news_url_rejects_non_google_input() -> None:
    client = AsyncMock()

    result = asyncio.run(
        resolve_google_news_url("https://finance.sina.com.cn/article.shtml", client)
    )

    assert result is None
    client.get.assert_not_awaited()
