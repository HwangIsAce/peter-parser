#!/usr/bin/env python3
"""Test lifelog_sample.pdf routing and final result generation."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def main() -> None:
    import os
    os.environ.setdefault("PIPELINE_PROGRESS", "1")
    from peter_parser.graph.flow import PipelineFlow
    from peter_parser.common.config import Config

    if not Config.UPSTAGE_API_KEY:
        print("ERROR: UPSTAGE_API_KEY not set.")
        sys.exit(1)

    path = project_root / "docs" / "input" / "lifelog_sample.pdf"
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)

    print(f"Testing: {path.name}")
    print(f"Expected document_type: lifelog")
    print("-" * 50)

    flow = PipelineFlow()
    document = path.read_bytes()
    result = flow.invoke(document, document_type="lifelog")

    dt = result.get("document_type", "?")
    chunks = result.get("chunks") or []
    export_json = result.get("export_json", "")

    print(f"document_type: {dt}")
    print(f"chunks: {len(chunks)}")
    print(f"export_json length: {len(export_json) if export_json else 0} bytes")
    print()
    status = "OK" if dt == "lifelog" else f"MISMATCH (expected lifelog, got {dt})"
    print(f"Status: {status}")
    if chunks:
        print(f"First chunk keys: {list(chunks[0].keys())}")
    print("Done.")

if __name__ == "__main__":
    main()
