from __future__ import annotations

import logging
from typing import Any

from backend.api.models.schemas import ClaudeResponse

logger = logging.getLogger(__name__)

# Default shapes for each category's extracted_data
_DEFAULTS: dict[str, dict[str, Any]] = {
    "recipe": {"ingredients": [], "steps": [], "cuisine": ""},
    "vocabulary": {"word": "", "definition": "", "example_sentence": "", "language": ""},
    "product": {"brand": "", "product_name": "", "category": ""},
    "quote": {"text": "", "author": "", "source": ""},
    "code": {"language": "", "snippet": "", "description": ""},
    "junk": {},
    "unclassified": {},
}


def extract(category: str, response: ClaudeResponse) -> dict[str, Any]:
    """
    Validate and clean the extracted_data for the given category.

    - Merges Claude's output with the expected default shape so all keys are
      present even when Claude omits some.
    - Strips keys that do not belong to the expected shape (unknown fields are
      dropped to keep the data clean).
    - For unknown/unrecognised categories returns an empty dict.

    Returns:
        Cleaned extracted_data dict.
    """
    defaults = _DEFAULTS.get(category)
    if defaults is None:
        logger.warning("Unknown category '%s' — returning empty extracted_data", category)
        return {}

    if not defaults:
        # junk / unclassified — no structured fields expected
        return {}

    raw: dict[str, Any] = response.extracted_data if isinstance(response.extracted_data, dict) else {}

    cleaned: dict[str, Any] = {}
    for key, default_value in defaults.items():
        value = raw.get(key, default_value)

        # Type coercion: ensure lists stay lists, strings stay strings
        if isinstance(default_value, list) and not isinstance(value, list):
            logger.debug(
                "Field '%s' expected list, got %s — resetting to default", key, type(value).__name__
            )
            value = default_value
        elif isinstance(default_value, str) and not isinstance(value, str):
            value = str(value) if value is not None else ""

        cleaned[key] = value

    return cleaned
