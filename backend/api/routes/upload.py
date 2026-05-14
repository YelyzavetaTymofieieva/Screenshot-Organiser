from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.api.models.schemas import Note, UploadRequest
from backend.api.services import classifier, extractor, storage, vision

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=Note)
async def upload_screenshot(request: UploadRequest) -> Note:
    """
    Receive a screenshot as base64, run it through the AI pipeline, and
    persist the result.

    Pipeline:
        vision (Claude) -> classifier (confidence thresholds) -> extractor
        (clean data) -> storage (local filesystem + in-memory store)
    """
    logger.info("Received upload: filename=%s filepath=%s", request.filename, request.filepath)

    # 1. Determine media type from filename extension
    lower = request.filename.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        media_type = "image/jpeg"
    else:
        media_type = "image/png"

    # 2. Call Claude Vision
    try:
        claude_response = vision.analyse_image(request.image_data, media_type=media_type)
    except Exception as exc:
        logger.exception("Vision service error")
        raise HTTPException(status_code=502, detail=f"Vision service error: {exc}") from exc

    # 3. Apply confidence-based classification
    final_category, original_response = classifier.classify(claude_response)

    # 4. Clean / validate extracted_data for the final category
    cleaned_data = extractor.extract(final_category, original_response)

    # 5. Persist note and move file
    note_data = {
        "category": final_category,
        "confidence": original_response.confidence,
        "title": original_response.title,
        "extracted_data": cleaned_data,
        "note": original_response.note,
    }

    try:
        note = storage.classify_and_store(note_data, request.filepath)
    except Exception as exc:
        logger.exception("Storage error")
        raise HTTPException(status_code=500, detail=f"Storage error: {exc}") from exc

    return note
