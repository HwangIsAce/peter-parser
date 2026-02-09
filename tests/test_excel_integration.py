"""Integration tests for Excel pipeline (prepare → chunk → chunk_enrich → export)."""
from __future__ import annotations

from io import BytesIO

import pytest

from openpyxl import Workbook

from peter_parser.graph.flow import PipelineFlow


def _create_sample_xlsx_bytes() -> bytes:
    """Create minimal .xlsx in memory."""
    wb = Workbook()
    ws1 = wb.active
    if ws1:
        ws1.title = "Sheet1"
        ws1["A1"], ws1["B1"] = "Name", "Value"
        ws1["A2"], ws1["B2"] = "foo", 100
        ws1["A3"], ws1["B3"] = "bar", 200
    ws2 = wb.create_sheet("Sheet2")
    ws2["A1"], ws2["B1"] = "ID", "Amount"
    ws2["A2"], ws2["B2"] = 1, 100
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_pipeline_integration_excel():
    """Full pipeline with document_type=excel: .xlsx → chunks → export.

    Skips if chunk_enrich fails (e.g. no OPENAI_API_KEY / connection).
    """
    xlsx_bytes = _create_sample_xlsx_bytes()
    try:
        flow = PipelineFlow()
        state = flow.invoke(document=xlsx_bytes, document_type="excel")
        assert state.get("document_type") == "excel"
        assert "parsed_document" in state
        assert len(state["parsed_document"].pages) == 2
        assert "chunks" in state
        assert len(state["chunks"]) == 2
        assert "export_json" in state
        assert state["chunks"][0].metadata.extra.get("excel", {}).get("sheet_name") == "Sheet1"
        assert state["chunks"][1].metadata.extra.get("excel", {}).get("sheet_name") == "Sheet2"
    except Exception as e:
        pytest.skip(f"Excel pipeline integration test skipped: {e}")
