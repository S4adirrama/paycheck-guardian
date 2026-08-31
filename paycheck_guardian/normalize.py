"""Deterministic merchant-name cleanup and alias lookup."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Mapping


@dataclass(frozen=True)
class MerchantRule:
    """The canonical representation for one known merchant alias."""

    merchant: str
    category: str


def _clean(raw: str) -> str:
    """Make a stable lookup string without terminal phone or order noise."""
    value = raw.upper().strip()
    value = re.sub(r"(?:\b(?:ORDER|ORD|REF|TRANSACTION|TXN)\b[ #:-]*[A-Z0-9-]+|\b\d{3}[-. ]\d{3}[-. ]\d{4})$", "", value)
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return " ".join(value.split())


def load_aliases(path: Path) -> dict[str, MerchantRule]:
    """Load alias rules from a local JSON mapping, with normalized keys."""
    with path.open(encoding="utf-8") as stream:
        contents = json.load(stream)
    if not isinstance(contents, dict):
        raise ValueError("merchant aliases must be a JSON object")
    return {
        _clean(alias): MerchantRule(merchant=entry["merchant"], category=entry["category"])
        for alias, entry in contents.items()
    }


def normalize_merchant(raw: str, aliases: Mapping[str, MerchantRule]) -> tuple[str, str]:
    """Return canonical merchant/category or a readable unknown fallback."""
    cleaned = _clean(raw)
    for alias in sorted(aliases, key=len, reverse=True):
        if cleaned == alias or cleaned.startswith(f"{alias} "):
            rule = aliases[alias]
            return rule.merchant, rule.category
    return cleaned.title(), "other"
