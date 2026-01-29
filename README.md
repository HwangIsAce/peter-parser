# Peter Parser

Document processing pipeline with optimized modules.

## Pipeline flow

1. **parse** — Document (PDF, etc.) is parsed into a structured `ParsedDocument`.
2. **route** — Document type is set: either from `invoke(document_type=...)` or by an LLM router that classifies the content.
3. **Conditional branch** — `heading` / `slide` → **enrich** (extract summaries, page metadata); `plain` / `lifelog` → **chunk** directly.
4. **chunk** — Chunking by document type: LumberChunker (heading/plain), VLMChunker (slide), LifelogChunker (lifelog).
5. **chunk_enrich** — Chunk-level metadata (summary, keywords).
6. **export** — Chunks are serialized to JSON in `state["export_json"]`.

## Document type (4-case routing)

| Type      | Description                                      | Path after route |
|-----------|--------------------------------------------------|------------------|
| `heading` | Structured docs with headings (papers, reports)  | enrich → chunk   |
| `plain`   | Unstructured text (notes, blog body)              | chunk            |
| `slide`   | Presentation / slide deck                        | enrich → chunk   |
| `lifelog` | 5W1H event-style daily log                       | chunk (LifelogChunker) |

## Architecture

![Architecture](assets/image.png)

