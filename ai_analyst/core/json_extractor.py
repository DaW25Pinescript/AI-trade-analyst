"""
Robustly extracts a JSON object from raw AI chat responses.

Real AI responses often include:
- Prose before or after the JSON
- Markdown code fences (```json ... ```)
- Explanatory text following the JSON
- Trailing commas or minor syntax issues

Design principle (spec rule #3): the extractor must be forgiving.
If the AI didn't return clean JSON, we attempt extraction before giving up.
"""
import re
import json


def extract_json(raw: str) -> str:
    """
    Extract and return the first valid top-level JSON object from raw text.

    Raises ValueError if no valid JSON object can be found.
    """
    # 1. Strip markdown code fences
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)

    # 2. Find the outermost { ... } block
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response (no opening brace '{').")

    # Walk from the end to find the matching closing brace
    end = cleaned.rfind("}")
    if end == -1 or end <= start:
        raise ValueError("No JSON object found in response (no closing brace '}').")

    candidate = cleaned[start : end + 1].strip()

    # 3. Validate it parses as JSON
    try:
        json.loads(candidate)
    except json.JSONDecodeError as e:
        # Attempt a second pass: find the last valid JSON boundary
        # by walking backward from the rfind position
        candidate = _find_valid_json(cleaned, start)
        if candidate is None:
            raise ValueError(
                f"Could not parse extracted content as valid JSON: {e}\n"
                f"Extracted text (first 500 chars): {cleaned[start:start+500]}"
            ) from e

    return candidate


def _find_valid_json(text: str, start: int) -> str | None:
    """
    Walk the string from `start` and use a brace-depth counter to find
    the boundary of the first valid JSON object.
    """
    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    return None
    return None
