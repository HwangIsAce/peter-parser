# ------------------------------------------------------------
# Heading prompt-based chunking (10-page windows, heading1/2/3)
# ------------------------------------------------------------

"""Prompts for heading-based chunk extraction. Used with up to 10 pages per LLM call."""

HEADING_CHUNK_SYSTEM_PROMPT = """You are an expert in document structure. Your task is to split the given text into chunks by heading hierarchy.

Input format: Each line has the form "ID N: content". Segment index = N (0-based). Count segments by these lines—segment 0 is the first line, segment 1 is the second line, and so on. Do not count physical newlines inside content.

Split at EVERY heading boundary. One chunk = one section (heading + its content until the next heading of same or higher level). Do NOT merge multiple sections into a single chunk. If the document has multiple headings, you MUST produce multiple chunks (typically 3 or more per window).

Heading patterns to recognize (any language):
- Numeric: 1., 1.1, 1.1.1, 2., 2.1
- English: Chapter 1, Section 2.1, 1. Introduction, 2. Methods
- Korean legal: 제1장, 제1조, 제1항, 1.1 적용범위, 1.2 용어의 정의
- Short standalone lines followed by body text

Identify heading1 (top-level), heading2 (sub-section), and heading3 (sub-sub-section) where they exist. Use heading2 and heading3 only when the document actually contains such levels; otherwise use only heading1.

For each chunk, output the segment range (start_index, end_index), heading level (1, 2, or 3), and title. Title must be the heading text for that section—do NOT leave it empty when a heading exists.

Return chunks in document order. The first chunk always starts at segment 0. Do not leave gaps."""

HEADING_CHUNK_USER_PROMPT = """The following text is from a document (up to {max_pages} pages). Each line is "ID N: content"—segment index is N. Split into chunks by heading structure.

<TEXT>
{text}
</TEXT>

For each chunk provide:
- start_index: 0-based segment index where this chunk starts (the N from "ID N:")
- end_index: 0-based segment index one past the last line (exclusive)
- level: 1 for heading1, 2 for heading2, 3 for heading3
- title: the heading text for this chunk (required; do not leave empty for real headings)

Split at every heading. Produce multiple chunks when the document has multiple sections. Return the list in order."""
