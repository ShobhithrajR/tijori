"""FastAPI entrypoint (lane 2 owns this file).

Spine state: bootable with /health only. Lane 2 adds the /v1 routers,
pipeline orchestration and audit repository.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="Tijori — DPDP Privacy Gateway",
    version="0.1.0",
    description="Detect, mask, forward sanitized text, reinsert locally.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.llm_model,
    }
