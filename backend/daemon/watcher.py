#!/usr/bin/env python3
from __future__ import annotations

import base64
import logging
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

WATCH_FOLDER = Path(os.getenv("WATCH_FOLDER", "~/Desktop")).expanduser()
API_URL = os.getenv("API_URL", "http://localhost:8000/api/upload")
POLL_INTERVAL = 2

SCREENSHOT_PATTERN = re.compile(
    r"^Screenshot \d{4}-\d{2}-\d{2} at \d{1,2}\.\d{2}\.\d{2}([\s ][AP]M)?\.(png|jpg|jpeg)$",
    re.IGNORECASE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("watcher")


def is_screenshot(filename: str) -> bool:
    return bool(SCREENSHOT_PATTERN.match(filename))


def post_screenshot(filepath: Path) -> None:
    logger.info("Processing: %s", filepath.name)
    try:
        raw = filepath.read_bytes()
    except (FileNotFoundError, PermissionError) as exc:
        logger.error("Cannot read '%s': %s", filepath, exc)
        return

    payload = {
        "filename": filepath.name,
        "image_data": base64.b64encode(raw).decode("utf-8"),
        "filepath": str(filepath),
    }

    try:
        response = httpx.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()
        logger.info("Done '%s' — %s", filepath.name, response.json())
    except httpx.HTTPStatusError as exc:
        logger.error("API error %s for '%s': %s", exc.response.status_code, filepath.name, exc.response.text)
    except httpx.RequestError as exc:
        logger.error("Request failed for '%s': %s", filepath.name, exc)


def main() -> None:
    if not WATCH_FOLDER.exists():
        logger.error("Watch folder does not exist: %s", WATCH_FOLDER)
        sys.exit(1)

    logger.info("Starting watcher on: %s", WATCH_FOLDER)
    logger.info("API endpoint: %s", API_URL)

    seen: set[Path] = {
        f for f in WATCH_FOLDER.iterdir()
        if f.is_file() and is_screenshot(f.name)
    }
    logger.info("Ignoring %d pre-existing screenshots", len(seen))

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            try:
                current = {
                    f for f in WATCH_FOLDER.iterdir()
                    if f.is_file() and is_screenshot(f.name)
                }
            except OSError as exc:
                logger.error("Cannot read watch folder: %s", exc)
                continue

            new_files = current - seen
            seen = current

            for filepath in sorted(new_files):
                logger.info("Detected: %s — waiting 1s", filepath.name)
                time.sleep(1)
                post_screenshot(filepath)

    except KeyboardInterrupt:
        logger.info("Watcher stopped.")


if __name__ == "__main__":
    main()
