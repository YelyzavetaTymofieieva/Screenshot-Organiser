from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api.models.schemas import Note
from backend.api.services import storage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/notes", response_model=list[Note])
async def list_notes(
    category: Optional[str] = Query(default=None, description="Filter by category")
) -> list[Note]:
    """List all notes, with an optional category filter."""
    return storage.get_notes(category=category)


@router.get("/notes/{note_id}", response_model=Note)
async def get_note(note_id: str) -> Note:
    """Retrieve a single note by ID."""
    note = storage.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    return note


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: str) -> None:
    """Delete a note by ID."""
    deleted = storage.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")


@router.put("/notes/{note_id}", response_model=Note)
async def update_note(note_id: str, updates: dict) -> Note:
    """
    Update a note — typically used for re-categorising an unclassified note.

    The request body should be a JSON object containing only the fields to
    update (e.g. ``{"category": "recipe"}``).
    """
    updated = storage.update_note(note_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Note '{note_id}' not found")
    return updated
