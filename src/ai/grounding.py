"""Deterministic guards for factual years in AI-generated news text."""

from collections import Counter
import re
from typing import Iterable, Mapping


_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_YEAR_TOKEN_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?:\s*年)?(?!\d)")


def extract_years(*values: object) -> set[int]:
    """Return explicit four-digit calendar years found in the supplied text."""
    years: set[int] = set()
    for value in values:
        if value is None:
            continue
        years.update(int(match) for match in _YEAR_RE.findall(str(value)))
    return years


def corroborated_years(
    results: Iterable[Mapping[str, object]],
    *,
    minimum_sources: int = 2,
) -> set[int]:
    """Return years independently present in at least ``minimum_sources`` results."""
    counts: Counter[int] = Counter()
    for result in results:
        years = extract_years(result.get("title"), result.get("body"))
        counts.update(years)
    return {year for year, count in counts.items() if count >= minimum_sources}


def remove_unsupported_years(text: object, supported_years: set[int]) -> str:
    """Remove year claims that are unsupported by source text or corroboration.

    The surrounding statement is retained. For example, an unsupported
    ``2025年第二季度`` becomes the safer ``第二季度`` rather than a guessed year.
    """
    value = str(text or "")

    def replace(match: re.Match[str]) -> str:
        year = int(match.group(1))
        return match.group(0) if year in supported_years else ""

    value = _YEAR_TOKEN_RE.sub(replace, value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"（\s*）", "", value)
    return value.strip()
