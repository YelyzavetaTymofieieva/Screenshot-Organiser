from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class UploadRequest(BaseModel):
    filename: str
    image_data: str  # base64
    filepath: str


class NoteBase(BaseModel):
    category: str  # recipe, vocabulary, product, quote, code, junk, unclassified
    confidence: float
    title: str
    extracted_data: dict
    note: Optional[str] = None


class Note(NoteBase):
    id: str
    created_at: str
    s3_key: Optional[str] = None
    local_path: Optional[str] = None  # for unclassified


class ClaudeResponse(BaseModel):
    category: str
    confidence: float
    title: str
    extracted_data: dict
    note: Optional[str] = None
