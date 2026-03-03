from typing import Any


def is_text_only(messages: Any) -> bool:
    if not isinstance(messages, list):
        return False

    for msg in messages:
        if not isinstance(msg, dict):
            return False
        content = msg.get("content")
        if isinstance(content, str):
            continue
        return False

    return True
