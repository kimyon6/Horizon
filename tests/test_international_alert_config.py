import json
from pathlib import Path

from src.models import Config


def test_daily_github_config_contains_only_steel_business_sources() -> None:
    path = Path("data/config.github.json")
    config = Config.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert config.sources.github == []
    categories = {feed.category for feed in config.sources.rss if feed.enabled}
    assert "wellness-business" not in categories
    assert "ai-business" not in categories
    assert set(config.filtering.category_groups) == {
        "upstream",
        "international",
        "steel",
        "macro",
    }
    assert config.filtering.max_items == 14
    assert config.filtering.current_day_only is True


def test_realtime_steel_alert_config_is_valid_and_strict() -> None:
    path = Path("data/config.international-alerts.github.json")
    config = Config.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert config.ai.languages == ["zh"]
    assert config.filtering.ai_score_threshold == 8.0
    assert config.filtering.max_items == 6
    assert config.filtering.time_window_hours == 24
    assert config.filtering.current_day_only is True
    assert config.filtering.seen_mark_processed is True
    assert config.filtering.seen_state_filename == "international-alert-seen.json"
    assert config.webhook is not None
    assert config.webhook.notify_when_empty is False

    enabled_feeds = [feed for feed in config.sources.rss if feed.enabled]
    categories = {feed.category for feed in enabled_feeds}
    assert len(enabled_feeds) == 7
    assert "steel-upstream" in categories
    assert "steel-market" in categories
    assert "steel-demand-macro" in categories
    assert "international-australia-ore" in categories
    assert "international-australia-disruption" in categories
    assert "international-global-ore" in categories
    assert "international-coking-coal" in categories
