#!/usr/bin/env python3
"""
Seed VLM chunker prompts from code into Redis. Run once per environment (e.g. after deploy).
Usage: uv run python scripts/seed_vlm_prompts.py
Requires: REDIS_URL set (or default redis://localhost:6379/0).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on path when run as script.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from peter_parser.common.prompt_store import (
    set_prompt,
    PROMPT_KEY_VLM_BOUNDARY_SYSTEM,
    PROMPT_KEY_VLM_BOUNDARY_USER,
)
from peter_parser.prompts.chunking import (
    BOUNDARY_DETECTION_SYSTEM_PROMPT,
    BOUNDARY_DETECTION_USER_PROMPT,
)


def main() -> None:
    set_prompt(PROMPT_KEY_VLM_BOUNDARY_SYSTEM, BOUNDARY_DETECTION_SYSTEM_PROMPT)
    set_prompt(PROMPT_KEY_VLM_BOUNDARY_USER, BOUNDARY_DETECTION_USER_PROMPT)
    print("Seeded prompt:vlm:boundary_system and prompt:vlm:boundary_user")


if __name__ == "__main__":
    main()
