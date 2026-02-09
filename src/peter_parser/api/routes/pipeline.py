"""Pipeline API: POST /parse, GET /status/{job_id}, GET /result/{job_id}."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from rq import Queue
from rq.job import Job as RQJob

from peter_parser.api.schemas.response import (
    ParseResponse,
    ResultResponse,
    StatusResponse,
)
from peter_parser.api.tasks import run_parse_job
from peter_parser.common.config import Config
from peter_parser.common.queue import get_connection, get_queue

router = APIRouter(tags=["pipeline"])


def _ensure_upload_dir() -> str:
    d = Config.UPLOAD_DIR
    if not os.path.isabs(d):
        d = os.path.join(os.getcwd(), d)
    os.makedirs(d, exist_ok=True)
    return d


def _status_from_rq(job: RQJob) -> str:
    if job.is_queued:
        return "pending"
    if job.is_started:
        return "processing"
    if job.is_finished:
        return "completed"
    if job.is_failed:
        return "failed"
    return "pending"


VALID_DOCUMENT_TYPES = ("heading", "plain", "slide", "lifelog", "excel")


@router.post("/parse", response_model=ParseResponse)
async def parse_upload(
    file: UploadFile = File(...),
    document_type: str = Form("plain", description="heading | plain | slide | lifelog | excel"),
) -> ParseResponse:
    """Upload document: PDF (heading/plain/slide), .txt (lifelog), or .xlsx (excel); enqueue job, return job_id."""
    doc_type = (document_type or "plain").strip().lower()
    if doc_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"document_type must be one of {VALID_DOCUMENT_TYPES}",
        )
    if not file.filename:
        raise HTTPException(status_code=400, detail="File required")
    fn_lower = file.filename.lower()
    if doc_type == "lifelog":
        if not fn_lower.endswith(".txt"):
            raise HTTPException(status_code=400, detail="For lifelog, .txt file required")
        upload_dir = _ensure_upload_dir()
        path = os.path.join(upload_dir, f"{uuid.uuid4()}.txt")
        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)
    elif doc_type == "excel":
        if not fn_lower.endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="For excel, .xlsx file required")
        upload_dir = _ensure_upload_dir()
        path = os.path.join(upload_dir, f"{uuid.uuid4()}.xlsx")
        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)
    else:
        if not fn_lower.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="For heading/plain/slide, PDF file required")
        upload_dir = _ensure_upload_dir()
        path = os.path.join(upload_dir, f"{uuid.uuid4()}.pdf")
        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)
    queue: Queue = get_queue()
    job = queue.enqueue(run_parse_job, path, doc_type, job_timeout=600)
    return ParseResponse(job_id=job.id, status="pending")


def _safe_created_at_iso(job: RQJob) -> str:
    """Return job created_at as ISO string; fallback to now() if missing or invalid."""
    created_at = getattr(job, "created_at", None)
    if created_at is None:
        return datetime.now(timezone.utc).isoformat()
    if getattr(created_at, "isoformat", None) is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        if getattr(created_at, "tzinfo", None) is None and hasattr(created_at, "replace"):
            created_at = created_at.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        return created_at.isoformat()
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat()


def _safe_error_string(job: RQJob) -> str | None:
    """Return error message for failed job; None otherwise. Always returns str or None."""
    if not getattr(job, "is_failed", False):
        return None
    try:
        exc = getattr(job, "exc_string", None)
        if exc is None:
            return None
        return str(exc)[:4096]
    except Exception:
        return None


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """Get parse job status."""
    try:
        conn = get_connection()
        job = RQJob.fetch(job_id, connection=conn)
    except Exception as e:
        err_msg = str(e).lower()
        if "no such job" in err_msg or "job not found" in err_msg or "not found" in err_msg:
            raise HTTPException(status_code=404, detail="Job not found") from e
        try:
            from rq.exceptions import NoSuchJobError
            if isinstance(e, NoSuchJobError):
                raise HTTPException(status_code=404, detail="Job not found") from e
        except HTTPException:
            raise
        raise HTTPException(status_code=500, detail=f"Failed to fetch job: {type(e).__name__}: {e}") from e
    status = _status_from_rq(job)
    try:
        return StatusResponse(
            job_id=job_id,
            status=status,
            error=_safe_error_string(job),
            created_at=_safe_created_at_iso(job),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build status: {type(e).__name__}: {e}") from e


@router.get("/result/{job_id}", response_model=ResultResponse)
async def get_result(job_id: str) -> ResultResponse:
    """Get parse result when job is completed; 400 if not completed."""
    conn = get_connection()
    try:
        job = RQJob.fetch(job_id, connection=conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_finished:
        raise HTTPException(status_code=400, detail="Job not completed")
    import json

    raw = conn.get(f"job_result:{job_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Result not found")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return ResultResponse(**data)
