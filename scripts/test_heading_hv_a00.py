#!/usr/bin/env python3
"""Test heading pipeline on HV-A00-000100 일반공통사항.pdf"""
from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
os.environ.setdefault("PIPELINE_PROGRESS", "1")

from peter_parser.graph.flow import PipelineFlow

pdf_path = project_root / "docs/input/HV-A00-000100 일반공통사항.pdf"
document = pdf_path.read_bytes()

flow = PipelineFlow()
result = flow.invoke(document, document_type="heading")

chunks = result.get("chunks") or []
print(f"총 청크 수: {len(chunks)}")
for i, c in enumerate(chunks[:8]):
    extra = getattr(c.metadata, "extra", {}) or {}
    hp = extra.get("heading_path", [])
    print(f"  [{i}] heading_path={hp}, chunk 길이={len(c.chunk)}")
print("OK")
