"""Content enrichment using AI (second-pass analysis).

For items that pass the score threshold, this module:
1. Searches the web for relevant context (via DuckDuckGo)
2. Feeds search results + item content to AI to generate grounded background knowledge
"""

import asyncio
import json
import re
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from ddgs import DDGS

from .client import AIClient
from .prompts import (
    CONCEPT_EXTRACTION_SYSTEM, CONCEPT_EXTRACTION_USER,
    CONTENT_ENRICHMENT_SYSTEM, CONTENT_ENRICHMENT_USER,
)
from .utils import parse_json_response
from .grounding import corroborated_years, extract_years, remove_unsupported_years
from ..google_news_urls import is_google_news_url, resolve_google_news_url
from ..models import ContentItem


class ContentEnricher:
    """Enriches high-scoring content items with background knowledge."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client
        self._url_client: Optional[httpx.AsyncClient] = None

    def _get_concurrency(self) -> int:
        """Return the configured enrichment concurrency, clamped to 1 or above."""
        config = getattr(self.client, "config", None)
        concurrency = getattr(config, "enrichment_concurrency", 1)
        return max(concurrency, 1)

    async def enrich_batch(self, items: List[ContentItem]) -> None:
        """Enrich items in-place with background knowledge.

        Args:
            items: Content items to enrich (modified in-place)
        """
        concurrency = self._get_concurrency()
        semaphore = asyncio.Semaphore(concurrency)

        async def _process(item: ContentItem, progress_task) -> None:
            async with semaphore:
                try:
                    await self._enrich_item(item)
                except Exception as e:
                    print(f"Error enriching item {item.id}: {e}, falling back to translation")
                    await self._translate_item(item)
            progress.advance(progress_task)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Enriching", total=len(items))
            coros = [
                _process(item, task) for item in items
            ]
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as url_client:
                self._url_client = url_client
                try:
                    await asyncio.gather(*coros)
                finally:
                    self._url_client = None

    async def _resolve_article_url(self, item: ContentItem) -> None:
        """Store a phone-friendly publisher URL for Google News items."""
        source_url = str(item.url)
        if not is_google_news_url(source_url):
            return
        resolved = await resolve_google_news_url(source_url, self._url_client)
        if resolved:
            item.metadata["google_news_url"] = source_url
            item.metadata["resolved_url"] = resolved

    async def _web_search(self, query: str, max_results: int = 3) -> list:
        """Search the web for context via DuckDuckGo.

        Returns:
            List of dicts with keys: title, url, body
        """
        try:
            # Suppress primp "Impersonate ... does not exist" stderr warning
            stderr = sys.stderr
            sys.stderr = open(os.devnull, "w")
            try:
                ddgs = DDGS()
                results = await asyncio.to_thread(ddgs.text, query, max_results=max_results)
            finally:
                sys.stderr.close()
                sys.stderr = stderr
        except Exception:
            return []

        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "body": r.get("body", "")}
            for r in (results or [])
        ]

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        """Try multiple strategies to extract a JSON object from an AI response.

        Returns the parsed dict, or None if all strategies fail.
        """
        return parse_json_response(response)

    async def _extract_concepts(self, item: ContentItem, content_text: str) -> List[str]:
        """Ask AI to identify concepts that need explanation.

        Args:
            item: Content item
            content_text: Extracted content text

        Returns:
            List of search queries for concepts that need explanation
        """
        user_prompt = CONCEPT_EXTRACTION_USER.format(
            title=item.title,
            summary=item.ai_summary or item.title,
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text[:1000],
        )

        try:
            response = await self.client.complete(
                system=CONCEPT_EXTRACTION_SYSTEM,
                user=user_prompt,
            )
            result = self._parse_json_response(response)
            if result is None:
                return []
            queries = result.get("queries", [])
            return queries[:3]
        except Exception:
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10)
    )
    async def _enrich_item(self, item: ContentItem) -> None:
        """Enrich a single item with background knowledge.

        Steps:
        1. Ask AI which concepts in the news need explanation
        2. Search the web for those concepts
        3. Ask AI to generate background based on search results

        Args:
            item: Content item to enrich (modified in-place via metadata)
        """
        # Resolve Google News wrappers before rendering links or prompting the AI.
        await self._resolve_article_url(item)

        # Extract content text and comments separately
        content_text = ""
        comments_text = ""
        if item.content:
            if "--- Top Comments ---" in item.content:
                main, comments_part = item.content.split("--- Top Comments ---", 1)
                content_text = main.strip()[:4000]
                comments_text = comments_part.strip()[:2000]
            else:
                content_text = item.content[:4000]

        # Step 1: AI identifies concepts to explain
        queries = await self._extract_concepts(item, content_text)

        # Step 2: Verify the exact headline first. Concept searches alone can
        # surface an older, similarly worded quarterly report and misdate a
        # current event.
        published_at = item.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        publication_year = published_at.astimezone(
            timezone(timedelta(hours=8))
        ).year
        verification_results = await self._web_search(
            f'{item.title} {publication_year}',
            max_results=5,
        )
        all_results = list(verification_results)
        web_sections = []
        if verification_results:
            lines = [
                f"- [{r['title']}]({r['url']}): {r['body']}"
                for r in verification_results
            ]
            web_sections.append("**Headline verification:**\n" + "\n".join(lines))

        for query in queries:
            results = await self._web_search(query)
            all_results.extend(results)
            if results:
                lines = [f"- [{r['title']}]({r['url']}): {r['body']}" for r in results]
                web_sections.append(f"**{query}:**\n" + "\n".join(lines))

        # The same page may appear in the headline and concept searches. Count
        # it only once so "two sources agree" really means two independent URLs.
        unique_results = {}
        for result in all_results:
            key = result.get("url") or (result.get("title"), result.get("body"))
            unique_results.setdefault(key, result)
        all_results = list(unique_results.values())
        web_context = "\n\n".join(web_sections) if web_sections else ""

        # Index of available URLs for citation validation
        available_urls = {r["url"]: r["title"] for r in all_results if r.get("url")}

        # Step 3: AI generates background grounded in search results
        user_prompt = CONTENT_ENRICHMENT_USER.format(
            title=item.title,
            url=item.metadata.get("resolved_url") or str(item.url),
            published_at=item.published_at.isoformat(),
            current_date=datetime.now(timezone.utc)
            .astimezone(timezone(timedelta(hours=8)))
            .date()
            .isoformat(),
            summary=item.ai_summary or item.title,
            score=item.ai_score or 0,
            reason=item.ai_reason or "",
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text,
            comments_section=f"\n**Community Comments:**\n{comments_text}" if comments_text else "",
            web_context=web_context or "No web search results available.",
        )

        response = await self.client.complete(
            system=CONTENT_ENRICHMENT_SYSTEM,
            user=user_prompt,
        )

        # Parse JSON response with robust fallback
        result = self._parse_json_response(response)
        if result is None:
            # Gracefully degrade: fall back to a lightweight translation
            # instead of dropping the item untranslated.
            print(f"Warning: could not parse enrichment response for {item.id}, falling back to translation")
            await self._translate_item(item)
            return

        source_years = extract_years(item.title, content_text)
        verified_years = corroborated_years(all_results)
        if source_years:
            supported_years = source_years | verified_years
        elif verified_years:
            # When the feed itself gives no year, prefer the newest independently
            # corroborated match and reject older lookalike quarterly reports.
            supported_years = {max(verified_years)}
        else:
            supported_years = set()
        if verified_years:
            item.metadata["verified_event_years"] = sorted(verified_years)

        # Combine structured sub-fields into per-language detailed_summary
        for lang in ("en", "zh"):
            if result.get(f"title_{lang}"):
                val = result[f"title_{lang}"]
                title = val.get("text") or str(val) if isinstance(val, dict) else str(val)
                item.metadata[f"title_{lang}"] = remove_unsupported_years(
                    title,
                    supported_years,
                )

            parts = []
            for field in ("whats_new", "why_it_matters", "key_details"):
                text = remove_unsupported_years(
                    result.get(f"{field}_{lang}", ""),
                    supported_years,
                )
                if text:
                    parts.append(text)
            if parts:
                item.metadata[f"detailed_summary_{lang}"] = " ".join(parts)

            if result.get(f"background_{lang}"):
                val = result[f"background_{lang}"]
                background = val.get("text") or str(val) if isinstance(val, dict) else str(val)
                item.metadata[f"background_{lang}"] = remove_unsupported_years(
                    background,
                    supported_years,
                )

            if result.get(f"community_discussion_{lang}"):
                val = result[f"community_discussion_{lang}"]
                discussion = val.get("text") or str(val) if isinstance(val, dict) else str(val)
                item.metadata[f"community_discussion_{lang}"] = remove_unsupported_years(
                    discussion,
                    supported_years,
                )

        # Store citation sources — only URLs that actually came from our search results
        if result.get("sources") and available_urls:
            valid = [
                {"url": u, "title": available_urls[u]}
                for u in result["sources"]
                if u in available_urls
            ]
            if valid:
                item.metadata["sources"] = valid

        # Backward-compatible fallback fields (English as default)
        item.metadata["detailed_summary"] = item.metadata.get("detailed_summary_en", "")
        item.metadata["background"] = item.metadata.get("background_en", "")
        item.metadata["community_discussion"] = item.metadata.get("community_discussion_en", "")

    async def _translate_item(self, item: ContentItem) -> None:
        """Lightweight translation fallback: when full enrichment fails, at least
        translate the title and summary to Chinese so the item is not dropped."""
        try:
            response = await self.client.complete(
                system="You are a translator. Translate to Simplified Chinese. Return only valid JSON, no other text.",
                user=(
                    f'Title: {item.title}\n'
                    f'Summary: {item.ai_summary or item.title}\n\n'
                    'Return JSON:\n'
                    '{"title_zh": "<中文标题>", "summary_zh": "<用中文写1-2句摘要>"}'
                ),
            )
            result = self._parse_json_response(response)
            if result:
                supported_years = extract_years(item.title, item.content)
                if result.get("title_zh"):
                    item.metadata["title_zh"] = remove_unsupported_years(
                        result["title_zh"],
                        supported_years,
                    )
                if result.get("summary_zh"):
                    item.metadata["detailed_summary_zh"] = remove_unsupported_years(
                        result["summary_zh"],
                        supported_years,
                    )
        except Exception:
            pass
