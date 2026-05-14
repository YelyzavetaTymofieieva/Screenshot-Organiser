from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from backend.api.models.schemas import Note

logger = logging.getLogger(__name__)

# In-memory store: { note_id: Note }
_store: dict[str, Note] = {}

# Destination base directory
_SCREENSHOTS_BASE = Path("~/Screenshots").expanduser()
_UNCLASSIFIED_DIR = _SCREENSHOTS_BASE / "Unclassified"
_ORGANISED_DIR = _SCREENSHOTS_BASE / "Organised"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _move_file(src: str, dest_dir: Path) -> str:
    """Move a file to dest_dir. Returns the new absolute path."""
    _ensure_dir(dest_dir)
    src_path = Path(src)
    dest_path = dest_dir / src_path.name

    # Avoid overwriting by appending a uuid suffix if a name clash exists
    if dest_path.exists():
        stem = src_path.stem
        suffix = src_path.suffix
        dest_path = dest_dir / f"{stem}_{uuid4().hex[:8]}{suffix}"

    try:
        shutil.move(str(src_path), str(dest_path))
        logger.info("Moved '%s' -> '%s'", src, dest_path)
    except (FileNotFoundError, PermissionError) as exc:
        logger.warning("Could not move file: %s", exc)
        # Store the original path so nothing is lost
        dest_path = src_path

    return str(dest_path)


def classify_and_store(note_data: dict[str, Any], filepath: str) -> Note:
    """
    Move the file to the appropriate local directory and persist the note
    in the in-memory store.

    Args:
        note_data: dict with keys matching NoteBase fields plus optional extras.
        filepath:  absolute path to the original screenshot file.

    Returns:
        The persisted Note object.
    """
    note_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    category = note_data.get("category", "unclassified")

    if category in ("junk", "unclassified"):
        dest_dir = _UNCLASSIFIED_DIR
    else:
        dest_dir = _ORGANISED_DIR / category

    local_path = _move_file(filepath, dest_dir)

    note = Note(
        id=note_id,
        created_at=created_at,
        category=category,
        confidence=note_data.get("confidence", 0.0),
        title=note_data.get("title", "Untitled"),
        extracted_data=note_data.get("extracted_data", {}),
        note=note_data.get("note"),
        s3_key=None,  # Milestone 2
        local_path=local_path,
    )

    _store[note_id] = note
    logger.info("Stored note id=%s category=%s", note_id, category)
    return note


def get_notes(category: Optional[str] = None) -> list[Note]:
    """Return all notes, optionally filtered by category."""
    notes = list(_store.values())
    if category:
        notes = [n for n in notes if n.category == category]
    return notes


def get_note(note_id: str) -> Optional[Note]:
    """Return a single note by ID, or None if not found."""
    return _store.get(note_id)


def delete_note(note_id: str) -> bool:
    """Remove a note from the store. Returns True if found and deleted."""
    if note_id in _store:
        del _store[note_id]
        logger.info("Deleted note id=%s", note_id)
        return True
    return False


def update_note(note_id: str, updates: dict[str, Any]) -> Optional[Note]:
    """
    Update fields on an existing note.

    Args:
        note_id: ID of the note to update.
        updates: dict of fields to update (any NoteBase/Note field).

    Returns:
        Updated Note, or None if not found.
    """
    note = _store.get(note_id)
    if note is None:
        return None

    note_dict = note.model_dump()
    # Only apply keys that are valid Note fields
    valid_keys = set(Note.model_fields.keys())
    for key, value in updates.items():
        if key in valid_keys and key not in ("id", "created_at"):
            note_dict[key] = value

    updated_note = Note(**note_dict)
    _store[note_id] = updated_note
    logger.info("Updated note id=%s fields=%s", note_id, list(updates.keys()))
    return updated_note
