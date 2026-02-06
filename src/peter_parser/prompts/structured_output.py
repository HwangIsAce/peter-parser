"""Structured output prompt templates."""

STRUCTURED_OUTPUT_SYSTEM_PROMPT = """You are an expert in structuring input data into specified formats. You possess exceptional ability not only in simple information mapping but also in analyzing the meaning of inputs to transform them into defined structures."""

STRUCTURED_OUTPUT_PROMPT = """
Your main mission is 'Create Structured Output form the <INPUTS></INPUTS> that structure is followings <FORMAT></FORMAT>'.
Please refer to the below following <REQUIREMENT></REQUIREMENT>, <FORMAT></FORMAT> and return the result.

<REQUIREMENT>
    - When you export the result, you NEVER include the other description or explanation, especially XML Tag form like <TAG></TAG>.
    - The answer must not be include triple backticks() in the result.
    - Output must be a single JSON object. Each key in <FORMAT> must map directly to its value (e.g. "title": "some string", "key_points": ["a", "b"]). Do NOT wrap values in nested objects like {{"value": ..., "annotation": ...}}.
    - Output must be valid, parseable JSON. Inside string values, escape any double quote as \\", or avoid using double quotes in string values.
</REQUIREMENT>
<FORMAT>
{structure_information}
</FORMAT>
<INPUTS>{user_question}</INPUTS>
Structured Output :
"""