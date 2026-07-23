"""Deterministic market-scope notes for steel and raw-material news."""

import re


_FUTURES = re.compile(
    r"期货|主力合约|连续合约|盘面|夜盘|日盘|收盘|开盘|合约"
)
_PHYSICAL = re.compile(
    r"现货|采购价|出厂价|钢厂|焦企|湿熄焦|干熄焦|提涨|提降|落地|执行"
)
_REBOUND = re.compile(r"反弹|先抑后扬|回升|拉升|走强")
_PRICE_CUT = re.compile(r"提降|下调|调降|降价")
_PRICE_RISE = re.compile(r"提涨|上调|调涨|涨价")
_IMPLEMENTED = re.compile(r"落地|执行|接受|正式实施|自.{0,20}起执行")
_NOT_IMPLEMENTED = re.compile(r"尚未落地|未落地|等待.{0,12}落地|拟|计划|诉求")


def market_context_notes(title: object, content: object = "") -> list[str]:
    """Describe futures/physical scope without relying on model inference."""
    text = f"{title or ''}\n{content or ''}"
    has_futures = bool(_FUTURES.search(text))
    has_physical = bool(_PHYSICAL.search(text))
    notes: list[str] = []

    if has_futures and has_physical:
        notes.append("同时涉及期货盘面和现货/钢厂采购，两个价格口径不能混为一谈。")
    elif has_futures:
        notes.append("行情变化指期货盘面，不代表现货成交价同步变化。")
    elif has_physical:
        notes.append("行情口径主要是现货或钢厂采购。")

    if has_futures and _REBOUND.search(text):
        notes.append("“反弹/先抑后扬”指期货合约走势，不等于焦炭现货涨价。")

    if _PRICE_CUT.search(text):
        if _IMPLEMENTED.search(text) and not _NOT_IMPLEMENTED.search(text):
            notes.append("原文显示提降或下调已经落地/执行，现货采购方向是下调。")
        else:
            notes.append("原文出现提降或下调，不能解读为焦炭现货上涨。")

    if _PRICE_RISE.search(text):
        if _IMPLEMENTED.search(text) and not _NOT_IMPLEMENTED.search(text):
            notes.append("原文显示提涨或上调已经落地/执行。")
        else:
            notes.append("原文只出现提涨或上调信息；未明确落地时，不代表成交价已经上涨。")

    return notes
