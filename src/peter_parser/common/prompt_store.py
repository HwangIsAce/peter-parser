"""Prompt store: runtime source for prompts (Redis). Used by VLMChunker."""
from __future__ import annotations

from typing import Optional

from peter_parser.common.queue import get_connection

# Redis keys for VLM chunker boundary detection prompts.
PROMPT_KEY_VLM_BOUNDARY_SYSTEM = "prompt:vlm:boundary_system"
PROMPT_KEY_VLM_BOUNDARY_USER = "prompt:vlm:boundary_user"


def get_prompt(name: str) -> Optional[str]:
    """Get prompt content from Redis. Returns None if key is missing."""
    conn = get_connection()
    value = conn.get(name)
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def set_prompt(name: str, content: str) -> None:
    """Store prompt content in Redis."""
    conn = get_connection()
    conn.set(name, content)
