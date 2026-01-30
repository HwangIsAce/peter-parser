"""RQ worker entrypoint. Run: PYTHONPATH=src python -m peter_parser.worker (or rq worker --url $REDIS_URL with PYTHONPATH=src)."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on path when run as __main__
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from rq import SimpleWorker, Worker

from peter_parser.common.queue import get_connection, get_queue


def main() -> None:
    """Run RQ worker for default queue. Use SimpleWorker on macOS to avoid fork+objc crash."""
    conn = get_connection()
    queue = get_queue()
    # On Darwin (macOS), default Worker forks and can crash with objc/NSCharacterSet.
    worker_cls = SimpleWorker if sys.platform == "darwin" else Worker
    worker = worker_cls([queue], connection=conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
