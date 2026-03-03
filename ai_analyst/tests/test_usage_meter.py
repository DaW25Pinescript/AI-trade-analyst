import json

from ai_analyst.core.usage_meter import append_usage, summarize_usage
from ai_analyst.models.llm_usage import LLMUsageEntry


def test_append_usage_writes_jsonl(tmp_path):
    run_dir = tmp_path / "runs" / "r1"
    entry = LLMUsageEntry(
        run_id="r1",
        ts_utc="2026-01-01T00:00:00+00:00",
        stage="phase1_analyst",
        node="n1",
        backend="litellm",
        model="gpt-4o",
        provider="openai",
        success=True,
        attempts=1,
        latency_ms=12,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_usd=0.01,
        error=None,
    )

    append_usage(run_dir, entry)

    lines = (run_dir / "usage.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["run_id"] == "r1"
    assert row["total_tokens"] == 30


def test_summarize_usage_aggregates(tmp_path):
    run_dir = tmp_path / "runs" / "r2"
    run_dir.mkdir(parents=True)
    path = run_dir / "usage.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "stage": "phase1_analyst",
                        "node": "default_analyst",
                        "model": "gpt-4o",
                        "provider": "openai",
                        "success": True,
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                        "cost_usd": 0.01,
                    }
                ),
                json.dumps(
                    {
                        "stage": "arbiter",
                        "node": "arbiter_node",
                        "model": "claude-haiku",
                        "provider": "anthropic",
                        "success": False,
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "total_tokens": None,
                        "cost_usd": None,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    summary = summarize_usage(run_dir)

    assert summary["total_calls"] == 2
    assert summary["successful_calls"] == 1
    assert summary["failed_calls"] == 1
    assert summary["calls_by_stage"]["phase1_analyst"] == 1
    assert summary["calls_by_node"]["default_analyst"] == 1
    assert summary["calls_by_model"]["gpt-4o"] == 1
    assert summary["calls_by_provider"]["openai"] == 1
    assert summary["tokens"]["total_tokens"] == 30
    assert summary["calls_with_token_usage"] == 1
    assert summary["calls_without_token_usage"] == 1
    assert summary["total_cost_usd"] == 0.01
