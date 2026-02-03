# ------------------------------------------------------------
# Heading prompt-based chunking (10-page windows, heading1/2/3)
# ------------------------------------------------------------

"""Prompts for heading-based chunk extraction. Used with up to 10 pages per LLM call."""

HEADING_CHUNK_SYSTEM_PROMPT = """You are an expert in document structure. Your task is to split the given text into chunks by heading hierarchy.

- Identify heading1 (top-level), heading2 (sub-section), and heading3 (sub-sub-section) where they exist.
- Use heading2 and heading3 only when the document actually contains such levels; otherwise use only heading1.
- For each chunk, output the segment range (start_index, end_index) and the heading level (1, 2, or 3) and title.
- Treat each line of the input as one segment: segment 0 is the first line, segment 1 is the second line, and so on. start_index is the first line of the chunk (0-based), end_index is one past the last line (exclusive).
- Return a list of chunks in document order. The first chunk always starts at segment 0. Do not leave gaps."""

HEADING_CHUNK_USER_PROMPT = """The following text is from a document (up to {max_pages} pages). Split it into chunks by heading structure.

<TEXT>
{text}
</TEXT>

For each chunk provide:
- start_index: 0-based index of the first line (segment) of the chunk
- end_index: 0-based index one past the last line of the chunk (exclusive)
- level: 1 for heading1, 2 for heading2, 3 for heading3 (use 2 and 3 only if present in the document)
- title: the heading text for that chunk

Return the list of chunks in order. Use line numbers as segment indices (first line = 0)."""
