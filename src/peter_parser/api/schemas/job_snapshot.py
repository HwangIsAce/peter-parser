"""Job snapshot schema: single per-job payload for API + optimizer consumption."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Redis list key for slide job ids (consumed by optimization batch).
SLIDE_JOB_QUEUE = "slide_job_queue"


class JobSnapshot(BaseModel):
    """One job's result and context. Stored at job_snapshot:{job_id}."""

    job_id: str = Field(description="RQ job id")
    document_type: Optional[str] = Field(default=None, description="heading | plain | slide | lifelog")
    document_summary: Optional[str] = Field(default=None, description="Document-level summary (slide path)")
    item_metadata: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Element metadata; key is element_id as string for JSON",
    )
    chunk_boundaries: List[int] = Field(default_factory=list, description="Indices where new chunks start")
    chunks: List[Dict[str, Any]] = Field(default_factory=list, description="Chunks as serializable dicts")
    created_at: str = Field(description="ISO 8601 datetime UTC")

    @classmethod
    def from_state(cls, state: Dict[str, Any], job_id: str) -> "JobSnapshot":
        """Build snapshot from pipeline state. Keys are normalized for JSON (e.g. int -> str)."""
        # item_metadata: state has Dict[int, Dict] -> use string keys for JSON
        raw_meta = state.get("item_metadata") or {}
        item_metadata = {str(k): v for k, v in raw_meta.items()}

        chunks_raw = state.get("chunks") or []
        chunks: List[Dict[str, Any]] = []
        for c in chunks_raw:
            if hasattr(c, "model_dump"):
                chunks.append(c.model_dump())
            elif hasattr(c, "dict"):
                chunks.append(c.dict())
            else:
                chunks.append(dict(c))

        return cls(
            job_id=job_id,
            document_type=state.get("document_type"),
            document_summary=state.get("document_summary"),
            item_metadata=item_metadata,
            chunk_boundaries=list(state.get("chunk_boundaries") or []),
            chunks=chunks,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
