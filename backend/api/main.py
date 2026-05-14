from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import notes, upload

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

app = FastAPI(
    title="Screenshot Organiser API",
    description="Backend API for the screenshot organiser pipeline.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — allow localhost origins used during local development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8501",  # Streamlit default
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(notes.router, prefix="/api", tags=["notes"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
