"""RQ worker entrypoint. Run: PYTHONPATH=src python -m peter_parser.worker (or rq worker --url $REDIS_URL with PYTHONPATH=src)."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on path when run as __main__
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from rq import Worker

from peter_parser.common.queue import get_connection, get_queue


def main() -> None:
    """Run RQ worker for default queue."""
    conn = get_connection()
    queue = get_queue()
    worker = Worker([queue], connection=conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
