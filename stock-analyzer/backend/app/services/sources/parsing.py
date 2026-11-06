"""Conversion des nombres au format français (« 7 970,00 », « -1,35 % », « 12,1 M »)."""
from __future__ import annotations

import re

_NUMBER = re.compile(r"[-+]?\d[\d\s  .]*(?:,\d+)?")


def fr_number(text: str | None) -> float | None:
    """« 7 970,00 » → 7970.0 ; « 537.58 EUR » → 537.58 ; « 59,61 M » → 59 610 000."""
    if not text:
        return None
    text = text.replace("−", "-").strip()
    m = _NUMBER.search(text)
    if not m:
        return None
    raw = re.sub(r"[\s  ]", "", m.group()).rstrip(".")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:  # « 1.234.567 »
        raw = raw.replace(".", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    suffix = text[m.end():].strip()[:2].upper()
    if suffix.startswith("T"):
        value *= 1e12
    elif suffix.startswith(("MD", "B")):
        value *= 1e9
    elif suffix.startswith("M"):
        value *= 1e6
    elif suffix.startswith("K"):
        value *= 1e3
    return value
