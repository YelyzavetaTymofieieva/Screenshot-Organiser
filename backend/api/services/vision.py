from __future__ import annotations

import json
import logging
import os

from openai import OpenAI
from dotenv import load_dotenv

from backend.api.models.schemas import ClaudeResponse

load_dotenv()

logger = logging.getLogger(__name__)

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
MODEL = "accounts/fireworks/models/qwen3p6-plus"

PROMPT = """You are a screenshot organiser. Analyse this screenshot and return ONLY a JSON object (no markdown, no explanation) with this exact structure:
{
  "category": one of ["recipe", "vocabulary", "product", "quote", "code", "junk"],
  "confidence": float between 0.0 and 1.0,
  "title": "short descriptive title (max 60 chars)",
  "extracted_data": {
    // for recipe: {"ingredients": [], "steps": [], "cuisine": "", "cooking_time": null}
    // for vocabulary: {"word": "", "definition": "", "example_sentence": "", "language": ""}
    // for product: {"brand": "", "product_name": "", "category": ""}
    // for quote: {"text": "", "author": "", "source": ""}
    // for code: {"language": "", "snippet": "", "description": ""}
    // for junk: {}
  },
  "note": "optional short human-readable note or null"
}
The screenshot may be in any language (including Ukrainian). Extract and preserve text in its original language."""


def analyse_image(image_data_b64: str, media_type: str = "image/png") -> ClaudeResponse:
    client = OpenAI(
        api_key=FIREWORKS_API_KEY,
        base_url="https://api.fireworks.ai/inference/v1",
    )

    message = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data_b64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": PROMPT,
                    },
                ],
            }
        ],
    )

    content = message.choices[0].message.content
    logger.info("Raw Fireworks response: %r", content)
    if not content:
        logger.error("Model returned empty content. Full response: %s", message)
        return ClaudeResponse(
            category="junk", confidence=0.0, title="Empty response",
            extracted_data={}, note="Model returned no content",
        )
    raw_text = content.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Attempt to extract JSON from within the response if Claude wrapped it
        import re

        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from model response: %s", raw_text)
                parsed = {
                    "category": "junk",
                    "confidence": 0.0,
                    "title": "Parse error",
                    "extracted_data": {},
                    "note": "Model returned unparseable response",
                }
        else:
            logger.error("No JSON found in model response: %s", raw_text)
            parsed = {
                "category": "junk",
                "confidence": 0.0,
                "title": "Parse error",
                "extracted_data": {},
                "note": "Model returned unparseable response",
            }

    return ClaudeResponse(
        category=parsed.get("category", "junk"),
        confidence=float(parsed.get("confidence", 0.0)),
        title=parsed.get("title", "Untitled")[:60],
        extracted_data=parsed.get("extracted_data", {}),
        note=parsed.get("note"),
    )
