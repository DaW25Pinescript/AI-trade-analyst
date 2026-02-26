import json

import pytest

from ai_analyst.core.json_extractor import extract_json


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"k": 1}', {"k": 1}),
        ('prefix {"k": 1} suffix', {"k": 1}),
        ('```json\n{"k": 1}\n```', {"k": 1}),
        ('```\n{"k": 1}\n``` trailing prose', {"k": 1}),
        (
            '{"nested": {"a": [1,2,3]}, "text": "value with } brace"} extra',
            {"nested": {"a": [1, 2, 3]}, "text": "value with } brace"},
        ),
    ],
)
def test_extract_json_handles_common_ai_wrappers(raw, expected):
    assert json.loads(extract_json(raw)) == expected


def test_extract_json_raises_on_missing_braces():
    with pytest.raises(ValueError, match="No JSON object found"):
        extract_json("model forgot json output")
