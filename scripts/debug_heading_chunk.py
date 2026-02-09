#!/usr/bin/env python3
"""Debug heading chunker: inspect document structure and what's sent to LLM."""
from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
os.environ.setdefault("PIPELINE_PROGRESS", "1")

# Parse only (no chunking) - fast
from peter_parser.impl.parser.upstage import UpstageParser
from peter_parser.common.config import Config
from peter_parser.impl.chunker.heading import (
    build_heading_windows,
    _elements_in_page_range,
)

pdf_path = project_root / "docs/input/HV-A00-000100 일반공통사항.pdf"
document = pdf_path.read_bytes()

print("=" * 60)
print("1. Upstage Parse")
print("=" * 60)
parser = UpstageParser(
    api_key=Config.UPSTAGE_API_KEY,
    api_url=Config.UPSTAGE_API_URL,
)
parsed_doc = parser.parse(document)

pages = getattr(parsed_doc, "pages", []) or []
elements = getattr(parsed_doc, "elements", []) or []

print(f"  pages: {len(pages)}")
print(f"  elements: {len(elements)}")

if pages:
    print(f"  page numbers (first 5): {[p.page_number for p in pages[:5]]}")
    print(f"  page numbers (last 5):  {[p.page_number for p in pages[-5:]]}")
    print(f"  page[0].text length: {len(pages[0].text) if pages[0].text else 0}")
    print(f"  page[0].text preview (200 chars): {repr((pages[0].text or '')[:200])}")

if elements:
    print(f"\n  element page_number distribution:")
    from collections import Counter
    pn_dist = Counter(getattr(el, "page_number", 0) for el in elements)
    for pn, cnt in sorted(pn_dist.items())[:10]:
        print(f"    page {pn}: {cnt} elements")
    if len(pn_dist) > 10:
        print(f"    ... ({len(pn_dist)} pages total)")

    print(f"\n  element text length (first 10): {[len(getattr(el, 'text', '') or '') for el in elements[:10]]}")
    print(f"  element[0] category: {getattr(elements[0], 'category', getattr(elements[0], 'type', '?'))}")
    print(f"  element[0].text preview: {repr((getattr(elements[0], 'text', '') or '')[:150])}")

print("\n" + "=" * 60)
print("2. Heading Windows")
print("=" * 60)
windows = build_heading_windows(pages, max_pages=10)
print(f"  window count: {len(windows)}")
for i, (pstart, pend, text) in enumerate(windows):
    print(f"  window[{i}]: pages {pstart}-{pend-1} (0-based), text len={len(text)}")

print("\n" + "=" * 60)
print("3. Elements per Window (_elements_in_page_range)")
print("=" * 60)
for win_idx, (page_start, page_end, _) in enumerate(windows):
    global_indices, window_elements = _elements_in_page_range(
        elements, page_start, page_end
    )
    print(f"  window[{win_idx}]: page_start={page_start}, page_end={page_end}")
    print(f"    -> global_indices count: {len(global_indices)}, window_elements count: {len(window_elements)}")
    if window_elements:
        text_sample = "\n".join(
            f"ID {i}: {(getattr(el, 'text', '') or '')[:80]}..."
            for i, el in enumerate(window_elements[:3])
        )
        print(f"    -> first 3 elements preview:\n{text_sample}")

print("\n" + "=" * 60)
print("4. Full text sent to LLM (first window, first 2000 chars)")
print("=" * 60)
if windows and elements:
    _, window_elements = _elements_in_page_range(elements, 0, min(10, len(pages)))
    full_text = "\n".join(
        f"ID {i}: {getattr(el, 'text', '') or ''}" for i, el in enumerate(window_elements)
    )
    print(f"  total length: {len(full_text)} chars")
    print(f"  preview:\n---\n{full_text[:2000]}\n---")

print("\nOK")
