"""Prompt templates."""
from peter_parser.prompts.structured_output import (
    STRUCTURED_OUTPUT_SYSTEM_PROMPT,
    STRUCTURED_OUTPUT_PROMPT,
)
from peter_parser.prompts.enrichment import (
    DOCUMENT_SUMMARY_PROMPT,
    PAGE_SCRIPT_PROMPT,
)
from peter_parser.prompts.chunking import (
    BOUNDARY_DETECTION_SYSTEM_PROMPT,
    BOUNDARY_DETECTION_USER_PROMPT,
)

__all__ = [
    "STRUCTURED_OUTPUT_SYSTEM_PROMPT",
    "STRUCTURED_OUTPUT_PROMPT",
    "DOCUMENT_SUMMARY_PROMPT",
    "PAGE_SCRIPT_PROMPT",
    "BOUNDARY_DETECTION_SYSTEM_PROMPT",
    "BOUNDARY_DETECTION_USER_PROMPT",
]