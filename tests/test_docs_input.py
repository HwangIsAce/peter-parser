"""Tests using real PDFs from docs/input (document_render, routing, optional full pipeline)."""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

DOCS_INPUT = project_root / "docs" / "input"

# Expected document_type per docs/input PDF
# HV-A00 → heading, 올리브영 → slide, lifelog_sample → lifelog
EXPECTED_DOCUMENT_TYPE: dict[str, str] = {
    "[다사]올리브영_뉴 헤리티지 캠페인_0708_F.pdf": "slide",
    "HV-A00-000100 일반공통사항.pdf": "heading",
    "lifelog_sample.pdf": "lifelog",
}
# Fallback by sorted filename order: HV-A00 (heading), [다사] (slide), lifelog (lifelog)
EXPECTED_ORDER: list[str] = ["heading", "slide", "lifelog"]


def _docs_input_pdfs() -> list[Path]:
    """Return list of PDF paths in docs/input (for tests that need real data)."""
    if not DOCS_INPUT.is_dir():
        return []
    return sorted(DOCS_INPUT.glob("*.pdf"))


# -----------------------------------------------------------------------------
# document_render (no API)
# -----------------------------------------------------------------------------


def test_document_render_docs_input_pdfs():
    """document_to_page_images returns non-empty PNG list for each docs/input PDF."""
    from peter_parser.common.document_render import document_to_page_images

    pdfs = _docs_input_pdfs()
    assert pdfs, "docs/input has no PDFs; add at least one for this test"
    for path in pdfs:
        doc = path.read_bytes()
        images = document_to_page_images(doc, max_pages=3, sample="uniform")
        assert isinstance(images, list), f"{path.name}: expected list"
        assert len(images) >= 1, f"{path.name}: expected at least 1 image"
        for img in images:
            assert isinstance(img, bytes), f"{path.name}: image should be bytes"
            assert img[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name}: expected PNG magic"


# -----------------------------------------------------------------------------
# Full pipeline with docs/input PDF (document_type provided by caller)
# -----------------------------------------------------------------------------


@pytest.mark.timeout(600)
def test_full_pipeline_docs_input_one_pdf():
    """Full pipeline (parse → chunk → …) with one docs/input PDF. Requires API keys."""
    import os
    os.environ["PIPELINE_PROGRESS"] = "1"
    from peter_parser.graph.flow import PipelineFlow
    from peter_parser.common.config import Config

    pdfs = _docs_input_pdfs()
    if not pdfs:
        return
    if not Config.UPSTAGE_API_KEY:
        return  # skip without parse API
    path = pdfs[0]
    document = path.read_bytes()
    name = path.name
    name_nfc = unicodedata.normalize("NFC", name)
    document_type = EXPECTED_DOCUMENT_TYPE.get(name) or EXPECTED_DOCUMENT_TYPE.get(name_nfc) or "plain"
    flow = PipelineFlow()
    result = flow.invoke(document, document_type=document_type)
    assert result.get("document_type") in ("heading", "plain", "slide", "lifelog")
    assert "chunks" in result
    assert isinstance(result["chunks"], list)
    assert len(result["chunks"]) >= 1, "expected at least one chunk"
    assert "export_json" in result
    assert "parsed_document" in result


def _run_full_pipeline_for_one_pdf(pdf_index: int) -> None:
    """Run full pipeline for a single PDF at docs/input (by sorted index)."""
    import os
    os.environ["PIPELINE_PROGRESS"] = "1"
    from peter_parser.graph.flow import PipelineFlow
    from peter_parser.common.config import Config

    pdfs = _docs_input_pdfs()
    if len(pdfs) < 3:
        pytest.skip(msg="docs/input has fewer than 3 PDFs")
    if not Config.UPSTAGE_API_KEY:
        pytest.skip(msg="UPSTAGE_API_KEY not set")
    if pdf_index >= len(pdfs):
        pytest.skip(msg=f"pdf_index {pdf_index} >= len(pdfs) {len(pdfs)}")

    path = pdfs[pdf_index]
    name = path.name
    name_nfc = unicodedata.normalize("NFC", name)
    expected_dt = EXPECTED_DOCUMENT_TYPE.get(name) or EXPECTED_DOCUMENT_TYPE.get(name_nfc) or (
        EXPECTED_ORDER[pdf_index] if pdf_index < len(EXPECTED_ORDER) else "plain"
    )
    flow = PipelineFlow()
    document = path.read_bytes()
    result = flow.invoke(document, document_type=expected_dt)
    dt = result.get("document_type")
    valid_types = ("heading", "plain", "slide", "lifelog")
    assert dt in valid_types, f"document_type {dt!r} not in {valid_types}"
    if expected_dt is not None and dt != expected_dt:
        print(f"  [warn] {name}: expected document_type={expected_dt!r}, got {dt!r}")
    chunks = result.get("chunks") or []
    assert isinstance(chunks, list), "chunks must be list"
    assert len(chunks) >= 1, f"expected at least one chunk, got {len(chunks)}"
    assert "export_json" in result, "missing export_json"
    assert "parsed_document" in result, "missing parsed_document"
    print(f"  {name} -> document_type={dt} (expected {expected_dt}), chunks={len(chunks)}")


@pytest.mark.timeout(600)
def test_full_pipeline_docs_input_pdf_0():
    """Full pipeline for 1st PDF in docs/input (sorted). Run separately to avoid long single test."""
    _run_full_pipeline_for_one_pdf(0)


@pytest.mark.timeout(600)
def test_full_pipeline_docs_input_pdf_1():
    """Full pipeline for 2nd PDF in docs/input (sorted)."""
    _run_full_pipeline_for_one_pdf(1)


@pytest.mark.timeout(600)
def test_full_pipeline_docs_input_pdf_2():
    """Full pipeline for 3rd PDF in docs/input (sorted)."""
    _run_full_pipeline_for_one_pdf(2)
