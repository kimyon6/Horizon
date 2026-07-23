from src.ai.market_context import market_context_notes


def test_futures_rebound_is_not_described_as_physical_coke_rise() -> None:
    notes = market_context_notes(
        "华泰期货：焦炭首轮提降，价格先抑后扬",
        "昨日双焦主力合约先抑后扬，钢厂开启焦炭首轮提降。",
    )
    combined = " ".join(notes)

    assert "两个价格口径不能混为一谈" in combined
    assert "不等于焦炭现货涨价" in combined
    assert "不能解读为焦炭现货上涨" in combined


def test_implemented_physical_price_cut_is_labeled_as_downward() -> None:
    notes = market_context_notes(
        "焦炭首轮提降落地",
        "钢厂采购价下调55元，自今日零时起执行。",
    )

    assert any("已经落地/执行" in note for note in notes)
    assert any("方向是下调" in note for note in notes)


def test_price_rise_proposal_is_not_labeled_as_completed_increase() -> None:
    notes = market_context_notes("焦企开启第十一轮提涨", "焦企提出涨价诉求。")

    assert any("不代表成交价已经上涨" in note for note in notes)


def test_explicit_not_landed_is_not_mistaken_for_implementation() -> None:
    notes = market_context_notes("焦炭第二轮提涨尚未落地", "等待钢厂接受。")

    assert not any("已经落地/执行" in note for note in notes)
    assert any("不代表成交价已经上涨" in note for note in notes)
