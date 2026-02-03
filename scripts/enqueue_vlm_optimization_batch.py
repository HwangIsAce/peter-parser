#!/usr/bin/env python3
"""
Enqueue run_vlm_chunk_optimization_batch to RQ. Use from cron for Phase 4 trigger.
Example cron (hourly): 0 * * * * cd /path/to/peter-parser && uv run python scripts/enqueue_vlm_optimization_batch.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from peter_parser.api.tasks import run_vlm_chunk_optimization_batch
from peter_parser.common.queue import get_queue


def main() -> None:
    queue = get_queue()
    job = queue.enqueue(run_vlm_chunk_optimization_batch, job_timeout=600)
    print(f"Enqueued run_vlm_chunk_optimization_batch job_id={job.id}")


if __name__ == "__main__":
    main()
