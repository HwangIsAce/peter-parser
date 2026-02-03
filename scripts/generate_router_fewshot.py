"""Generate few-shot images for VLM router from docs/input PDFs.

Run from project root:
  uv run python scripts/generate_router_fewshot.py

Writes to assets/router_fewshot/heading/, slide/, lifelog/ (1-2 pages per PDF).
"""
from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from peter_parser.common.document_render import document_to_page_images

DOCS_INPUT = project_root / "docs" / "input"
OUT_BASE = project_root / "assets" / "router_fewshot"

# PDF filename (in docs/input) -> document_type for few-shot
MAPPING = [
    ("HV-A00-000100 일반공통사항.pdf", "heading"),
    ("[다사]올리브영_뉴 헬리티지 캠페인_0708_F.pdf", "slide"),
    ("lifelog_sample.pdf", "lifelog"),
]


def main() -> None:
    for filename, doc_type in MAPPING:
        path = DOCS_INPUT / filename
        if not path.exists():
            print(f"Skip (not found): {path}")
            continue
        doc_bytes = path.read_bytes()
        images = document_to_page_images(doc_bytes, max_pages=2, sample="uniform")
        if not images:
            print(f"Skip (no images): {path}")
            continue
        out_dir = OUT_BASE / doc_type
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(images):
            out_path = out_dir / f"page_{i}.png"
            out_path.write_bytes(img)
            print(f"Wrote {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()
