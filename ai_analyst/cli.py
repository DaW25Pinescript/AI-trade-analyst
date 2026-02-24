"""
AI Analyst CLI — Multi-Model Trade Analysis System
Version: 1.2.0 (Manual / Hybrid / Automated)

Usage examples:

  # Check API key status and recommended mode
  python cli.py status

  # Start a manual run (no API keys needed)
  python cli.py run --instrument XAUUSD --session NY --mode manual \\
    --d1 charts/d1.png --h4 charts/h4.png --h1 charts/h1.png --m15 charts/m15.png

  # Start a hybrid run (uses whatever keys are present, manual for the rest)
  python cli.py run --instrument XAUUSD --session NY --mode hybrid \\
    --d1 charts/d1.png --h4 charts/h4.png

  # After filling in manual response files, run the Arbiter
  python cli.py arbiter --run-id <run-id>

  # List all past runs
  python cli.py history

  # Replay a past run (re-runs Arbiter with same inputs, useful for prompt testing)
  python cli.py replay --run-id <run-id>
"""
import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

# Load .env from the ai_analyst directory
load_dotenv(Path(__file__).parent / ".env")

app = typer.Typer(
    name="ai-analyst",
    help="Multi-Model AI Trade Analyst — v1.2 Manual/Hybrid/Automated",
    add_completion=False,
)

_SEP = "═" * 43
_THIN = "─" * 43


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_chart_b64(path: Optional[Path], label: str) -> Optional[str]:
    if path is None:
        return None
    if not path.exists():
        typer.echo(f"[WARN] Chart file not found: {path} ({label}) — skipping.")
        return None
    raw = path.read_bytes()
    return base64.b64encode(raw).decode("utf-8")


def _print_verdict(verdict) -> None:
    typer.echo(f"\n{_SEP}")
    typer.echo("FINAL VERDICT")
    typer.echo(_SEP)
    typer.echo(f"  Decision:       {verdict.decision}")
    typer.echo(f"  Final Bias:     {verdict.final_bias}")
    typer.echo(f"  Confidence:     {verdict.overall_confidence:.0%}")
    typer.echo(f"  Agreement:      {verdict.analyst_agreement_pct}%")
    typer.echo(f"  Risk Override:  {'YES' if verdict.risk_override_applied else 'no'}")
    typer.echo(f"  Notes:          {verdict.arbiter_notes}")

    if verdict.approved_setups:
        typer.echo("\n  APPROVED SETUPS:")
        for setup in verdict.approved_setups:
            typer.echo(f"    • {setup.type}")
            typer.echo(f"      Entry: {setup.entry_zone}  Stop: {setup.stop}")
            typer.echo(f"      Targets: {', '.join(setup.targets)}")
            typer.echo(f"      R:R: {setup.rr_estimate}  Confidence: {setup.confidence:.0%}")

    if verdict.no_trade_conditions:
        typer.echo("\n  NO-TRADE CONDITIONS:")
        for cond in verdict.no_trade_conditions:
            typer.echo(f"    • {cond}")

    typer.echo(_SEP)


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------

@app.command()
def run(
    instrument: str = typer.Option(..., "--instrument", "-i", help="e.g. XAUUSD"),
    session: str = typer.Option(..., "--session", "-s", help="e.g. NY, London, Asia"),
    mode: str = typer.Option(
        "hybrid", "--mode", "-m",
        help="manual | hybrid | automated"
    ),
    # Charts
    d1:  Optional[Path] = typer.Option(None, "--d1",  help="Daily chart image"),
    h4:  Optional[Path] = typer.Option(None, "--h4",  help="4H chart image"),
    h1:  Optional[Path] = typer.Option(None, "--h1",  help="1H chart image"),
    m15: Optional[Path] = typer.Option(None, "--m15", help="15m chart image"),
    m5:  Optional[Path] = typer.Option(None, "--m5",  help="5m chart image"),
    # Risk / account
    balance:    float = typer.Option(10000.0, "--balance",     help="Account balance"),
    min_rr:     float = typer.Option(2.0,     "--min-rr",      help="Minimum R:R"),
    max_risk:   float = typer.Option(0.5,     "--max-risk",    help="Max risk per trade (%)"),
    # Market context
    regime:     str   = typer.Option("unknown",     "--regime",    help="trending | ranging | unknown"),
    news_risk:  str   = typer.Option("none_noted",  "--news-risk", help="none_noted | elevated | critical"),
    # Lens toggles
    lens_ict:   bool  = typer.Option(True,  "--lens-ict/--no-ict",            help="ICT/ICC lens"),
    lens_ms:    bool  = typer.Option(True,  "--lens-ms/--no-ms",              help="Market Structure lens"),
    lens_of:    bool  = typer.Option(False, "--lens-orderflow/--no-orderflow", help="Orderflow Lite lens"),
    lens_tl:    bool  = typer.Option(False, "--lens-trendlines/--no-trendlines", help="Trendlines lens"),
    lens_smt:   bool  = typer.Option(False, "--lens-smt/--no-smt",            help="SMT Divergence lens"),
):
    """Start a new analysis run."""
    from .models.ground_truth import GroundTruthPacket, RiskConstraints, MarketContext
    from .models.lens_config import LensConfig
    from .models.persona import PersonaType
    from .models.execution_config import RunState, RunStatus
    from .core.execution_router import ExecutionRouter, build_execution_config
    from .core.api_key_manager import suggest_execution_mode
    from .core.run_state_manager import save_run_state

    # Resolve mode
    if mode not in ("manual", "hybrid", "automated"):
        typer.echo(f"[ERROR] --mode must be one of: manual, hybrid, automated")
        raise typer.Exit(1)

    if mode == "hybrid":
        suggested = suggest_execution_mode()
        if suggested == "manual":
            typer.echo("[INFO] No API keys found — running in manual mode.")
            mode = "manual"

    # Build chart map
    charts: dict[str, str] = {}
    for label, path in [("D1", d1), ("H4", h4), ("H1", h1), ("M15", m15), ("M5", m5)]:
        b64 = _load_chart_b64(path, label)
        if b64:
            charts[label] = b64

    if not charts:
        typer.echo("[ERROR] At least one chart image must be provided.")
        raise typer.Exit(1)

    timeframes = list(charts.keys())

    ground_truth = GroundTruthPacket(
        instrument=instrument,
        session=session,
        timeframes=timeframes,
        charts=charts,
        risk_constraints=RiskConstraints(
            min_rr=min_rr,
            max_risk_per_trade=max_risk,
        ),
        context=MarketContext(
            account_balance=balance,
            market_regime=regime,
            news_risk=news_risk,
        ),
    )

    lens_config = LensConfig(
        ICT_ICC=lens_ict,
        MarketStructure=lens_ms,
        OrderflowLite=lens_of,
        Trendlines=lens_tl,
        SMT_Divergence=lens_smt,
    )

    personas = [
        PersonaType.DEFAULT_ANALYST,
        PersonaType.RISK_OFFICER,
        PersonaType.PROSECUTOR,
        PersonaType.ICT_PURIST,
    ]

    execution_config = build_execution_config(mode, personas)

    run_state = RunState(
        run_id=ground_truth.run_id,
        status=RunStatus.CREATED,
        mode=mode,
        instrument=instrument,
        session=session,
    )
    save_run_state(run_state)

    typer.echo(f"\n{_SEP}")
    typer.echo(f"AI ANALYST — NEW RUN")
    typer.echo(_SEP)
    typer.echo(f"  Run ID:     {ground_truth.run_id}")
    typer.echo(f"  Instrument: {instrument}  Session: {session}")
    typer.echo(f"  Mode:       {mode.upper()}")
    typer.echo(f"  Charts:     {', '.join(timeframes)}")
    typer.echo(f"  Analysts:   {len(execution_config.analysts)} "
               f"({sum(1 for a in execution_config.analysts if a.delivery.value == 'api')} API, "
               f"{sum(1 for a in execution_config.analysts if a.delivery.value == 'manual')} manual)")
    typer.echo(_SEP)

    router = ExecutionRouter(execution_config, ground_truth, lens_config, run_state)

    verdict = asyncio.run(router.start())

    if verdict is None:
        pack_dir = run_state.prompt_pack_dir or f"output/runs/{ground_truth.run_id}/manual_prompts/"
        typer.echo(f"\n📁 Prompt pack generated:")
        typer.echo(f"   {pack_dir}")
        typer.echo(f"\n👉 Follow the README.txt instructions, then run:")
        typer.echo(f"   python cli.py arbiter --run-id {ground_truth.run_id}\n")
    else:
        _print_verdict(verdict)


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------

@app.command()
def status():
    """Show API key status and recommended execution mode."""
    from .core.api_key_manager import (
        get_key_status, PROVIDER_LABELS, suggest_execution_mode,
        get_available_models,
    )
    from .core.run_state_manager import list_all_runs
    from .core.lens_loader import PROMPT_LIBRARY_VERSION, LENS_DIR

    typer.echo(f"\n{_SEP}")
    typer.echo("AI ANALYST — SYSTEM STATUS")
    typer.echo(_SEP)

    typer.echo("\nAPI KEYS:")
    key_status = get_key_status()
    for env_var, is_set in key_status.items():
        label = PROVIDER_LABELS.get(env_var, env_var)
        mark = "✅" if is_set else "❌"
        note = "available" if is_set else f"Not set  → analysts using this model will run manually"
        typer.echo(f"  {mark} {env_var:<25} → {label} — {note}")

    mode = suggest_execution_mode()
    api_count = sum(1 for v in key_status.values() if v)
    total = len(key_status)

    typer.echo(f"\nRECOMMENDED MODE: {mode.upper()}")
    if mode == "manual":
        typer.echo("  → All analysts will require manual prompt/response")
    elif mode == "hybrid":
        typer.echo(f"  → {api_count} provider(s) will run automatically")
        typer.echo(f"  → {total - api_count} provider(s) will require manual prompt/response")
    else:
        typer.echo("  → All analysts will run automatically via API")

    typer.echo(f"\nTO ADD MORE MODELS:")
    typer.echo(f"  Edit .env and add the missing API keys.")
    typer.echo(f"  Run this command again to check status.")

    typer.echo(f"\nPROMPT LIBRARY: {PROMPT_LIBRARY_VERSION}")
    typer.echo(f"LENS FILES:      {LENS_DIR}")

    runs = list_all_runs()
    if runs:
        last = runs[0]
        typer.echo(f"\nLAST RUN: {last.run_id[:8]}... | {last.instrument} | "
                   f"{last.session} | {last.created_at.strftime('%Y-%m-%d %H:%M UTC')} | "
                   f"STATUS: {last.status}")

    typer.echo(_SEP + "\n")


# ---------------------------------------------------------------------------
# arbiter command
# ---------------------------------------------------------------------------

@app.command()
def arbiter(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to process"),
):
    """Collect manual responses and run the Arbiter for a pending run."""
    from .core.run_state_manager import load_run_state
    from .models.execution_config import RunStatus, ExecutionConfig
    from .models.ground_truth import GroundTruthPacket
    from .models.lens_config import LensConfig
    from .core.execution_router import ExecutionRouter

    OUTPUT_BASE = Path(__file__).parent / "output" / "runs"

    # Load persisted state
    try:
        run_state = load_run_state(run_id)
    except FileNotFoundError:
        typer.echo(f"[ERROR] No run found with ID: {run_id}")
        typer.echo(f"        Run `python cli.py history` to see available runs.")
        raise typer.Exit(1)

    if run_state.status == RunStatus.VERDICT_ISSUED:
        typer.echo(f"[INFO] Run {run_id[:8]}... already has a verdict.")
        verdict_path = OUTPUT_BASE / run_id / "final_verdict.json"
        if verdict_path.exists():
            typer.echo(f"       Verdict: {verdict_path}")
        raise typer.Exit(0)

    if run_state.status not in (RunStatus.AWAITING_RESPONSES, RunStatus.RESPONSES_COLLECTED):
        typer.echo(f"[ERROR] Run {run_id[:8]}... is in state '{run_state.status}' — "
                   f"expected AWAITING_RESPONSES.")
        raise typer.Exit(1)

    # Reload ground truth and configs from disk
    run_dir = OUTPUT_BASE / run_id
    try:
        gt_dict = json.loads((run_dir / "ground_truth.json").read_text())
        # Charts were saved separately as images; they're not needed for arbiter
        # We reconstruct a minimal packet
        ec_raw = (run_dir / "execution_config.json").read_text()
    except FileNotFoundError as e:
        typer.echo(f"[ERROR] Could not load run data: {e}")
        raise typer.Exit(1)

    # Reconstruct GroundTruthPacket (no charts — arbiter doesn't need them)
    from .models.ground_truth import RiskConstraints, MarketContext
    rc = gt_dict.get("risk_constraints", {})
    ctx = gt_dict.get("context", {})
    import uuid
    ground_truth = GroundTruthPacket(
        run_id=run_id,
        instrument=gt_dict["instrument"],
        session=gt_dict["session"],
        timeframes=gt_dict.get("timeframes", []),
        charts={},  # not needed for arbiter
        risk_constraints=RiskConstraints(**rc),
        context=MarketContext(**ctx),
        generated_by=gt_dict.get("generated_by", "api"),
    )

    execution_config = ExecutionConfig.model_validate_json(ec_raw)
    lens_config = LensConfig()  # not needed for arbiter response collection

    typer.echo(f"\n{_SEP}")
    typer.echo(f"AI ANALYST — RUNNING ARBITER")
    typer.echo(_SEP)
    typer.echo(f"  Run ID:     {run_id[:8]}...")
    typer.echo(f"  Instrument: {ground_truth.instrument}  Session: {ground_truth.session}")
    typer.echo(f"\nCollecting manual responses...")

    router = ExecutionRouter(execution_config, ground_truth, lens_config, run_state)

    try:
        verdict = asyncio.run(router.resume_and_run_arbiter())
    except RuntimeError as e:
        typer.echo(f"\n[ERROR] {e}")
        raise typer.Exit(1)

    _print_verdict(verdict)


# ---------------------------------------------------------------------------
# history command
# ---------------------------------------------------------------------------

@app.command()
def history():
    """List all past runs."""
    from .core.run_state_manager import list_all_runs

    runs = list_all_runs()

    if not runs:
        typer.echo("No runs found. Start one with: python cli.py run ...")
        return

    typer.echo(f"\n{_SEP}")
    typer.echo("AI ANALYST — RUN HISTORY")
    typer.echo(_SEP)
    typer.echo(f"  {'Run ID':10}  {'Instrument':8}  {'Session':8}  {'Mode':10}  {'Status':20}  {'Created'}")
    typer.echo(f"  {'-'*10}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*20}  {'-'*16}")

    for state in runs:
        short_id = state.run_id[:8] + "..."
        created = state.created_at.strftime("%Y-%m-%d %H:%M")
        typer.echo(
            f"  {short_id:13}  {state.instrument:8}  {state.session:8}  "
            f"{state.mode:10}  {state.status:20}  {created}"
        )

    typer.echo(_SEP + "\n")


# ---------------------------------------------------------------------------
# replay command
# ---------------------------------------------------------------------------

@app.command()
def replay(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to replay"),
):
    """
    Replay a past run — re-runs the Arbiter with the same analyst outputs.
    Useful for testing prompt changes without re-running analysts.
    """
    from .core.run_state_manager import load_run_state
    from .models.execution_config import RunStatus

    OUTPUT_BASE = Path(__file__).parent / "output" / "runs"

    try:
        run_state = load_run_state(run_id)
    except FileNotFoundError:
        typer.echo(f"[ERROR] No run found with ID: {run_id}")
        raise typer.Exit(1)

    if run_state.status not in (RunStatus.ARBITER_COMPLETE, RunStatus.VERDICT_ISSUED):
        typer.echo(
            f"[ERROR] Run {run_id[:8]}... has status '{run_state.status}'. "
            f"Replay requires a completed run (ARBITER_COMPLETE or VERDICT_ISSUED)."
        )
        raise typer.Exit(1)

    run_dir = OUTPUT_BASE / run_id
    analyst_outputs_dir = run_dir / "analyst_outputs"

    typer.echo(f"\n{_SEP}")
    typer.echo(f"AI ANALYST — REPLAYING RUN {run_id[:8]}...")
    typer.echo(_SEP)

    # Load all saved analyst outputs
    from .models.analyst_output import AnalystOutput
    outputs: list[AnalystOutput] = []
    for path in sorted(analyst_outputs_dir.glob("*.json")):
        if "arbiter" in path.stem:
            continue
        try:
            outputs.append(AnalystOutput.model_validate_json(path.read_text()))
            typer.echo(f"  Loaded: {path.name}")
        except Exception as e:
            typer.echo(f"  [WARN] Skipping {path.name}: {e}")

    if len(outputs) < 2:
        typer.echo(f"[ERROR] Need at least 2 analyst outputs to replay. Found {len(outputs)}.")
        raise typer.Exit(1)

    # Load ground truth
    from .models.ground_truth import GroundTruthPacket, RiskConstraints, MarketContext
    gt_dict = json.loads((run_dir / "ground_truth.json").read_text())
    rc = gt_dict.get("risk_constraints", {})
    ctx = gt_dict.get("context", {})

    ground_truth = GroundTruthPacket(
        run_id=run_id,
        instrument=gt_dict["instrument"],
        session=gt_dict["session"],
        timeframes=gt_dict.get("timeframes", []),
        charts={},
        risk_constraints=RiskConstraints(**rc),
        context=MarketContext(**ctx),
    )

    from .core.arbiter_prompt_builder import build_arbiter_prompt
    from .models.arbiter_output import FinalVerdict
    from litellm import acompletion

    ARBITER_MODEL = "claude-haiku-4-5-20251001"

    async def _replay():
        prompt = build_arbiter_prompt(
            analyst_outputs=outputs,
            risk_constraints=ground_truth.risk_constraints,
            run_id=f"{run_id}-replay",
        )
        response = await acompletion(
            model=ARBITER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )
        raw: str = response.choices[0].message.content
        return FinalVerdict.model_validate_json(raw)

    verdict = asyncio.run(_replay())
    _print_verdict(verdict)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
