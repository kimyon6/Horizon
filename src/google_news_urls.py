"""Resolve Google News wrapper links to the original publisher URL."""

from __future__ import annotations

import base64
import json
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


_BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def is_google_news_url(value: object) -> bool:
    """Return True only for Google News wrapper URLs."""
    try:
        return urlparse(str(value)).hostname == "news.google.com"
    except (TypeError, ValueError):
        return False


def _article_token(source_url: str) -> Optional[str]:
    parsed = urlparse(source_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.hostname != "news.google.com" or len(parts) < 2:
        return None
    if parts[-2] not in {"articles", "read"}:
        return None
    return parts[-1]


def _valid_original_url(value: object) -> Optional[str]:
    raw = str(value).strip()
    try:
        parsed = urlparse(raw)
    except (TypeError, ValueError):
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.hostname == "news.google.com":
        return None
    return raw


def _decode_embedded_url(token: str) -> Optional[str]:
    """Decode older Google tokens that contain the publisher URL directly."""
    try:
        padded = token + "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    except (ValueError, UnicodeError):
        return None
    match = re.search(r"https?://[^\x00-\x20\"']+", decoded)
    return _valid_original_url(match.group(0)) if match else None


def _parse_batch_response(text: str) -> Optional[str]:
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk or chunk.startswith(")]}'"):
            continue
        try:
            rows = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list) or len(row) < 3 or row[1] != "Fbv4je":
                continue
            try:
                decoded = json.loads(row[2])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(decoded, list) and len(decoded) > 1:
                original = _valid_original_url(decoded[1])
                if original:
                    return original
    return None


async def resolve_google_news_url(
    source_url: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[str]:
    """Resolve a Google News RSS/read link, returning None on any failure.

    Google changes this private wrapper protocol occasionally, so callers must
    always have a safe fallback and must never depend on resolution succeeding.
    """
    token = _article_token(source_url)
    if not token:
        return None

    embedded = _decode_embedded_url(token)
    if embedded:
        return embedded

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )

    try:
        signature = None
        timestamp = None
        for path in ("articles", "rss/articles"):
            try:
                response = await client.get(f"https://news.google.com/{path}/{token}")
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            element = BeautifulSoup(response.text, "html.parser").select_one(
                "c-wiz > div[jscontroller]"
            )
            if element:
                signature = element.get("data-n-a-sg")
                timestamp = element.get("data-n-a-ts")
            if signature and timestamp:
                break

        if not signature or not timestamp:
            return None

        timestamp_value: object = int(timestamp) if str(timestamp).isdigit() else timestamp
        request = [
            "garturlreq",
            [
                [
                    "X", "X", ["X", "X"], None, None, 1, 1, "US:en", None,
                    1, None, None, None, None, None, 0, 1,
                ],
                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0,
            ],
            token,
            timestamp_value,
            signature,
        ]
        payload = ["Fbv4je", json.dumps(request, separators=(",", ":"))]
        response = await client.post(
            _BATCH_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "User-Agent": _USER_AGENT,
            },
            data={"f.req": json.dumps([[payload]], separators=(",", ":"))},
        )
        response.raise_for_status()
        return _parse_batch_response(response.text)
    except Exception:
        return None
    finally:
        if owns_client:
            await client.aclose()
