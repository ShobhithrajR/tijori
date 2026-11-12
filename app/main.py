"""FastAPI entrypoint (lane 2 owns this file).

Run with: uvicorn app.main:app --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.pipeline.pipeline import PrivacyPipeline


def create_app(*, pipeline: PrivacyPipeline | None = None) -> FastAPI:
    """Build the app. Tests may inject a pipeline with a fake provider/DB."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active = pipeline or PrivacyPipeline()
        application.state.pipeline = active
        application.state.repository = active.repository
        yield

    application = FastAPI(
        title="Tijori — DPDP Privacy Gateway",
        version="0.1.0",
        description="Detect, mask, forward sanitized text, reinsert locally.",
        lifespan=lifespan,
    )
    application.include_router(router)
    return application


app = create_app()
