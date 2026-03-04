from typing import Any


def is_text_only(messages: Any) -> bool:
    """
    Return True iff every message content block is plain text (no images).

    Handles two content formats:
      - String content: {"role": "user", "content": "some text"}
      - List content:   {"role": "user", "content": [{"type": "text", "text": "…"}]}

    MED-7 fix: list-format content where every block has type='text' is correctly
    detected as text-only (previously returned False, blocking claude_code_api routing
    for prompts built with list-format blocks).
    """
    if not isinstance(messages, list):
        return False

    for msg in messages:
        if not isinstance(msg, dict):
            return False
        content = msg.get("content")

        if isinstance(content, str):
            continue

        if isinstance(content, list):
            # Every block in the list must be a text block
            for block in content:
                if not isinstance(block, dict):
                    return False
                if block.get("type") != "text":
                    return False
            continue

        # None or unexpected type — treat as non-text
        return False

    return True
