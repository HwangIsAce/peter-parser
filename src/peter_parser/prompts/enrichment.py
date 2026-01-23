"""Prompts for document enrichment."""

DOCUMENT_SUMMARY_PROMPT = """Summarize the following document.

<DOCUMENT>
{document_content}
</DOCUMENT>

Provide a comprehensive summary including the main content, purpose, and key points of the document."""

PAGE_SCRIPT_PROMPT = """Analyze this slide page and extract the following information:
1. Page title
2. Presentation script

Based on the slide content, create a natural presentation script that can be used for presenting this slide."""