#!/usr/bin/env python3
"""
Call real API (POST /parse, GET /status, GET /result) for each PDF in docs/input,
measure duration, and write results to docs/output.
Requires: API server and RQ worker running (Redis, uvicorn, worker).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "docs" / "input"
OUTPUT_DIR = ROOT / "docs" / "output"
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
POLL_INTERVAL = 3
JOB_TIMEOUT = 600  # seconds per job


def find_input_pdfs():
    return sorted(INPUT_DIR.glob("*.pdf"))


def run_one(path: Path, session, output_dir: Path) -> dict:
    """POST /parse, poll /status until completed/failed, GET /result; return result dict.
    When completed, writes full result (chunks) to output_dir as {stem}_result.json."""
    name = path.name
    stem = path.stem
    result = {
        "file": name,
        "job_id": None,
        "status": None,
        "duration_sec": None,
        "num_chunks": 0,
        "error": None,
        "result_file": None,
    }
    start = time.perf_counter()
    try:
        with open(path, "rb") as f:
            files = {"file": (name, f, "application/pdf")}
            r = session.post(f"{BASE_URL}/parse", files=files, timeout=30)
        r.raise_for_status()
        data = r.json()
        job_id = data.get("job_id")
        result["job_id"] = job_id
        if not job_id:
            result["error"] = "No job_id in response"
            result["duration_sec"] = round(time.perf_counter() - start, 2)
            return result

        # Poll status until completed or failed or timeout
        deadline = start + JOB_TIMEOUT
        while time.perf_counter() < deadline:
            r = session.get(f"{BASE_URL}/status/{job_id}", timeout=10)
            r.raise_for_status()
            st = r.json()
            result["status"] = st.get("status")
            if result["status"] in ("completed", "failed"):
                break
            time.sleep(POLL_INTERVAL)

        result["duration_sec"] = round(time.perf_counter() - start, 2)

        if result["status"] == "completed":
            r = session.get(f"{BASE_URL}/result/{job_id}", timeout=30)
            r.raise_for_status()
            res_data = r.json()
            chunks = res_data.get("chunks") or []
            result["num_chunks"] = len(chunks)
            # Write full result to docs/output
            safe_stem = "".join(c if c.isalnum() or c in "._- " else "_" for c in stem)
            result_filename = f"{safe_stem}_result.json"
            result_path = output_dir / result_filename
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(res_data, f, ensure_ascii=False, indent=2)
            result["result_file"] = result_filename
        elif result["status"] == "failed":
            # Optionally fetch status again for exc_string
            r = session.get(f"{BASE_URL}/status/{job_id}", timeout=10)
            if r.ok:
                result["error"] = r.json().get("error")
        elif result["status"] is None:
            result["error"] = "Timeout waiting for job"
    except Exception as e:
        result["duration_sec"] = round(time.perf_counter() - start, 2)
        result["error"] = str(e)
    return result


def main():
    import requests

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = find_input_pdfs()
    if not pdfs:
        print("No PDFs in docs/input", file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers["Accept"] = "application/json"
    results = []
    for path in pdfs:
        print(f"Testing: {path.name} ...")
        r = run_one(path, session, OUTPUT_DIR)
        results.append(r)
        if r.get("error"):
            print(f"  {r['status']} in {r['duration_sec']}s: {r['error']}")
        else:
            out = f"  {r['status']} in {r['duration_sec']}s, {r['num_chunks']} chunks"
            if r.get("result_file"):
                out += f" -> {r['result_file']}"
            print(out)

    # Summary without large payloads
    summary = [
        {
            "file": r["file"],
            "job_id": r["job_id"],
            "status": r["status"],
            "duration_sec": r["duration_sec"],
            "num_chunks": r["num_chunks"],
            "result_file": r.get("result_file"),
            "error": r.get("error"),
        }
        for r in results
    ]
    report = {"run_at": datetime.now().isoformat(), "base_url": BASE_URL, "results": summary}

    report_json = OUTPUT_DIR / "report.json"
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Wrote {report_json}")

    report_md = OUTPUT_DIR / "report.md"
    lines = [
        "# API test report (docs/input)",
        "",
        f"Run at: {report['run_at']}",
        f"Base URL: {BASE_URL}",
        "",
        "| File | job_id | Status | Duration (s) | Chunks | Result file | Error |",
        "|------|--------|--------|--------------|--------|-------------|-------|",
    ]
    for r in summary:
        err = (r.get("error") or "")[:60]
        result_file = r.get("result_file") or "-"
        lines.append(
            f"| {r['file']} | {r['job_id'] or '-'} | {r['status'] or '-'} | {r['duration_sec']} | {r['num_chunks']} | {result_file} | {err} |"
        )
    with open(report_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {report_md}")

    return 0 if all(r.get("status") == "completed" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
