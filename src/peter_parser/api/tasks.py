"""RQ task: run pipeline and store result for GET /result."""
from __future__ import annotations

import json
import logging
import os
import time

from rq import get_current_job

from peter_parser.common.config import Config
from peter_parser.common.queue import get_connection
from peter_parser.graph.flow import PipelineFlow
from peter_parser.graph.states import DOCUMENT_TYPE_SLIDE
from peter_parser.api.schemas.job_snapshot import JobSnapshot, SLIDE_JOB_QUEUE

# TTL for job_result and job_snapshot (7 days).
JOB_STORAGE_TTL = 86400 * 7

logger = logging.getLogger(__name__)


def run_parse_job(file_path: str, document_type: str = "plain") -> None:
    """
    RQ job: read file, run PipelineFlow.invoke(), store result in Redis.
    - job_result:{job_id}: API response for GET /result.
    - job_snapshot:{job_id}: full snapshot (for optimizer consumption).
    - slide_job_queue: list of job_id for slide docs (batch consumes).

    Args:
        file_path: Path to PDF file (.pdf) or text file (.txt for lifelog).
        document_type: "heading" | "plain" | "slide" | "lifelog".
    """
    job = get_current_job()
    job_id = job.id if job else None
    if not job_id:
        raise RuntimeError("run_parse_job must run inside RQ worker")
    conn = get_connection()
    result_key = f"job_result:{job_id}"
    snapshot_key = f"job_snapshot:{job_id}"
    try:
        if document_type == "lifelog":
            with open(file_path, "r", encoding="utf-8") as f:
                document = f.read()
            from peter_parser_core import BaseParser
            from peter_parser_core.common.types import ContentModel
            from peter_parser_core import ParsedDocument

            class NoOpParser(BaseParser):
                def parse(self, doc):
                    return ParsedDocument(content=ContentModel(text=""), elements=[], pages=[], metadata={})

            flow = PipelineFlow(parser=NoOpParser())
            state = flow.invoke(document=document, document_type="lifelog")
        else:
            with open(file_path, "rb") as f:
                document = f.read()
            flow = PipelineFlow()
            state = flow.invoke(document=document, document_type=document_type)
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


def run_vlm_chunk_optimization_batch() -> None:
    """
    RQ job: pop up to VLM_OPT_BATCH_SIZE job_ids from slide_job_queue, load
    job_snapshot for each, run optimizer (evaluate + optimize user prompt),
    write both VLM prompts to Redis. Enqueue periodically via cron or when
    slide jobs accumulate (e.g. cron: rq enqueue peter_parser.api.tasks.run_vlm_chunk_optimization_batch).
    """
    conn = get_connection()
    batch_size = Config.VLM_OPT_BATCH_SIZE
    raw = conn.lpop(SLIDE_JOB_QUEUE, batch_size)
    if not raw:
        logger.info("run_vlm_chunk_optimization_batch: slide_job_queue empty, skipping")
        return
    job_ids = [j.decode("utf-8") if isinstance(j, bytes) else str(j) for j in (raw if isinstance(raw, list) else [raw])]
    snapshots: list[dict] = []
    for job_id in job_ids:
        key = f"job_snapshot:{job_id}"
        data = conn.get(key)
        if data is None:
            logger.warning("run_vlm_chunk_optimization_batch: missing snapshot for job_id=%s", job_id)
            continue
        try:
            payload = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
            snapshots.append(payload)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("run_vlm_chunk_optimization_batch: invalid snapshot job_id=%s err=%s", job_id, e)
            continue
    if not snapshots:
        logger.info("run_vlm_chunk_optimization_batch: no valid snapshots, skipping")
        return
    start = time.perf_counter()
    try:
        from peter_parser.impl.optimizer_adapter import run_optimization_and_save_prompts

        metrics = run_optimization_and_save_prompts(
            snapshots,
            openai_model=Config.VLM_OPT_OPENAI_MODEL or None,
        )
        elapsed = time.perf_counter() - start
        logger.info(
            "run_vlm_chunk_optimization_batch: success snapshots=%d job_ids=%s elapsed=%.2fs metrics=%s",
            len(snapshots),
            job_ids[:5] if len(job_ids) > 5 else job_ids,
            elapsed,
            metrics,
        )
    except Exception as e:
        logger.exception(
            "run_vlm_chunk_optimization_batch: failed snapshots=%d job_ids=%s err=%s",
            len(snapshots),
            job_ids[:5] if len(job_ids) > 5 else job_ids,
            e,
        )
        raise
