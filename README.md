# Peter Parser

Document processing pipeline with optimized modules.

## Pipeline flow

1. **parse** — Document (PDF, etc.) is parsed into a structured `ParsedDocument`.
2. **route** — Document type is set: either from `invoke(document_type=...)` or by an LLM router that classifies the content.
3. **Conditional branch** — Only `slide` → **enrich** (document summary + per-page title/script); `heading` / `plain` / `lifelog` → **chunk** directly.
4. **chunk** — Chunking by document type: HeadingPromptChunker (heading), LumberChunker (plain), VLMChunker (slide), LifelogChunker (lifelog).
5. **chunk_enrich** — Chunk-level metadata (summary, keywords).
6. **export** — Chunks are serialized to JSON in `state["export_json"]`.

## Document type (4-case routing)

| Type      | Description                                      | Path after route |
|-----------|--------------------------------------------------|------------------|
| `heading` | Structured docs with headings (papers, reports)  | chunk            |
| `plain`   | Unstructured text (notes, blog body)              | chunk            |
| `slide`   | Presentation / slide deck                        | enrich → chunk   |
| `lifelog` | 5W1H event-style daily log                       | chunk (LifelogChunker) |

## Heading chunking (heading documents)

For **heading** documents, the chunk stage uses **HeadingPromptChunker**: content is processed in windows of up to **10 pages** (configurable via `HEADING_CHUNK_MAX_PAGES`). An LLM identifies heading1 / heading2 / heading3 and outputs chunk boundaries by segment (element) index.

- **Input:** Parsed document with `elements` and `pages`; no prior enrichment.
- **Output:** Chunks with element-based boundaries. Each chunk’s `metadata.extra` includes:
  - `heading1`, `heading2`, `heading3` — current heading titles (empty string if absent).
  - `heading_path` — list of non-empty headings, e.g. `["Chapter 1", "1.1 Section"]`.
- **API:** When `heading_path` is present, it is exposed as `ResultItem.metadata.category` so clients can use the heading hierarchy for navigation or filtering.

## Dynamic prompt optimization (slide / VLMChunker only)

Only the **slide** branch’s **chunk** stage is optimized: the two prompts used by **VLMChunker** (`prompt:vlm:boundary_system`, `prompt:vlm:boundary_user`) are loaded from Redis and can be updated by a background batch job that runs the **llm-chunker-optimizer** on collected slide job snapshots.

- **In scope:** slide → enrich → **chunk (VLMChunker)** → chunk_enrich → export; the two boundary-detection prompts above.
- **Out of scope:** enrich prompts, chunk_enrich prompts, **LumberChunker**, **LifelogChunker**, and all other prompts remain unchanged (code/constants).

Flow: slide jobs push `job_id` to `slide_job_queue`; a batch job (e.g. cron) runs `run_vlm_chunk_optimization_batch`, which pops snapshots, evaluates chunks, optimizes the user prompt, and writes both prompts to Redis so the next slide chunk run uses them without restart.

### Setup and trigger

- Install optimizer: `uv sync --extra optimizer`
- Seed prompts once: `uv run python scripts/seed_vlm_prompts.py`
- Enqueue batch (cron or manual): `uv run python scripts/enqueue_vlm_optimization_batch.py`

### Config (env)

| Variable | Description | Default |
|----------|-------------|---------|
| `VLM_OPT_BATCH_SIZE` | Max slide job snapshots per batch | `10` |
| `VLM_OPT_OPENAI_MODEL` | Model used for prompt optimization | `gpt-4` |

Requires `OPENAI_API_KEY` and Redis (`REDIS_URL`) for the optimizer batch.

## Architecture

![Architecture](assets/image.png)

