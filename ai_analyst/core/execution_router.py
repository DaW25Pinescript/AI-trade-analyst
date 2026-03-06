"""
ExecutionRouter — routes each analyst to API or manual delivery.

Implements the three execution modes (spec v1.2):
  Mode 1 — MANUAL:    generates prompt pack, waits for user responses
  Mode 2 — HYBRID:    runs API analysts concurrently, generates prompts for the rest
  Mode 3 — AUTOMATED: runs all analysts via API (uses the existing LangGraph pipeline)

In all cases the same Arbiter logic runs once analyst Evidence Objects are collected.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from macro_risk_officer.core.models import MacroContext

logger = logging.getLogger(__name__)

# Module-level MRO scheduler singleton — shared across ExecutionRouter instances.
# Same lazy-init / fail-silent pattern as graph/macro_context_node.py so the
# MRO package remains a soft dependency.
_mro_scheduler: Optional[object] = None


def _get_mro_scheduler() -> Optional[object]:
    global _mro_scheduler
    if _mro_scheduler is None:
        try:
            from macro_risk_officer.ingestion.scheduler import MacroScheduler
            _mro_scheduler = MacroScheduler()
        except ImportError:
            logger.warning(
                "[MRO] macro_risk_officer not available — macro context disabled in ExecutionRouter."
            )
    return _mro_scheduler


def _try_fetch_macro_context(instrument: str) -> Optional["MacroContext"]:
    """Fetch macro context for *instrument*, returning None on any failure."""
    scheduler = _get_mro_scheduler()
    if scheduler is None:
        return None
    try:
        return scheduler.get_context(instrument=instrument)
    except Exception as exc:
        logger.warning(
            "[MRO] MacroContext fetch failed in ExecutionRouter (%s: %s) — "
            "continuing without macro context.",
            type(exc).__name__,
            exc,
        )
        return None

from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig
from ..models.execution_config import (
    AnalystConfig, AnalystDelivery, ExecutionConfig, RunState, RunStatus,
)
from ..models.analyst_output import AnalystOutput
from ..models.arbiter_output import FinalVerdict
from ..models.persona import PersonaType
from ..graph.analyst_nodes import run_analyst, run_deliberation_round, MINIMUM_VALID_ANALYSTS
from .analyst_prompt_builder import build_analyst_prompt
from .arbiter_prompt_builder import build_arbiter_prompt
from .prompt_pack_generator import PromptPackGenerator
from .json_extractor import extract_json
from .run_state_manager import transition, save_run_state
from .logger import log_run
from .run_paths import get_run_dir
from .usage_meter import acompletion_metered

OUTPUT_BASE = Path(__file__).parent.parent / "output" / "runs"

# Arbiter model — text-only, cheaper (same as graph/arbiter_node.py)
ARBITER_MODEL = "claude-haiku-4-5-20251001"


def _safe_excerpt(raw: str, max_chars: int = 256) -> str:
    excerpt = (raw or "").replace("\n", " ").strip()
    return excerpt[:max_chars]


def _fallback_verdict(run_id: str, reason: str) -> FinalVerdict:
    return FinalVerdict.model_validate({
        "final_bias": "neutral",
        "decision": "NO_TRADE",
        "approved_setups": [],
        "no_trade_conditions": [reason],
        "overall_confidence": 0.0,
        "analyst_agreement_pct": 0,
        "risk_override_applied": False,
        "arbiter_notes": reason,
        "audit_log": {
            "run_id": run_id,
            "analysts_received": 0,
            "analysts_valid": 0,
            "htf_consensus": False,
            "setup_consensus": False,
            "risk_override": False,
        },
    })


class ExecutionRouter:
    def __init__(
        self,
        config: ExecutionConfig,
        ground_truth: GroundTruthPacket,
        lens_config: LensConfig,
        run_state: RunState,
        macro_context: Optional["MacroContext"] = None,
        enable_deliberation: bool = False,
    ) -> None:
        self.config = config
        self.ground_truth = ground_truth
        self.lens_config = lens_config
        self.run_state = run_state
        self.run_id = ground_truth.run_id
        self.macro_context = macro_context
        self.enable_deliberation = enable_deliberation   # v2.1b
        self.analyst_outputs_dir = OUTPUT_BASE / self.run_id / "analyst_outputs"
        self.analyst_outputs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    async def start(self) -> Optional[FinalVerdict]:
        """
        Kick off the run. Returns FinalVerdict immediately if fully automated,
        or None if manual responses are still pending (caller should instruct user).
        """
        api_outputs = await self._run_api_analysts()
        self._save_api_outputs(api_outputs)

        if self.config.has_manual_analysts:
            pack = PromptPackGenerator(
                self.ground_truth, self.config, self.lens_config
            )
            pack_dir = pack.generate()

            pending_ids = [a.analyst_id for a in self.config.manual_analysts]
            complete_ids = [a.analyst_id for a in self.config.api_analysts]

            self.run_state = transition(
                self.run_state,
                RunStatus.AWAITING_RESPONSES,
                analysts_pending=pending_ids,
                analysts_complete=complete_ids,
                prompt_pack_dir=str(pack_dir),
            )
            return None  # caller waits for manual responses

        # Fully automated — optionally run deliberation, then arbiter
        all_outputs = api_outputs
        return await self._run_arbiter_and_finalise(all_outputs)

    async def resume_and_run_arbiter(self) -> FinalVerdict:
        """
        Called by `cli.py arbiter --run-id` after the user has filled in response files.
        Loads API outputs already saved, validates manual responses, then runs Arbiter.
        """
        api_outputs = self._load_saved_api_outputs()
        manual_outputs = self.collect_manual_responses()

        all_outputs = api_outputs + manual_outputs
        if len(all_outputs) < MINIMUM_VALID_ANALYSTS:
            raise RuntimeError(
                f"Only {len(all_outputs)} valid analyst response(s) collected. "
                f"Minimum required: {MINIMUM_VALID_ANALYSTS}."
            )

        self.run_state = transition(
            self.run_state, RunStatus.VALIDATION_PASSED
        )
        return await self._run_arbiter_and_finalise(all_outputs)

    # ------------------------------------------------------------------
    # Manual response collection
    # ------------------------------------------------------------------

    def collect_manual_responses(self) -> list[AnalystOutput]:
        """
        Read, extract JSON from, and validate response files the user has filled in.
        Empty files are skipped gracefully (design principle #5: never block on missing keys).
        """
        responses_dir = (
            OUTPUT_BASE / self.run_id / "manual_prompts" / "responses"
        )
        if not responses_dir.exists():
            return []

        outputs: list[AnalystOutput] = []
        for response_file in sorted(responses_dir.glob("analyst_*_response.json")):
            raw = response_file.read_text(encoding="utf-8").strip()
            if not raw:
                continue  # empty stub — user hasn't filled this one in

            try:
                json_str = extract_json(raw)
                output = AnalystOutput.model_validate_json(json_str)
                outputs.append(output)
                print(f"  ✅ Validated: {response_file.name}")
            except Exception as e:
                print(f"  ❌ Failed to parse {response_file.name}: {e}")
                print(f"     Please check the file, correct the JSON, and re-run.")

        self.run_state = transition(
            self.run_state, RunStatus.RESPONSES_COLLECTED,
            analysts_complete=self.run_state.analysts_complete + [
                f.stem for f in responses_dir.glob("analyst_*_response.json")
                if f.stat().st_size > 0
            ],
            analysts_pending=[],
        )
        return outputs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_api_analysts(self) -> list[AnalystOutput]:
        """Run all API-delivery analysts concurrently."""
        api_configs = self.config.api_analysts
        if not api_configs:
            return []

        tasks = [
            run_analyst(
                {"model": a.model, "persona": a.persona},
                build_analyst_prompt(self.ground_truth, self.lens_config, a.persona),
                self.run_id,
            )
            for a in api_configs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid: list[AnalystOutput] = []
        for i, result in enumerate(results):
            model = api_configs[i].model
            if isinstance(result, AnalystOutput):
                valid.append(result)
                print(f"  ✅ API analyst '{model}' succeeded.")
            else:
                print(f"  ❌ API analyst '{model}' failed: {result}")
        return valid

    def _save_api_outputs(self, outputs: list[AnalystOutput]) -> None:
        for i, output in enumerate(outputs):
            path = self.analyst_outputs_dir / f"api_analyst_{i+1}_validated.json"
            path.write_text(output.model_dump_json(indent=2), encoding="utf-8")

    def _load_saved_api_outputs(self) -> list[AnalystOutput]:
        outputs: list[AnalystOutput] = []
        for path in sorted(self.analyst_outputs_dir.glob("api_analyst_*_validated.json")):
            try:
                outputs.append(AnalystOutput.model_validate_json(
                    path.read_text(encoding="utf-8")
                ))
            except Exception as e:
                print(f"  [WARN] Could not reload saved API output {path.name}: {e}")
        return outputs

    async def _run_deliberation(
        self,
        all_outputs: list[AnalystOutput],
        configs: list[dict],
    ) -> list[AnalystOutput]:
        """
        v2.1b — Run a deliberation round for all API analysts.
        Returns the Round 2 outputs. On individual failures, logs a warning and
        falls back to an empty list so the arbiter can proceed with Round 1 only.
        """
        from pydantic import ValidationError as _VE
        tasks = [
            run_deliberation_round(
                config=configs[i],
                own_output=all_outputs[i],
                peer_outputs=[all_outputs[j] for j in range(len(all_outputs)) if j != i],
                run_id=self.run_id,
            )
            for i in range(len(all_outputs))
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        delib: list[AnalystOutput] = []
        for i, result in enumerate(results):
            model = configs[i].get("model", "unknown") if isinstance(configs[i], dict) else "unknown"
            if isinstance(result, AnalystOutput):
                delib.append(result)
            elif isinstance(result, _VE):
                logger.warning("Deliberation '%s' returned schema-invalid output: %s", model, result)
            else:
                logger.warning("Deliberation '%s' failed: %s", model, result)
        return delib

    async def _run_arbiter_and_finalise(
        self, all_outputs: list[AnalystOutput]
    ) -> FinalVerdict:
        # Fetch macro context if not already injected (fail-silent).
        if self.macro_context is None:
            self.macro_context = _try_fetch_macro_context(self.ground_truth.instrument)

        overlay_was_provided = bool(self.ground_truth.m15_overlay)

        # v2.1b — run deliberation round if enabled (automated/API analysts only)
        deliberation_outputs: list[AnalystOutput] | None = None
        if self.enable_deliberation and all_outputs:
            # Build configs list from api_analysts so run_deliberation_round gets model names
            api_configs = [
                {"model": a.model, "persona": a.persona}
                for a in self.config.api_analysts
            ]
            # Align with all_outputs (which are the validated API outputs in order)
            configs_for_delib = api_configs[: len(all_outputs)]
            deliberation_outputs = await self._run_deliberation(all_outputs, configs_for_delib)
            if deliberation_outputs:
                print(f"  Deliberation complete: {len(deliberation_outputs)} Round 2 outputs.")

        # Generate and optionally write the arbiter prompt to disk
        arbiter_prompt = build_arbiter_prompt(
            analyst_outputs=all_outputs,
            risk_constraints=self.ground_truth.risk_constraints,
            run_id=self.run_id,
            overlay_delta_reports=[],
            overlay_was_provided=overlay_was_provided,
            macro_context=self.macro_context,
            deliberation_outputs=deliberation_outputs,
        )

        # Write arbiter_prompt.txt if prompt pack exists
        pack_dir = OUTPUT_BASE / self.run_id / "manual_prompts"
        if pack_dir.exists():
            pack_gen = PromptPackGenerator(
                self.ground_truth, self.config, self.lens_config
            )
            pack_gen.write_arbiter_prompt_file(arbiter_prompt)

        self.run_state = transition(self.run_state, RunStatus.ARBITER_COMPLETE)

        response = await acompletion_metered(
            run_dir=get_run_dir(self.run_id),
            run_id=self.run_id,
            stage="arbiter",
            node="execution_router",
            model=ARBITER_MODEL,
            messages=[{"role": "user", "content": arbiter_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )
        raw: str = response.choices[0].message.content
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            error_obj = {
                "error_type": "JSON_DECODE_ERROR",
                "code": "ARBITER_MALFORMED_JSON",
                "response_excerpt": _safe_excerpt(raw),
            }
            logger.warning("ExecutionRouter arbiter malformed JSON: %s", error_obj)
            verdict = _fallback_verdict(
                run_id=self.run_id,
                reason="Arbiter response malformed; defaulting to NO_TRADE.",
            )
        else:
            if not payload.get("decision"):
                logger.warning(
                    "ExecutionRouter arbiter verdict missing/empty decision; defaulting to NO_TRADE run_id=%s",
                    self.run_id,
                )
                payload["decision"] = "NO_TRADE"

            try:
                verdict = FinalVerdict.model_validate(payload)
            except Exception:
                error_obj = {
                    "error_type": "VERDICT_SCHEMA_ERROR",
                    "code": "ARBITER_INVALID_SCHEMA",
                    "response_excerpt": _safe_excerpt(raw),
                }
                logger.warning("ExecutionRouter arbiter schema validation failed: %s", error_obj)
                verdict = _fallback_verdict(
                    run_id=self.run_id,
                    reason="Arbiter response invalid; defaulting to NO_TRADE.",
                )

        # Save final verdict to disk
        verdict_path = OUTPUT_BASE / self.run_id / "final_verdict.json"
        verdict_path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")

        # Full audit log
        log_run(self.ground_truth, all_outputs, verdict)

        self.run_state = transition(self.run_state, RunStatus.VERDICT_ISSUED)
        return verdict


# ------------------------------------------------------------------
# Factory: build ExecutionConfig from API key availability
# ------------------------------------------------------------------

def build_execution_config(mode: str, analyst_personas: list[PersonaType]) -> ExecutionConfig:
    """
    Build an ExecutionConfig appropriate for the requested mode.
    If mode == "hybrid", inspects available API keys and routes accordingly.
    If mode == "manual", all analysts are MANUAL.
    If mode == "automated", all analysts must be API (caller validates key availability).
    """
    from ..core.api_key_manager import get_model_for_analyst_index

    analysts: list[AnalystConfig] = []
    for i, persona in enumerate(analyst_personas):
        analyst_id = f"analyst_{i+1}"

        if mode == "manual":
            delivery = AnalystDelivery.MANUAL
            model = None
            env_var = None
        elif mode == "automated":
            model, env_var = get_model_for_analyst_index(i)
            if model is None:
                raise RuntimeError(
                    f"Automated mode requires API keys for all analysts. "
                    f"Analyst slot {i+1} has no available model. "
                    f"Run `python cli.py status` to see which keys are missing."
                )
            delivery = AnalystDelivery.API
        else:  # hybrid — use API if key available, else manual
            model, env_var = get_model_for_analyst_index(i)
            if model:
                delivery = AnalystDelivery.API
            else:
                delivery = AnalystDelivery.MANUAL
                model = None
                env_var = None

        analysts.append(AnalystConfig(
            analyst_id=analyst_id,
            persona=persona,
            delivery=delivery,
            model=model,
            api_key_env_var=env_var,
        ))

    return ExecutionConfig(mode=mode, analysts=analysts)
