"""Tests for parse/status/result API (mocked Redis/RQ)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
src_path = project_root / "src"
import sys
sys.path.insert(0, str(src_path))

from fastapi.testclient import TestClient

from peter_parser.api.main import app
from peter_parser.api.schemas.response import ParseResponse, ResultResponse, StatusResponse


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_queue_and_redis():
    """Mock get_queue and get_connection so no real Redis needed."""
    fake_job = MagicMock()
    fake_job.id = "test-job-123"
    fake_job.is_queued = True
    fake_job.is_started = False
    fake_job.is_finished = False
    fake_job.is_failed = False
    fake_job.exc_string = None
    fake_job.created_at = datetime.now(timezone.utc)

    fake_queue = MagicMock()
    fake_queue.enqueue.return_value = fake_job

    fake_conn = MagicMock()
    fake_conn.get.return_value = None

    with patch("peter_parser.api.routes.pipeline.get_queue", return_value=fake_queue), \
         patch("peter_parser.api.routes.pipeline.get_connection", return_value=fake_conn):
        yield {"queue": fake_queue, "conn": fake_conn, "job": fake_job}


def test_parse_upload_returns_job_id(client, mock_queue_and_redis):
    """POST /parse returns job_id and status pending."""
    pdf_content = b"%PDF-1.4 fake pdf"
    response = client.post("/parse", files={"file": ("doc.pdf", pdf_content, "application/pdf")})
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert data["job_id"] == "test-job-123"


def test_parse_upload_rejects_non_pdf(client, mock_queue_and_redis):
    """POST /parse without PDF returns 400."""
    response = client.post("/parse", files={"file": ("doc.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def test_status_returns_pending(client, mock_queue_and_redis):
    """GET /status/{job_id} returns status."""
    mock_queue_and_redis["job"].is_queued = True
    mock_queue_and_redis["job"].is_finished = False
    with patch("peter_parser.api.routes.pipeline.RQJob") as RQJob:
        RQJob.fetch.return_value = mock_queue_and_redis["job"]
        response = client.get("/status/test-job-123")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "test-job-123"
    assert data["status"] == "pending"


def test_status_returns_404_for_unknown_job(client, mock_queue_and_redis):
    """GET /status/{job_id} returns 404 for unknown job."""
    with patch("peter_parser.api.routes.pipeline.RQJob") as RQJob:
        RQJob.fetch.side_effect = Exception("Job not found")
        response = client.get("/status/unknown-id")
    assert response.status_code == 404


def test_result_returns_400_when_not_completed(client, mock_queue_and_redis):
    """GET /result/{job_id} returns 400 when job not finished."""
    mock_queue_and_redis["job"].is_finished = False
    with patch("peter_parser.api.routes.pipeline.RQJob") as RQJob:
        RQJob.fetch.return_value = mock_queue_and_redis["job"]
        response = client.get("/result/test-job-123")
    assert response.status_code == 400


def test_result_returns_chunks_when_completed(client, mock_queue_and_redis):
    """GET /result/{job_id} returns chunks when job finished."""
    mock_queue_and_redis["job"].is_finished = True
    stored = {"chunks": [{"uuid": "c1", "doc_title": "Doc", "chunk": "Hello.", "chunk_order": 0, "metadata": {}}]}
    mock_queue_and_redis["conn"].get.return_value = json.dumps(stored)
    with patch("peter_parser.api.routes.pipeline.RQJob") as RQJob:
        RQJob.fetch.return_value = mock_queue_and_redis["job"]
        response = client.get("/result/test-job-123")
    assert response.status_code == 200
    data = response.json()
    assert "chunks" in data
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["uuid"] == "c1"
    assert data["chunks"][0]["chunk"] == "Hello."


def test_result_returns_404_for_unknown_job(client, mock_queue_and_redis):
    """GET /result/{job_id} returns 404 for unknown job."""
    with patch("peter_parser.api.routes.pipeline.RQJob") as RQJob:
        RQJob.fetch.side_effect = Exception("Job not found")
        response = client.get("/result/unknown-id")
    assert response.status_code == 404


def test_mapper_chunk_to_result_item():
    """Chunk -> ResultItem mapper produces spec-compliant structure."""
    from peter_parser.api.schemas.mappers import chunk_to_result_item
    from peter_parser_core.common.types import Chunk, ChunkMetadata

    c = Chunk(
        uuid="u1",
        doc_title="Doc",
        chunk="Text.",
        chunk_order=0,
        metadata=ChunkMetadata(chunk_size=5, extra={"page_numbers": [1, 2]}),
    )
    item = chunk_to_result_item(c)
    assert item.uuid == "u1"
    assert item.doc_title == "Doc"
    assert item.chunk == "Text."
    assert item.chunk_order == 0
    assert item.metadata.doc_page == [1, 2]
