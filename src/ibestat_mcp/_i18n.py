"""Shared internationalization utilities for IBESTAT response parsing."""

from __future__ import annotations

import unicodedata


def strip_accents(text: str) -> str:
    """Remove diacritics/accents from *text* for safe encoding.

    Uses NFKD normalization to decompose characters, then strips combining
    marks (category 'Mn').
    """
    if not text:
        return text
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def extract_localized_text(multilingual: dict | None, lang: str = "ca") -> str:
    """Extract text for *lang* from an InternationalString.

    The API structure is::

        {"text": [{"value": "the text", "lang": "ca"}, ...]}

    Falls back to the first available entry when the requested language is
    not present.  Returns an empty string for ``None`` or empty input.
    """
    if not multilingual:
        return ""
    texts = multilingual.get("text")
    if not texts:
        return ""
    for item in texts:
        if item.get("lang") == lang:
            return item["value"]
    # Fallback: return first available
    return texts[0]["value"]
