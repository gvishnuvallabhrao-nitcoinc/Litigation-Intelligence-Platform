"""
Judge name normalization.
Names are inconsistent across Indian Kanoon and eCourts — this map must grow
as you scrape. Add new aliases whenever you encounter a new variant.
"""

import re

JUDGE_ALIASES: dict[str, str] = {
    "hon'ble mr. justice rajiv shakdher": "rajiv_shakdher",
    "justice r. shakdher": "rajiv_shakdher",
    "mr. justice rajiv shakdher": "rajiv_shakdher",
    "hon'ble mr. justice manmohan": "manmohan",
    "justice manmohan": "manmohan",
    "hon'ble ms. justice pratibha m. singh": "pratibha_m_singh",
    "justice pratibha singh": "pratibha_m_singh",
    "ms. justice pratibha m. singh": "pratibha_m_singh",
    "hon'ble mr. justice vibhu bakhru": "vibhu_bakhru",
    "justice vibhu bakhru": "vibhu_bakhru",
    "hon'ble mr. justice c. hari shankar": "c_hari_shankar",
    "justice c. hari shankar": "c_hari_shankar",
    "hon'ble mr. justice navin chawla": "navin_chawla",
    "justice navin chawla": "navin_chawla",
    "hon'ble mr. justice amit bansal": "amit_bansal",
    "justice amit bansal": "amit_bansal",
    "hon'ble mr. justice anish dayal": "anish_dayal",
    "justice anish dayal": "anish_dayal",
}

_STRIP_PREFIXES = re.compile(
    r"^(hon'ble\s+)?(the\s+)?"
    r"(mr\.|ms\.|mrs\.|dr\.|shri\s+|smt\.\s+)?\s*"
    r"justice\s+",
    re.IGNORECASE,
)


def normalize_judge(raw_name: str) -> str:
    """
    Returns a canonical snake_case judge key for use as a DB / stats key.
    Falls back to a cleaned snake_case version of the raw name when no alias exists.
    """
    if not raw_name:
        return "unknown"

    key = raw_name.lower().strip()

    if key in JUDGE_ALIASES:
        return JUDGE_ALIASES[key]

    # Strip honorifics and derive a clean key
    cleaned = _STRIP_PREFIXES.sub("", key)
    cleaned = re.sub(r"[^a-z0-9\s]", "", cleaned).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "unknown"


def add_alias(raw_name: str, canonical: str) -> None:
    """Register a new alias at runtime (e.g. when scraper finds a new variant)."""
    JUDGE_ALIASES[raw_name.lower().strip()] = canonical
