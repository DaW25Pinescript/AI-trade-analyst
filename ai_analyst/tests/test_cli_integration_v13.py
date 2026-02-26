import json
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from ai_analyst.cli import app


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
    b"\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _create_chart(path: Path) -> Path:
    path.write_bytes(PNG_1X1)
    return path


def _extract_run_id(stdout: str) -> str:
    match = re.search(r"Run ID:\s+([0-9a-f\-]{36})", stdout)
    assert match, f"could not find run id in output:\n{stdout}"
    return match.group(1)


def _run_dir(run_id: str) -> Path:
    package_root = Path(__file__).resolve().parents[1]
    return package_root / "output" / "runs" / run_id


def _stub_litellm(monkeypatch, decision: str = "NO_TRADE"):
    verdict = {
        "final_bias": "neutral",
        "decision": decision,
        "approved_setups": [],
        "no_trade_conditions": ["integration test"],
        "overall_confidence": 0.51,
        "analyst_agreement_pct": 50,
        "risk_override_applied": False,
        "arbiter_notes": "stubbed verdict",
        "audit_log": {
            "run_id": "stub",
            "analysts_received": 2,
            "analysts_valid": 2,
            "htf_consensus": False,
            "setup_consensus": False,
            "risk_override": False,
        },
    }

    async def fake_acompletion(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(verdict)))]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))


def test_run_manual_mode_generates_prompt_pack_with_real_chart_files(tmp_path):
    runner = CliRunner()

    h4 = _create_chart(tmp_path / "h4.png")
    h1 = _create_chart(tmp_path / "h1.png")
    m15 = _create_chart(tmp_path / "m15.png")
    m5 = _create_chart(tmp_path / "m5.png")

    result = runner.invoke(
        app,
        [
            "run",
            "--instrument",
            "XAUUSD",
            "--session",
            "NY",
            "--mode",
            "manual",
            "--h4",
            str(h4),
            "--h1",
            str(h1),
            "--m15",
            str(m15),
            "--m5",
            str(m5),
        ],
    )

    assert result.exit_code == 0, result.stdout
    run_id = _extract_run_id(result.stdout)
    run_dir = _run_dir(run_id)

    try:
        prompts_dir = run_dir / "manual_prompts"
        assert (prompts_dir / "README.txt").exists()
        assert (prompts_dir / "responses").is_dir()
        # Response stubs are inside manual_prompts/responses
        response_files = sorted((prompts_dir / "responses").glob("analyst_*_response.json"))
        assert len(response_files) >= 2

        chart_files = sorted((prompts_dir / "charts").glob("*_screenshot.png"))
        names = {p.name for p in chart_files}
        assert {"H4_screenshot.png", "H1_screenshot.png", "M15_screenshot.png", "M5_screenshot.png"}.issubset(names)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_arbiter_and_replay_end_to_end_with_manual_responses(monkeypatch, tmp_path):
    _stub_litellm(monkeypatch)
    runner = CliRunner()

    h4 = _create_chart(tmp_path / "h4.png")
    m15 = _create_chart(tmp_path / "m15.png")

    run_result = runner.invoke(
        app,
        [
            "run",
            "--instrument",
            "XAUUSD",
            "--session",
            "London",
            "--mode",
            "manual",
            "--h4",
            str(h4),
            "--m15",
            str(m15),
        ],
    )
    assert run_result.exit_code == 0, run_result.stdout

    run_id = _extract_run_id(run_result.stdout)
    run_dir = _run_dir(run_id)

    try:
        responses_dir = run_dir / "manual_prompts" / "responses"
        wrapped_payload = """Analysis complete.
```json
{
  \"htf_bias\": \"bearish\",
  \"structure_state\": \"continuation\",
  \"key_levels\": {\"premium\": [\"1950-1955\"], \"discount\": [\"1910-1915\"]},
  \"setup_valid\": true,
  \"setup_type\": \"liquidity_sweep_reversal\",
  \"entry_model\": \"Pullback\",
  \"invalidation\": \"Close above 1955\",
  \"disqualifiers\": [],
  \"confidence\": 0.72,
  \"rr_estimate\": 2.4,
  \"notes\": \"valid\",
  \"recommended_action\": \"SHORT\"
}
```
Thanks.
"""
        for file in sorted(responses_dir.glob("analyst_*_response.json"))[:2]:
            file.write_text(wrapped_payload, encoding="utf-8")

        arbiter_result = runner.invoke(app, ["arbiter", "--run-id", run_id])
        assert arbiter_result.exit_code == 0, arbiter_result.stdout

        verdict_path = run_dir / "final_verdict.json"
        assert verdict_path.exists()
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        assert verdict["decision"] == "NO_TRADE"
        assert "overall_confidence" in verdict

        # Seed replay inputs: replay reads analyst_outputs/*.json
        analyst_outputs_dir = run_dir / "analyst_outputs"
        for idx in range(2):
            payload = json.loads(wrapped_payload.split("```json", 1)[1].split("```", 1)[0])
            (analyst_outputs_dir / f"manual_analyst_{idx+1}.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

        replay_result = runner.invoke(app, ["replay", "--run-id", run_id])
        assert replay_result.exit_code == 0, replay_result.stdout
        assert "REPLAYING RUN" in replay_result.stdout
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
