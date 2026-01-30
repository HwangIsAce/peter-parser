"""RQ task: run pipeline and store result for GET /result."""
from __future__ import annotations

import json
import os

from rq import get_current_job

from peter_parser.common.queue import get_connection
from peter_parser.graph.flow import PipelineFlow


def run_parse_job(file_path: str) -> None:
    """
    RQ job: read file, run PipelineFlow.invoke(), store result in Redis.
    job_id is taken from RQ get_current_job().id; result at job_result:{job_id}.
    """
    job = get_current_job()
    job_id = job.id if job else None
    if not job_id:
        raise RuntimeError("run_parse_job must run inside RQ worker")
    conn = get_connection()
    result_key = f"job_result:{job_id}"
    try:
        with open(file_path, "rb") as f:
            doc_bytes = f.read()
        flow = PipelineFlow()
        state = flow.invoke(document=doc_bytes)
        chunks = state.get("chunks") or []
        from peter_parser.api.schemas.mappers import chunks_to_result_response

        resp = chunks_to_result_response(chunks)
        payload = resp.model_dump()
        conn.set(result_key, json.dumps(payload, ensure_ascii=False), ex=86400 * 7)  # 7 days TTL
    except Exception:
        raise
    finally:
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
