from src.ai.grounding import corroborated_years, extract_years, remove_unsupported_years


def test_extract_years_reads_only_explicit_calendar_years() -> None:
    assert extract_years("2026年二季度", "产量8426万吨") == {2026}


def test_corroborated_year_requires_two_independent_results() -> None:
    results = [
        {"title": "2026年第二季度报告", "body": "最新报告"},
        {"title": "淡水河谷更新", "body": "公司发布2026年二季度数据"},
        {"title": "历史数据", "body": "2025年二季度"},
    ]

    assert corroborated_years(results) == {2026}


def test_remove_unsupported_year_preserves_period_without_guessing() -> None:
    text = "淡水河谷公布2025 年第二季度铁矿石产量为8426万吨。"

    assert remove_unsupported_years(text, {2026}) == (
        "淡水河谷公布第二季度铁矿石产量为8426万吨。"
    )
