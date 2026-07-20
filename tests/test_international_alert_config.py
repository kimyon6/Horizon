import json
from pathlib import Path

from src.models import Config


def test_international_alert_config_is_valid_and_strict() -> None:
    path = Path("data/config.international-alerts.github.json")
    config = Config.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert config.ai.languages == ["zh"]
    assert config.filtering.ai_score_threshold == 8.0
    assert config.filtering.max_items == 5
    assert config.filtering.seen_state_filename == "international-alert-seen.json"
    assert config.webhook is not None
    assert config.webhook.notify_when_empty is False

    enabled_feeds = [feed for feed in config.sources.rss if feed.enabled]
    categories = {feed.category for feed in enabled_feeds}
    assert len(enabled_feeds) == 4
    assert "international-australia-ore" in categories
    assert "international-australia-disruption" in categories
    assert "international-global-ore" in categories
    assert "international-coking-coal" in categories
