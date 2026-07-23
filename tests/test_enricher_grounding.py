import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from src.ai.enricher import ContentEnricher
from src.models import ContentItem, SourceType


def test_enricher_verifies_headline_and_removes_unsupported_old_year(monkeypatch) -> None:
    result = {
        "title_en": "Vale Q2 output beats expectations",
        "title_zh": "淡水河谷二季度产量超预期",
        "whats_new_en": "Vale reported 2025 second-quarter output of 84.26 Mt.",
        "whats_new_zh": "淡水河谷公布2025年第二季度铁矿石产量8426万吨。",
        "why_it_matters_en": "The supply signal matters to steel mills.",
        "why_it_matters_zh": "该供应信号会影响钢厂采购预期。",
        "key_details_en": "Two current reports identify this as 2026 data.",
        "key_details_zh": "两个最新来源确认这是2026年数据。",
        "background_en": "Vale is a major producer.",
        "background_zh": "淡水河谷是主要铁矿石生产商。",
        "community_discussion_en": "",
        "community_discussion_zh": "",
        "sources": [],
    }

    async def complete(**kwargs):
        return json.dumps(result, ensure_ascii=False)

    item = ContentItem(
        id="rss:vale:q2",
        source_type=SourceType.RSS,
        title="淡水河谷二季度铁矿石产量8426万吨超预期",
        url="https://example.com/vale",
        content="淡水河谷二季度铁矿石产量报8426万吨，高于市场预期。",
        published_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = item.title
    item.ai_reason = "重要供应数据"
    enricher = ContentEnricher(SimpleNamespace(complete=complete))
    queries = []

    async def no_resolve(_item):
        return None

    async def no_concepts(_item, _content):
        return []

    async def search(query, max_results=3):
        queries.append((query, max_results))
        return [
            {
                "title": "淡水河谷2026年第二季度产销量报告",
                "url": "https://example.com/a",
                "body": "2026年第二季度铁矿石产量8426万吨。",
            },
            {
                "title": "淡水河谷第二季度产量同比增长",
                "url": "https://example.com/b",
                "body": "公司发布2026年第二季度报告。",
            },
        ]

    monkeypatch.setattr(enricher, "_resolve_article_url", no_resolve)
    monkeypatch.setattr(enricher, "_extract_concepts", no_concepts)
    monkeypatch.setattr(enricher, "_web_search", search)

    asyncio.run(enricher._enrich_item(item))

    assert queries == [(f"{item.title} 2026", 5)]
    assert "2025" not in item.metadata["detailed_summary_zh"]
    assert "第二季度铁矿石产量8426万吨" in item.metadata["detailed_summary_zh"]
    assert "2026年数据" in item.metadata["detailed_summary_zh"]
    assert item.metadata["verified_event_years"] == [2026]
