"""RQ task: run pipeline and store result for GET /result."""
from __future__ import annotations

import json
import os

from rq import get_current_job

from peter_parser.common.queue import get_connection
from peter_parser.graph.flow import PipelineFlow
from peter_parser.graph.states import DOCUMENT_TYPE_SLIDE
from peter_parser.api.schemas.job_snapshot import JobSnapshot, SLIDE_JOB_QUEUE

# TTL for job_result and job_snapshot (7 days).
JOB_STORAGE_TTL = 86400 * 7


def run_parse_job(file_path: str) -> None:
    """
    RQ job: read file, run PipelineFlow.invoke(), store result in Redis.
    - job_result:{job_id}: API response for GET /result.
    - job_snapshot:{job_id}: full snapshot (for optimizer consumption).
    - slide_job_queue: list of job_id for slide docs (batch consumes).
    """
    job = get_current_job()
    job_id = job.id if job else None
    if not job_id:
        raise RuntimeError("run_parse_job must run inside RQ worker")
    conn = get_connection()
    result_key = f"job_result:{job_id}"
    snapshot_key = f"job_snapshot:{job_id}"
    try:
        with open(file_path, "rb") as f:
            doc_bytes = f.read()
        flow = PipelineFlow()
        state = flow.invoke(document=doc_bytes)
        chunks = state.get("chunks") or []
        from peter_parser.api.schemas.mappers import chunks_to_result_response

        resp = chunks_to_result_response(chunks)
        payload = resp.model_dump()
        conn.set(result_key, json.dumps(payload, ensure_ascii=False), ex=JOB_STORAGE_TTL)

        snapshot = JobSnapshot.from_state(state, job_id=job_id)
        conn.set(
            snapshot_key,
            json.dumps(snapshot.model_dump(), ensure_ascii=False),
            ex=JOB_STORAGE_TTL,
        )

        if state.get("document_type") == DOCUMENT_TYPE_SLIDE:
            conn.rpush(SLIDE_JOB_QUEUE, job_id)
    except Exception:
        raise
    finally:
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
