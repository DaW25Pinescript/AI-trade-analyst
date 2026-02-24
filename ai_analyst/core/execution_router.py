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
from pathlib import Path
from typing import Optional

from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig
from ..models.execution_config import (
    AnalystConfig, AnalystDelivery, ExecutionConfig, RunState, RunStatus,
)
from ..models.analyst_output import AnalystOutput
from ..models.arbiter_output import FinalVerdict
from ..models.persona import PersonaType
from ..graph.analyst_nodes import run_analyst, MINIMUM_VALID_ANALYSTS
from .analyst_prompt_builder import build_analyst_prompt
from .arbiter_prompt_builder import build_arbiter_prompt
from .prompt_pack_generator import PromptPackGenerator
from .json_extractor import extract_json
from .run_state_manager import transition, save_run_state
from .logger import log_run

OUTPUT_BASE = Path(__file__).parent.parent / "output" / "runs"

# Arbiter model — text-only, cheaper (same as graph/arbiter_node.py)
ARBITER_MODEL = "claude-haiku-4-5-20251001"


class ExecutionRouter:
    def __init__(
        self,
        config: ExecutionConfig,
        ground_truth: GroundTruthPacket,
        lens_config: LensConfig,
        run_state: RunState,
    ) -> None:
        self.config = config
        self.ground_truth = ground_truth
        self.lens_config = lens_config
        self.run_state = run_state
        self.run_id = ground_truth.run_id
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

        # Fully automated — run arbiter immediately
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

    async def _run_arbiter_and_finalise(
        self, all_outputs: list[AnalystOutput]
    ) -> FinalVerdict:
        from litellm import acompletion

        # Generate and optionally write the arbiter prompt to disk
        arbiter_prompt = build_arbiter_prompt(
            analyst_outputs=all_outputs,
            risk_constraints=self.ground_truth.risk_constraints,
            run_id=self.run_id,
        )

        # Write arbiter_prompt.txt if prompt pack exists
        pack_dir = OUTPUT_BASE / self.run_id / "manual_prompts"
        if pack_dir.exists():
            pack_gen = PromptPackGenerator(
                self.ground_truth, self.config, self.lens_config
            )
            pack_gen.write_arbiter_prompt_file(arbiter_prompt)

        self.run_state = transition(self.run_state, RunStatus.ARBITER_COMPLETE)

        response = await acompletion(
            model=ARBITER_MODEL,
            messages=[{"role": "user", "content": arbiter_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )
        raw: str = response.choices[0].message.content
        verdict = FinalVerdict.model_validate_json(raw)

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
