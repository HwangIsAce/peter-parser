#!/usr/bin/env python3
"""Run full pipeline for each PDF in docs/input and print routing/chunk results.

Usage:
    uv run python scripts/run_full_pipeline_docs_input.py

Requires UPSTAGE_API_KEY and optional VLM/LLM endpoints for routing.
No timeout - run in terminal to see results for all docs/input PDFs.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

DOCS_INPUT = project_root / "docs" / "input"

# Expected document_type per docs/input PDF (for comparison)
# HV-A00 → heading, 올리브영 → slide, lifelog_sample → lifelog
EXPECTED_DOCUMENT_TYPE: dict[str, str] = {
    "[다사]올리브영_뉴 헤리티지 캠페인_0708_F.pdf": "slide",
    "HV-A00-000100 일반공통사항.pdf": "heading",
    "lifelog_sample.pdf": "lifelog",
}
# Fallback by sorted filename order: HV-A00 (heading), [다사] (slide), lifelog (lifelog)
EXPECTED_ORDER: list[str] = ["heading", "slide", "lifelog"]


def main() -> None:
    import os
    os.environ.setdefault("PIPELINE_PROGRESS", "1")  # show step progress during test

    from peter_parser.graph.flow import PipelineFlow
    from peter_parser.common.config import Config

    if not Config.UPSTAGE_API_KEY:
        print("ERROR: UPSTAGE_API_KEY not set. Set it in .env or environment.")
        sys.exit(1)

    # 요청이 나갈 서버 확인용 (Connection error 시 여기서 URL/키 확인)
    llm_url = Config.OPENAI_BASE_URL or "(비어있음 → 기본 OpenAI)"
    vlm_url = Config.OPENAI_VISION_BASE_URL or "(비어있음 → LLM과 동일)"
    print(f"LLM URL: {llm_url[:50]}..." if len(str(llm_url)) > 50 else f"LLM URL: {llm_url}")
    print(f"VLM URL: {vlm_url[:50]}..." if len(str(vlm_url)) > 50 else f"VLM URL: {vlm_url}")

    pdfs = sorted(DOCS_INPUT.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {DOCS_INPUT}")
        sys.exit(1)

    print(f"Running full pipeline for {len(pdfs)} PDF(s) in docs/input")
    print("=" * 60)

    flow = PipelineFlow()

    for idx, path in enumerate(pdfs):
        name = path.name
        name_nfc = unicodedata.normalize("NFC", name)
        expected = EXPECTED_DOCUMENT_TYPE.get(name) or EXPECTED_DOCUMENT_TYPE.get(name_nfc) or (
            EXPECTED_ORDER[idx] if idx < len(EXPECTED_ORDER) else "?"
        )

        print(f"\n[{idx + 1}/{len(pdfs)}] {name}")
        print(f"  Expected document_type: {expected}")

        try:
            document = path.read_bytes()
            result = flow.invoke(document)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        dt = result.get("document_type", "?")
        chunks = result.get("chunks") or []
        chunk_count = len(chunks)
        status = "OK" if dt == expected else "MISMATCH"

        print(f"  document_type: {dt} [{status}]")
        print(f"  chunks: {chunk_count}")
        if "export_json" in result:
            export_len = len(result["export_json"]) if result["export_json"] else 0
            print(f"  export_json length: {export_len} bytes")

        if dt != expected:
            print(f"  WARN: expected {expected}, got {dt}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
