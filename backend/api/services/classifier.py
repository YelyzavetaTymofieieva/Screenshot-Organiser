from __future__ import annotations

import logging

from backend.api.models.schemas import ClaudeResponse

logger = logging.getLogger(__name__)

# Confidence thresholds
AUTO_CLASSIFY_THRESHOLD = 0.75
MANUAL_REVIEW_THRESHOLD = 0.50


def classify(response: ClaudeResponse) -> tuple[str, ClaudeResponse]:
    """
    Apply confidence thresholds to determine the final category.

    Rules:
      >= 0.75 : keep category as-is (auto-classify)
      0.50–0.74: return "unclassified" (route to manual review queue)
      <  0.50 : return "junk"

    Returns:
        (final_category, original_response)
    """
    confidence = response.confidence

    if confidence >= AUTO_CLASSIFY_THRESHOLD:
        final_category = response.category
        logger.info(
            "Auto-classified as '%s' (confidence=%.2f)", final_category, confidence
        )
    elif confidence >= MANUAL_REVIEW_THRESHOLD:
        final_category = "unclassified"
        logger.info(
            "Low confidence (%.2f) — routing to unclassified for manual review",
            confidence,
        )
    else:
        final_category = "junk"
        logger.info(
            "Very low confidence (%.2f) — marking as junk", confidence
        )

    return final_category, response
