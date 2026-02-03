"""Adapter to run llm-chunker-optimizer and write VLM prompts to Redis."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from peter_parser.common.prompt_store import (
    get_prompt,
    set_prompt,
    PROMPT_KEY_VLM_BOUNDARY_SYSTEM,
    PROMPT_KEY_VLM_BOUNDARY_USER,
)
from peter_parser.prompts.chunking import (
    BOUNDARY_DETECTION_SYSTEM_PROMPT,
    BOUNDARY_DETECTION_USER_PROMPT,
)

try:
    from chunker_optimizer.domain.entities.chunk import Chunk as OptimizerChunk
    from chunker_optimizer.domain.entities.prompt import Prompt as OptimizerPrompt
    from chunker_optimizer.application.use_cases.evaluate_chunks import EvaluateChunksUseCase
    from chunker_optimizer.application.use_cases.optimize_prompt import OptimizePromptUseCase
    from chunker_optimizer.infrastructure.llm.openai_client import OpenAIClient

    _OPTIMIZER_AVAILABLE = True
except ImportError:
    _OPTIMIZER_AVAILABLE = False
    OptimizerChunk = None
    OptimizerPrompt = None
    EvaluateChunksUseCase = None
    OptimizePromptUseCase = None
    OpenAIClient = None


def _snapshot_chunks_to_optimizer(snapshot: Dict[str, Any]) -> Tuple[List[Any], str]:
    """Convert JobSnapshot chunks to optimizer Chunk list and original_text."""
    if not _OPTIMIZER_AVAILABLE:
        raise RuntimeError(
            "llm-chunker-optimizer is not installed. "
            "Install with: uv sync --extra optimizer"
        )
    chunks_in = snapshot.get("chunks") or []
    parts: List[str] = []
    optimizer_chunks: List[Any] = []
    start = 0
    for i, c in enumerate(chunks_in):
        text = c.get("chunk") or c.get("content") or ""
        if not text.strip():
            text = " "
        end = start + len(text)
        ch_id = c.get("uuid") or str(i)
        optimizer_chunks.append(
            OptimizerChunk(
                id=ch_id,
                content=text,
                start_index=start,
                end_index=end,
                metadata={
                    "chunk_order": i,
                    "doc_title": c.get("doc_title", ""),
                    **(c.get("metadata") or {}),
                },
            )
        )
        parts.append(text)
        start = end + 2  # "\n\n"
    original_text = "\n\n".join(parts)
    return optimizer_chunks, original_text


def run_optimization_and_save_prompts(
    snapshots: List[Dict[str, Any]],
    *,
    openai_model: Optional[str] = None,
) -> None:
    """
    Evaluate chunks from snapshots, run one prompt optimization, write both
    VLM prompts to Redis. Uses current Redis/code prompts as initial;
    optimizes the user prompt and keeps system prompt as-is.

    Args:
        snapshots: List of job snapshot dicts (from job_snapshot:{job_id}).
        openai_model: Optional OpenAI model for OptimizePromptUseCase.
    """
    if not _OPTIMIZER_AVAILABLE:
        raise RuntimeError(
            "llm-chunker-optimizer is not installed. "
            "Install with: uv sync --extra optimizer"
        )
    if not snapshots:
        return

    all_chunks: List[Any] = []
    all_texts: List[str] = []
    for s in snapshots:
        oc, orig = _snapshot_chunks_to_optimizer(s)
        all_chunks.extend(oc)
        all_texts.append(orig)
    original_text = "\n\n".join(all_texts)

    if not all_chunks:
        return

    evaluate_use_case = EvaluateChunksUseCase()
    metrics = evaluate_use_case.execute(all_chunks, original_text)

    system_content = get_prompt(PROMPT_KEY_VLM_BOUNDARY_SYSTEM) or BOUNDARY_DETECTION_SYSTEM_PROMPT
    user_content = get_prompt(PROMPT_KEY_VLM_BOUNDARY_USER) or BOUNDARY_DETECTION_USER_PROMPT

    llm_client = OpenAIClient(model=openai_model or "gpt-4")
    optimize_use_case = OptimizePromptUseCase(llm_client=llm_client)
    current_prompt = OptimizerPrompt(id="vlm_boundary_user", content=user_content, version=1)
    new_prompt = optimize_use_case.execute(
        current_prompt,
        metrics,
        all_chunks,
        0,
    )

    set_prompt(PROMPT_KEY_VLM_BOUNDARY_SYSTEM, system_content)
    set_prompt(PROMPT_KEY_VLM_BOUNDARY_USER, new_prompt.content)
