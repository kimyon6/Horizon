from datetime import datetime, timezone

from src.models import ContentItem, SourceType
from src.orchestrator import _beijing_today, keep_current_beijing_day


def _item(item_id: str, published_at: datetime) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=item_id,
        url=f"https://example.com/{item_id}",
        published_at=published_at,
    )


def test_current_day_filter_uses_beijing_calendar_boundary() -> None:
    now = datetime(2026, 7, 21, 1, 0, tzinfo=timezone.utc)  # Beijing 09:00
    items = [
        _item("yesterday", datetime(2026, 7, 20, 15, 59, tzinfo=timezone.utc)),
        _item("today-after-midnight", datetime(2026, 7, 20, 16, 1, tzinfo=timezone.utc)),
        _item("today-recent", datetime(2026, 7, 21, 0, 50, tzinfo=timezone.utc)),
    ]

    kept = keep_current_beijing_day(items, now=now)

    assert [item.id for item in kept] == ["today-after-midnight", "today-recent"]


def test_beijing_report_date_does_not_use_previous_utc_date() -> None:
    now = datetime(2026, 7, 20, 23, 17, tzinfo=timezone.utc)

    assert _beijing_today(now) == "2026-07-21"
