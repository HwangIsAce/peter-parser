#!/usr/bin/env python3
"""Test heading pipeline on HV-A00 and 프로메가 Brief (hybrid category-as-hint)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
os.environ.setdefault("PIPELINE_PROGRESS", "1")
os.environ["CHUNKER_LLM_MAX_CONCURRENCY"] = "15"
os.environ["CHUNK_ENRICH_MAX_CONCURRENCY"] = "15"

from peter_parser.graph.flow import PipelineFlow

PDFS = [
    "docs/input/프로메가 Brief_240923_수정.pdf",
    "docs/input/HV-A00-000100 일반공통사항.pdf",
]


def run(pdf_rel: str) -> None:
    pdf_path = project_root / pdf_rel
    if not pdf_path.exists():
        print(f"Skip (not found): {pdf_rel}")
        return
    document = pdf_path.read_bytes()
    flow = PipelineFlow()
    result = flow.invoke(document, document_type="heading")
    chunks = result.get("chunks") or []
    empty = sum(1 for c in chunks if not (c.chunk or "").strip())
    print(f"\n=== {pdf_path.name} ===")
    print(f"총 청크: {len(chunks)}, 빈 청크: {empty}")
    for i, c in enumerate(chunks[:15]):
        extra = getattr(c.metadata, "extra", {}) or {}
        hp = extra.get("heading_path", [])
        print(f"  [{i}] heading_path={hp}, len={len(c.chunk)}")
    if len(chunks) > 15:
        print(f"  ... ({len(chunks)} total)")


if __name__ == "__main__":
    for rel in PDFS:
        run(rel)
    print("\nOK")
