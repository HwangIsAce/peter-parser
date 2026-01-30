"""Response schemas for parse/status/result API."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ParseResponse(BaseModel):
    """POST /parse response."""

    job_id: str
    status: str = "pending"


class StatusResponse(BaseModel):
    """GET /status/{job_id} response."""

    job_id: str
    status: str  # pending | processing | completed | failed
    error: Optional[str] = None
    created_at: str  # ISO 8601


class ResultImageItem(BaseModel):
    """Single image in result metadata (API spec)."""

    uuid: str = ""
    file: str = ""
    image_path: str = ""
    image_title: str = ""
    image_context: str = ""
    image_type: str = ""
    image_keywords: List[str] = Field(default_factory=list)
    potential_questions: List[str] = Field(default_factory=list)
    page: str = ""


class ResultItemMetadata(BaseModel):
    """Result item metadata (API spec)."""

    proj_title: str = ""
    doc_title: str = ""
    process_title: str = ""
    doc_unit: str = ""
    doc_page: List[int] = Field(default_factory=list)
    category: List[str] = Field(default_factory=list)
    images: List[ResultImageItem] = Field(default_factory=list)


class ResultItem(BaseModel):
    """Single chunk in GET /result response (API spec)."""

    uuid: str = ""
    doc_title: str = ""
    chunk: str = ""
    chunk_order: int = 0
    metadata: ResultItemMetadata = Field(default_factory=ResultItemMetadata)


class ResultResponse(BaseModel):
    """GET /result/{job_id} response: array of chunks."""

    chunks: List[ResultItem] = Field(default_factory=list)
