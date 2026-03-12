import json
from types import SimpleNamespace

from ai_analyst.graph.arbiter_node import arbiter_node


async def test_malformed_arbiter_json_returns_structured_error_and_no_trade(
    sample_ground_truth, sample_lens_config, monkeypatch
):
    async def fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{not-valid-json"))]
        )

    monkeypatch.setattr("ai_analyst.graph.arbiter_node.acompletion_metered", fake_completion)

    state = {
        "ground_truth": sample_ground_truth,
        "lens_config": sample_lens_config,
        "analyst_outputs": [],
        "analyst_configs_used": [],
        "overlay_delta_reports": [],
        "chart_analysis_runtime": None,
        "macro_context": None,
        "final_verdict": None,
        "error": None,
        "enable_deliberation": False,
        "deliberation_outputs": [],
        "_pipeline_start_ts": None,
        "_node_timings": None,
    }

    out = await arbiter_node(state)

    assert out["final_verdict"].decision == "NO_TRADE"
    assert out["error"] is not None
    err = json.loads(out["error"])
    assert err["error_type"] == "JSON_DECODE_ERROR"
    assert err["code"] == "ARBITER_MALFORMED_JSON"
    assert "response_excerpt" in err


async def test_missing_verdict_decision_defaults_to_no_trade_with_warning(
    sample_ground_truth, sample_lens_config, monkeypatch, caplog
):
    payload = {
        "final_bias": "neutral",
        "decision": "",
        "approved_setups": [],
        "no_trade_conditions": ["test"],
        "overall_confidence": 0.1,
        "analyst_agreement_pct": 0,
        "risk_override_applied": False,
        "arbiter_notes": "stub",
        "audit_log": {
            "run_id": sample_ground_truth.run_id,
            "analysts_received": 0,
            "analysts_valid": 0,
            "htf_consensus": False,
            "setup_consensus": False,
            "risk_override": False,
        },
    }

    async def fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    monkeypatch.setattr("ai_analyst.graph.arbiter_node.acompletion_metered", fake_completion)

    state = {
        "ground_truth": sample_ground_truth,
        "lens_config": sample_lens_config,
        "analyst_outputs": [],
        "analyst_configs_used": [],
        "overlay_delta_reports": [],
        "chart_analysis_runtime": None,
        "macro_context": None,
        "final_verdict": None,
        "error": None,
        "enable_deliberation": False,
        "deliberation_outputs": [],
        "_pipeline_start_ts": None,
        "_node_timings": None,
    }

    out = await arbiter_node(state)

    assert out["final_verdict"].decision == "NO_TRADE"
    assert any("missing/empty" in rec.getMessage() for rec in caplog.records)
