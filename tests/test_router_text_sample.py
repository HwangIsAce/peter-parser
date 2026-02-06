"""Unit tests for sample_router_text."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from peter_parser.common.router_text_sample import sample_router_text


def test_sample_router_text_no_pages_uses_content():
    """When parsed_document has no pages, uses content.text."""
    parsed = MagicMock()
    parsed.pages = []
    parsed.content = MagicMock()
    parsed.content.text = "Full document text here"
    result = sample_router_text(parsed, max_pages=5, sample="random")
    assert result == "Full document text here"


def test_sample_router_text_empty_content():
    """When no pages and empty content, returns empty string."""
    parsed = MagicMock()
    parsed.pages = []
    parsed.content = MagicMock()
    parsed.content.text = ""
    result = sample_router_text(parsed, max_pages=5)
    assert result == ""


def test_sample_router_text_with_pages_random():
    """With pages, samples up to max_pages."""
    page1 = MagicMock()
    page1.text = "Page 1 text"
    page2 = MagicMock()
    page2.text = "Page 2 text"
    page3 = MagicMock()
    page3.text = "Page 3 text"
    parsed = MagicMock()
    parsed.pages = [page1, page2, page3]
    result = sample_router_text(parsed, max_pages=2, sample="random")
    # Should contain 2 page texts (order may vary with random)
    parts = result.split("\n\n")
    assert len(parts) <= 2
    assert all(p in ["Page 1 text", "Page 2 text", "Page 3 text"] for p in parts)


def test_sample_router_text_with_pages_uniform():
    """With pages and uniform sampling, picks evenly spaced pages."""
    pages = [MagicMock(text=f"Page {i+1}") for i in range(10)]
    parsed = MagicMock()
    parsed.pages = pages
    result = sample_router_text(parsed, max_pages=3, sample="uniform")
    parts = result.split("\n\n")
    assert len(parts) == 3
    assert "Page 1" in parts[0]
    assert "Page 5" in parts[1] or "Page 6" in parts[1]
    assert "Page 10" in parts[2]


def test_sample_router_text_respects_max_chars():
    """Result is truncated to max_chars."""
    parsed = MagicMock()
    parsed.pages = []
    parsed.content = MagicMock()
    parsed.content.text = "x" * 1000
    result = sample_router_text(parsed, max_pages=5, max_chars=100)
    assert len(result) == 100
    assert result == "x" * 100
