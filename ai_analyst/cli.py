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
    # v2.1b deliberation
    deliberation: bool = typer.Option(
        False,
        "--deliberation/--no-deliberation",
        help="v2.1b: Run optional second analyst round (peer deliberation) before arbiter.",
    ),
    # v2.2 live progress
    live: bool = typer.Option(
        False,
        "--live/--no-live",
        help="v2.2: Print live progress as each analyst completes.",
    ),
):
    """Start a new analysis run."""
    from .models.ground_truth import (
        GroundTruthPacket,
        RiskConstraints,
        MarketContext,
        ScreenshotMetadata,
        ALLOWED_CLEAN_TIMEFRAMES,
    )
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

    unsupported = [tf for tf in charts if tf not in ALLOWED_CLEAN_TIMEFRAMES]
    for tf in unsupported:
        typer.echo(f"[WARN] Timeframe '{tf}' is not supported by GroundTruth schema and will be skipped.")

    charts = {tf: b64 for tf, b64 in charts.items() if tf in ALLOWED_CLEAN_TIMEFRAMES}
    if not charts:
        typer.echo("[ERROR] No supported clean-chart timeframes were provided (H4/H1/M15/M5).")
        raise typer.Exit(1)

    timeframes = list(charts.keys())
    screenshot_metadata = [
        ScreenshotMetadata(timeframe=tf, lens="NONE", evidence_type="price_only")
        for tf in timeframes
    ]

    ground_truth = GroundTruthPacket(
        instrument=instrument,
        session=session,
        timeframes=timeframes,
        charts=charts,
        screenshot_metadata=screenshot_metadata,
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
    if deliberation:
        typer.echo(f"  Deliberation: ENABLED (second analyst round before arbiter)")
    if live:
        typer.echo(f"  Live progress: ON")
    typer.echo(_SEP)

    router = ExecutionRouter(
        execution_config, ground_truth, lens_config, run_state,
        enable_deliberation=deliberation,
    )

    if live:
        # v2.2 — register a progress queue and print events as analysts complete
        from .core import progress_store as _ps

        async def _run_with_live_progress() -> Optional[FinalVerdict]:
            queue = _ps.register(ground_truth.run_id)

            stop = asyncio.Event()

            async def _drain():
                """Read progress events from the queue until the pipeline is done."""
                while not stop.is_set():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=0.3)
                        stage = event.get("stage", "?")
                        persona = event.get("persona", "?")
                        if stage in ("phase1", "deliberation"):
                            action = event.get("action", "?")
                            conf = event.get("confidence", 0.0)
                            typer.echo(
                                f"  [{stage}] {persona}: {action} "
                                f"(confidence: {conf:.0%})"
                            )
                        elif stage == "phase2_overlay":
                            contradictions = event.get("contradictions", 0)
                            typer.echo(
                                f"  [overlay] {persona}: delta complete "
                                f"({contradictions} contradiction(s))"
                            )
                    except asyncio.TimeoutError:
                        pass  # re-check stop flag
                # Drain any remaining events that arrived just before stop was set
                while True:
                    try:
                        event = queue.get_nowait()
                        stage = event.get("stage", "?")
                        persona = event.get("persona", "?")
                        if stage in ("phase1", "deliberation"):
                            action = event.get("action", "?")
                            conf = event.get("confidence", 0.0)
                            typer.echo(
                                f"  [{stage}] {persona}: {action} "
                                f"(confidence: {conf:.0%})"
                            )
                    except asyncio.QueueEmpty:
                        break

            drain_task = asyncio.create_task(_drain())
            try:
                verdict = await router.start()
            finally:
                stop.set()
                await drain_task
                _ps.unregister(ground_truth.run_id)
            return verdict

        verdict = asyncio.run(_run_with_live_progress())
    else:
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
    ground_truth = GroundTruthPacket(
        run_id=run_id,
        instrument=gt_dict["instrument"],
        session=gt_dict["session"],
        timeframes=gt_dict.get("timeframes", []),
        charts={},  # not needed for arbiter
        screenshot_metadata=[],
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
        screenshot_metadata=[],
        risk_constraints=RiskConstraints(**rc),
        context=MarketContext(**ctx),
    )

    from .core.arbiter_prompt_builder import build_arbiter_prompt
    from .core.run_paths import get_run_dir
    from .core.usage_meter import acompletion_metered
    from .models.arbiter_output import FinalVerdict
    from .llm_router import router
    from .llm_router.task_types import ARBITER_DECISION

    async def _replay():
        macro_context = None
        try:
            from macro_risk_officer.ingestion.scheduler import MacroScheduler
            macro_context = MacroScheduler().get_context(instrument=ground_truth.instrument)
        except Exception:
            pass
        prompt = build_arbiter_prompt(
            analyst_outputs=outputs,
            risk_constraints=ground_truth.risk_constraints,
            run_id=f"{run_id}-replay",
            macro_context=macro_context,
        )
        route = router.resolve(ARBITER_DECISION)
        replay_run_id = f"{run_id}-replay"
        response = await acompletion_metered(
            run_dir=get_run_dir(replay_run_id),
            run_id=replay_run_id,
            stage="replay_arbiter",
            node="arbiter",
            model=route["model"],
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
            api_base=route["base_url"],
            api_key=route["api_key"],
        )
        raw: str = response.choices[0].message.content
        return FinalVerdict.model_validate_json(raw)

    verdict = asyncio.run(_replay())
    _print_verdict(verdict)


@app.command()
def usage(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to summarize usage for"),
):
    """Summarize LLM usage.jsonl for a run."""
    from .core.run_paths import get_run_dir
    from .core.usage_meter import summarize_usage

    run_dir = get_run_dir(run_id)
    summary = summarize_usage(run_dir)
    out_path = run_dir / "usage_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    typer.echo(f"\n{_SEP}")
    typer.echo("AI ANALYST — USAGE SUMMARY")
    typer.echo(_SEP)
    typer.echo(f"Run ID: {run_id}")
    typer.echo(f"Total calls: {summary['total_calls']}")
    typer.echo("Calls by stage:")
    for k, v in summary["calls_by_stage"].items():
        typer.echo(f"  - {k}: {v}")
    typer.echo("Calls by model:")
    for k, v in summary["calls_by_model"].items():
        typer.echo(f"  - {k}: {v}")
    typer.echo(
        "Tokens (summed non-null): "
        f"prompt={summary['tokens']['prompt_tokens']} "
        f"completion={summary['tokens']['completion_tokens']} "
        f"total={summary['tokens']['total_tokens']}"
    )
    typer.echo(f"Total cost (summed non-null): ${summary['total_cost_usd']:.6f}")
    typer.echo(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# export-audit command (Phase 5)
# ---------------------------------------------------------------------------

@app.command("export-audit")
def export_audit(
    fmt: str = typer.Option(
        "csv", "--format", "-f",
        help="Output format: csv | json",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path (default: audit_trail.<format> in cwd)",
    ),
):
    """Phase 5 — Export full audit trail (runs, verdicts, usage) to CSV or JSON."""
    from .core.run_state_manager import list_all_runs
    from .core.usage_meter import summarize_usage

    if fmt not in ("csv", "json"):
        typer.echo("[ERROR] --format must be 'csv' or 'json'.")
        raise typer.Exit(1)

    runs = list_all_runs()
    if not runs:
        typer.echo("No runs found. Nothing to export.")
        raise typer.Exit(0)

    OUTPUT_BASE = Path(__file__).parent / "output" / "runs"
    records: list[dict] = []

    for state in runs:
        run_dir = OUTPUT_BASE / state.run_id
        # Load verdict if available
        verdict_data: dict = {}
        verdict_path = run_dir / "final_verdict.json"
        if verdict_path.exists():
            try:
                verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Load usage summary
        usage = {}
        try:
            from .core.usage_meter import summarize_usage as _su
            usage = _su(run_dir)
        except Exception:
            pass

        record = {
            "run_id": state.run_id,
            "instrument": state.instrument,
            "session": state.session,
            "mode": state.mode,
            "status": state.status.value if hasattr(state.status, "value") else str(state.status),
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            # Verdict fields
            "decision": verdict_data.get("decision", ""),
            "final_bias": verdict_data.get("final_bias", ""),
            "overall_confidence": verdict_data.get("overall_confidence", ""),
            "analyst_agreement_pct": verdict_data.get("analyst_agreement_pct", ""),
            "risk_override_applied": verdict_data.get("risk_override_applied", ""),
            "arbiter_notes": verdict_data.get("arbiter_notes", ""),
            # Usage fields
            "total_llm_calls": usage.get("total_calls", 0),
            "successful_calls": usage.get("successful_calls", 0),
            "failed_calls": usage.get("failed_calls", 0),
            "total_cost_usd": usage.get("total_cost_usd", 0.0),
            "prompt_tokens": usage.get("tokens", {}).get("prompt_tokens", 0),
            "completion_tokens": usage.get("tokens", {}).get("completion_tokens", 0),
        }
        records.append(record)

    if output is None:
        output = Path(f"audit_trail.{fmt}")

    if fmt == "json":
        output.write_text(json.dumps(records, indent=2), encoding="utf-8")
    else:
        import csv as csv_mod
        if records:
            fieldnames = list(records[0].keys())
            with output.open("w", newline="", encoding="utf-8") as f:
                writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)

    typer.echo(f"\n{_SEP}")
    typer.echo(f"AUDIT TRAIL EXPORT")
    typer.echo(_SEP)
    typer.echo(f"  Runs exported: {len(records)}")
    typer.echo(f"  Format:        {fmt.upper()}")
    typer.echo(f"  Output:        {output}")
    typer.echo(_SEP + "\n")


# ---------------------------------------------------------------------------
# import-aar command (Phase 5)
# ---------------------------------------------------------------------------

@app.command("import-aar")
def import_aar(
    source: Path = typer.Argument(..., help="Path to AAR file (CSV or JSON)"),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Validate without writing. Shows what would be imported.",
    ),
):
    """Phase 5 — Bulk import after-action reviews from a CSV or JSON file."""
    if not source.exists():
        typer.echo(f"[ERROR] File not found: {source}")
        raise typer.Exit(1)

    suffix = source.suffix.lower()
    aar_records: list[dict] = []

    if suffix == ".json":
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                aar_records = raw
            elif isinstance(raw, dict):
                aar_records = [raw]
            else:
                typer.echo("[ERROR] JSON must be an array of AAR objects or a single AAR object.")
                raise typer.Exit(1)
        except json.JSONDecodeError as e:
            typer.echo(f"[ERROR] Invalid JSON: {e}")
            raise typer.Exit(1)
    elif suffix == ".csv":
        import csv as csv_mod
        try:
            with source.open("r", encoding="utf-8") as f:
                reader = csv_mod.DictReader(f)
                for row in reader:
                    # Coerce numeric fields
                    for key in ("actualEntry", "actualExit", "rAchieved"):
                        if key in row and row[key]:
                            try:
                                row[key] = float(row[key])
                            except ValueError:
                                pass
                    for key in ("revisedConfidence",):
                        if key in row and row[key]:
                            try:
                                row[key] = int(row[key])
                            except ValueError:
                                pass
                    for key in ("firstTouch", "wouldHaveWon", "killSwitchTriggered"):
                        if key in row:
                            row[key] = row[key].lower() in ("true", "1", "yes")
                    if "failureReasonCodes" in row and isinstance(row["failureReasonCodes"], str):
                        codes = row["failureReasonCodes"].strip()
                        if codes:
                            row["failureReasonCodes"] = [c.strip() for c in codes.split("|")]
                        else:
                            row["failureReasonCodes"] = []
                    aar_records = aar_records  # already appending below
                    aar_records.append(row)
        except Exception as e:
            typer.echo(f"[ERROR] Failed to read CSV: {e}")
            raise typer.Exit(1)
    else:
        typer.echo(f"[ERROR] Unsupported file type '{suffix}'. Use .json or .csv.")
        raise typer.Exit(1)

    if not aar_records:
        typer.echo("No AAR records found in file.")
        raise typer.Exit(0)

    # Validate required fields
    REQUIRED_FIELDS = {"ticketId", "outcomeEnum", "reviewedAt"}
    OUTPUT_BASE = Path(__file__).parent / "output" / "aars"

    valid = 0
    errors = 0
    for i, aar in enumerate(aar_records):
        missing = REQUIRED_FIELDS - set(aar.keys())
        if missing:
            typer.echo(f"  [SKIP] Record {i+1}: missing required fields: {', '.join(sorted(missing))}")
            errors += 1
            continue

        ticket_id = aar["ticketId"]

        if dry_run:
            typer.echo(f"  [DRY-RUN] Record {i+1}: ticketId={ticket_id} outcome={aar.get('outcomeEnum', '?')}")
            valid += 1
            continue

        # Write AAR to output directory
        aar_dir = OUTPUT_BASE / ticket_id
        aar_dir.mkdir(parents=True, exist_ok=True)
        aar_path = aar_dir / "aar.json"

        # Set schemaVersion if not present
        if "schemaVersion" not in aar:
            aar["schemaVersion"] = "1.0.0"

        aar_path.write_text(json.dumps(aar, indent=2), encoding="utf-8")
        valid += 1

    typer.echo(f"\n{_SEP}")
    typer.echo(f"BULK AAR IMPORT {'(DRY RUN)' if dry_run else ''}")
    typer.echo(_SEP)
    typer.echo(f"  Source:     {source}")
    typer.echo(f"  Records:   {len(aar_records)} total")
    typer.echo(f"  Imported:  {valid}")
    typer.echo(f"  Errors:    {errors}")
    if not dry_run and valid > 0:
        typer.echo(f"  Output:    {OUTPUT_BASE}")
    typer.echo(_SEP + "\n")


# ---------------------------------------------------------------------------
# export-analytics command (Phase 5)
# ---------------------------------------------------------------------------

@app.command("export-analytics")
def export_analytics(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output CSV file path (default: analytics_export.csv in cwd)",
    ),
):
    """Phase 5 — Export analytics data (all runs with verdicts) to CSV for external tools."""
    from .core.run_state_manager import list_all_runs
    from .core.usage_meter import summarize_usage

    runs = list_all_runs()
    if not runs:
        typer.echo("No runs found. Nothing to export.")
        raise typer.Exit(0)

    OUTPUT_BASE = Path(__file__).parent / "output" / "runs"
    rows: list[dict] = []

    for state in runs:
        run_dir = OUTPUT_BASE / state.run_id

        # Load verdict
        verdict_data: dict = {}
        verdict_path = run_dir / "final_verdict.json"
        if verdict_path.exists():
            try:
                verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Load usage
        usage = {}
        try:
            usage = summarize_usage(run_dir)
        except Exception:
            pass

        # Load AAR if linked
        aar_data: dict = {}
        aar_dir = Path(__file__).parent / "output" / "aars" / state.run_id
        aar_path = aar_dir / "aar.json"
        if aar_path.exists():
            try:
                aar_data = json.loads(aar_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Build setups summary
        setups = verdict_data.get("approved_setups", [])
        setup_types = "; ".join(s.get("type", "") for s in setups) if setups else ""
        avg_rr = ""
        if setups:
            rrs = [s.get("rr_estimate", 0) for s in setups if s.get("rr_estimate")]
            avg_rr = f"{sum(rrs) / len(rrs):.2f}" if rrs else ""

        row = {
            "run_id": state.run_id,
            "instrument": state.instrument,
            "session": state.session,
            "mode": state.mode,
            "status": state.status.value if hasattr(state.status, "value") else str(state.status),
            "created_at": state.created_at.isoformat(),
            # Verdict
            "decision": verdict_data.get("decision", ""),
            "final_bias": verdict_data.get("final_bias", ""),
            "overall_confidence": verdict_data.get("overall_confidence", ""),
            "analyst_agreement_pct": verdict_data.get("analyst_agreement_pct", ""),
            "risk_override_applied": verdict_data.get("risk_override_applied", ""),
            "setup_types": setup_types,
            "avg_rr_estimate": avg_rr,
            "no_trade_conditions": "; ".join(verdict_data.get("no_trade_conditions", [])),
            # Usage
            "total_cost_usd": usage.get("total_cost_usd", 0.0),
            "total_llm_calls": usage.get("total_calls", 0),
            "prompt_tokens": usage.get("tokens", {}).get("prompt_tokens", 0),
            "completion_tokens": usage.get("tokens", {}).get("completion_tokens", 0),
            # AAR (if present)
            "aar_outcome": aar_data.get("outcomeEnum", ""),
            "aar_verdict": aar_data.get("verdictEnum", ""),
            "aar_r_achieved": aar_data.get("rAchieved", ""),
            "aar_exit_reason": aar_data.get("exitReasonEnum", ""),
            "aar_psychological_tag": aar_data.get("psychologicalTag", ""),
        }
        rows.append(row)

    if output is None:
        output = Path("analytics_export.csv")

    import csv as csv_mod
    if rows:
        fieldnames = list(rows[0].keys())
        with output.open("w", newline="", encoding="utf-8") as f:
            writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    typer.echo(f"\n{_SEP}")
    typer.echo(f"ANALYTICS CSV EXPORT")
    typer.echo(_SEP)
    typer.echo(f"  Runs exported: {len(rows)}")
    typer.echo(f"  Output:        {output}")
    typer.echo(f"  Columns:       {len(rows[0]) if rows else 0}")
    typer.echo(_SEP + "\n")


# ---------------------------------------------------------------------------
# feedback command (Phase 7)
# ---------------------------------------------------------------------------

@app.command()
def feedback():
    """Phase 7 — Generate feedback loop report from AAR outcomes for prompt refinement."""
    from .core.feedback_loop import build_feedback_report

    report = build_feedback_report()
    typer.echo(report.format())


# ---------------------------------------------------------------------------
# backtest command (Phase 8b)
# ---------------------------------------------------------------------------

@app.command()
def backtest(
    instrument: Optional[str] = typer.Option(
        None, "--instrument", "-i",
        help="Filter by instrument (e.g. XAUUSD). Default: all.",
    ),
    regime: Optional[str] = typer.Option(
        None, "--regime", "-r",
        help="Filter by macro regime (e.g. risk_on, risk_off, neutral).",
    ),
    session: Optional[str] = typer.Option(
        None, "--session", "-s",
        help="Filter by session (e.g. NY, London).",
    ),
    min_confidence: float = typer.Option(
        0.0, "--min-confidence",
        help="Minimum arbiter confidence threshold (0.0-1.0).",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Export backtest results to JSON file.",
    ),
):
    """Phase 8b — Run strategy backtest over historical outcomes."""
    from .core.backtester import run_backtest, BacktestConfig

    config = BacktestConfig(
        instrument_filter=instrument,
        regime_filter=regime,
        session_filter=session,
        min_confidence=min_confidence,
    )
    report = run_backtest(config)
    typer.echo(report.format())

    if output:
        output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        typer.echo(f"  Results exported to: {output}")


# ---------------------------------------------------------------------------
# e2e command (Phase 8c)
# ---------------------------------------------------------------------------

@app.command()
def e2e():
    """Phase 8c — Run end-to-end integration validation checks."""
    from .core.e2e_validator import run_e2e_validation

    report = run_e2e_validation()
    typer.echo(report.format())

    if not report.all_passed:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# plugins command (Phase 8d)
# ---------------------------------------------------------------------------

@app.command()
def plugins():
    """Phase 8d — List all registered plugins (personas, data sources, hooks)."""
    from .core.plugin_registry import registry

    registry.discover_builtins()
    registry.discover_plugins()
    typer.echo(registry.format_summary())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
