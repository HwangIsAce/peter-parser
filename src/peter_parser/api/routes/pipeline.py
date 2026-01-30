"""Pipeline API: POST /parse, GET /status/{job_id}, GET /result/{job_id}."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
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


@router.post("/parse", response_model=ParseResponse)
async def parse_upload(file: UploadFile = File(...)) -> ParseResponse:
    """Upload PDF, enqueue parse job; return job_id and status pending."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF file required")
    upload_dir = _ensure_upload_dir()
    path = os.path.join(upload_dir, f"{uuid.uuid4()}.pdf")
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    queue: Queue = get_queue()
    job = queue.enqueue(run_parse_job, path)
    return ParseResponse(job_id=job.id, status="pending")


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """Get parse job status."""
    conn = get_connection()
    try:
        job = RQJob.fetch(job_id, connection=conn)
    except Exception:
        raise HTTPException(status_code=404, detail="Job not found")
    status = _status_from_rq(job)
    created_at = job.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return StatusResponse(
        job_id=job_id,
        status=status,
        error=job.exc_string if job.is_failed else None,
        created_at=created_at.isoformat() if created_at else datetime.now(timezone.utc).isoformat(),
    )


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
    data = json.loads(raw)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return ResultResponse(**data)
