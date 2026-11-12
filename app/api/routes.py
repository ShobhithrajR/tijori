"""HTTP surface (lane 2). CONTRACT.md §4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.audit.repository import AuditRepository
from app.config import settings
from app.contracts import AuditRecord, ProcessRequest, ProcessResponse, SanitizeRequest, SanitizeResponse
from app.pipeline.pipeline import (
    OutboundLeakageError,
    PipelineFailure,
    PrivacyPipeline,
    ProviderFailure,
)

router = APIRouter()


def get_pipeline(request: Request) -> PrivacyPipeline:
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        pipeline = PrivacyPipeline()
        request.app.state.pipeline = pipeline
    return pipeline


def get_repository(request: Request) -> AuditRepository:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        repository = get_pipeline(request).repository
        request.app.state.repository = repository
    return repository


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    provider_name = settings.llm_provider
    model = settings.llm_model
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is not None:
        try:
            active = pipeline.provider
            provider_name = active.name
            model = active.model
        except Exception:
            pass
    return {
        "status": "ok",
        "provider": provider_name,
        "model": model,
    }


@router.post("/v1/sanitize", response_model=SanitizeResponse)
def sanitize(
    req: SanitizeRequest,
    pipeline: PrivacyPipeline = Depends(get_pipeline),
) -> SanitizeResponse:
    try:
        return pipeline.sanitize(req)
    except PipelineFailure as exc:
        raise HTTPException(
            status_code=500,
            detail=f"gateway request failed (request_id={exc.request_id})",
        ) from exc


@router.post("/v1/process", response_model=ProcessResponse)
async def process(
    req: ProcessRequest,
    pipeline: PrivacyPipeline = Depends(get_pipeline),
) -> ProcessResponse:
    try:
        return await pipeline.process(req)
    except ProviderFailure as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider request failed (request_id={exc.request_id})",
        ) from exc
    except OutboundLeakageError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Outbound payload rejected: unmasked PII detected "
                f"(request_id={exc.request_id})"
            ),
        ) from exc
    except PipelineFailure as exc:
        raise HTTPException(
            status_code=500,
            detail=f"gateway request failed (request_id={exc.request_id})",
        ) from exc


@router.get("/v1/audit", response_model=list[AuditRecord])
def list_audit(
    limit: int = Query(default=50, ge=1, le=500),
    repository: AuditRepository = Depends(get_repository),
) -> list[AuditRecord]:
    return repository.list(limit=limit)


@router.get("/v1/audit/{request_id}", response_model=AuditRecord)
def get_audit(
    request_id: str,
    repository: AuditRepository = Depends(get_repository),
) -> AuditRecord:
    record = repository.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="audit record not found")
    return record
