"""
Generates the Manual Prompt Pack for a run.

The pack is a self-contained folder the user can open and use with any AI chat
interface — no technical knowledge of the system required.

Output layout:
  output/runs/{run_id}/
  ├── ground_truth.json
  ├── execution_config.json
  ├── state.json
  └── manual_prompts/
      ├── README.txt
      ├── analyst_1_DEFAULT_ANALYST.txt
      ├── analyst_2_RISK_OFFICER.txt
      ├── ...
      ├── charts/
      │   ├── D1_screenshot.png
      │   └── ...
      └── responses/
          ├── analyst_1_response.json    ← empty stubs
          └── ...
"""
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.ground_truth import GroundTruthPacket
from ..models.execution_config import AnalystConfig, ExecutionConfig
from ..models.lens_config import LensConfig
from .lens_loader import load_active_lens_contracts, load_persona_prompt
from .analyst_prompt_builder import OUTPUT_SCHEMA

OUTPUT_BASE = Path(__file__).parent.parent / "output" / "runs"

_SEP = "═" * 63
_THIN = "─" * 63


# ---------------------------------------------------------------------------
# README template
# ---------------------------------------------------------------------------

def _build_readme(
    run_id: str,
    instrument: str,
    session: str,
    timestamp: str,
    analyst_configs: list[AnalystConfig],
) -> str:
    analyst_lines = "\n".join(
        f"      Analyst {i+1} → analyst_{i+1}_{a.persona.value.upper()}.txt"
        for i, a in enumerate(analyst_configs)
    )

    return f"""{_SEP}
AI ANALYST — MANUAL ANALYSIS PACK
{_SEP}
Run ID:     {run_id}
Instrument: {instrument}
Session:    {session}
Generated:  {timestamp}
{_SEP}

INSTRUCTIONS
{_THIN}

STEP 1 — FOR EACH ANALYST PROMPT FILE:
  a) Open your preferred AI chat (Claude, ChatGPT, Grok, Gemini, etc.)
  b) Start a NEW conversation (very important — no prior context)
  c) Attach ALL chart images from the charts/ folder
  d) Copy and paste the ENTIRE contents of the analyst prompt file
  e) Send and wait for the response

  Prompt files for this run:
{analyst_lines}

STEP 2 — SAVE THE RESPONSE:
  a) Copy the ENTIRE JSON response the AI gives you
  b) Paste it into the corresponding file in the responses/ folder
     (e.g. analyst_1_response.json for analyst_1_DEFAULT_ANALYST.txt)
  c) Save the file

STEP 3 — RUN THE ARBITER:
  Once all response files are filled in, return to the terminal and run:

    python cli.py arbiter --run-id {run_id}

  The system will validate all responses and produce the Final Verdict.

TIPS
{_THIN}
- Use DIFFERENT AI models for different analysts if possible.
  This reduces model collusion and gives richer disagreement.
  Suggested: Analyst 1 → Claude, Analyst 2 → ChatGPT,
             Analyst 3 → Grok,    Analyst 4 → Gemini

- If the AI doesn't return valid JSON, paste the response anyway.
  The system will attempt to extract the JSON automatically and
  flag any issues for you to fix.

- You can use fewer than 4 analysts (minimum 2 required for Arbiter).
  Just leave unused response files empty.

- The Arbiter prompt is NOT generated until you run Step 3.
  This ensures the Arbiter only ever sees completed analyst outputs.

IMPORTANT
{_THIN}
- Each analyst must be in a FRESH conversation with no prior context.
- Do NOT share one analyst's response with another AI before they respond.
- Do NOT modify the prompt files — they contain structured instructions
  the AI must follow exactly.
"""


# ---------------------------------------------------------------------------
# Analyst prompt template
# ---------------------------------------------------------------------------

def _build_analyst_prompt_file(
    analyst_number: int,
    total_analysts: int,
    persona_name: str,
    persona_content: str,
    lens_content: str,
    ground_truth: GroundTruthPacket,
    run_id: str,
    timestamp: str,
) -> str:
    gt = ground_truth
    rc = gt.risk_constraints
    ctx = gt.context
    chart_count = len(gt.charts)
    timeframes_str = ", ".join(gt.timeframes)
    no_trade_str = ", ".join(rc.no_trade_windows) if rc.no_trade_windows else "None"
    open_pos_str = json.dumps(ctx.open_positions) if ctx.open_positions else "None"

    return f"""{_SEP}
AI ANALYST PROMPT — Analyst {analyst_number} of {total_analysts} ({persona_name})
Run ID: {run_id}
Instrument: {gt.instrument} | Session: {gt.session} | {timestamp}
{_SEP}

IMPORTANT INSTRUCTIONS FOR YOU (THE AI RECEIVING THIS PROMPT):
- Attached to this message are {chart_count} chart screenshot(s) of {gt.instrument}
- You must analyse ALL timeframes shown: {timeframes_str}
- You must return ONLY a valid JSON object — no explanation, no prose
- Do not add markdown code fences (no ```json)
- If you cannot determine something, use null — never guess

{_SEP}
SECTION 1 — YOUR ROLE & PERSONA
{_SEP}

{persona_content}

{_SEP}
SECTION 2 — ACTIVE ANALYSIS LENSES (RULES YOU MUST FOLLOW)
{_SEP}

{lens_content}

{_SEP}
SECTION 3 — MARKET DATA (DO NOT MODIFY)
{_SEP}

Instrument:          {gt.instrument}
Session:             {gt.session}
Timeframes provided: {timeframes_str}
Account Balance:     {ctx.account_balance}
Open Positions:      {open_pos_str}
Market Regime:       {ctx.market_regime}
News Risk:           {ctx.news_risk}
Min R:R:             {rc.min_rr}
Max Risk / Trade:    {rc.max_risk_per_trade}%
Max Daily Risk:      {rc.max_daily_risk}%
No-Trade Windows:    {no_trade_str}

{_SEP}
SECTION 4 — REQUIRED JSON OUTPUT FORMAT
{_SEP}

Return ONLY this JSON object, filled in with your analysis.
Do not include any text before or after the JSON.

{OUTPUT_SCHEMA}

{_SEP}
HARD RULES — YOU MUST ENFORCE THESE IN YOUR OUTPUT:
- If setup_valid is false → recommended_action MUST be NO_TRADE
- If confidence < 0.45   → recommended_action MUST be NO_TRADE
- If disqualifiers list is non-empty → recommended_action MUST be NO_TRADE
- NO_TRADE is a valid and respected outcome — do not avoid it
{_SEP}

Please analyse the attached charts now and return only the JSON.
"""


# ---------------------------------------------------------------------------
# Arbiter prompt wrapper (written to file after responses collected)
# ---------------------------------------------------------------------------

def _build_arbiter_prompt_file(run_id: str, arbiter_prompt_body: str) -> str:
    return f"""{_SEP}
AI ANALYST — ARBITER PROMPT
Run ID: {run_id}
{_SEP}

INSTRUCTIONS:
Paste this prompt into any AI chat (no images needed — text only).
Copy the JSON response back into:
  output/runs/{run_id}/arbiter_response.json

{_SEP}

{arbiter_prompt_body}

{_SEP}
"""


# ---------------------------------------------------------------------------
# PromptPackGenerator
# ---------------------------------------------------------------------------

class PromptPackGenerator:
    def __init__(
        self,
        ground_truth: GroundTruthPacket,
        execution_config: ExecutionConfig,
        lens_config: LensConfig,
    ) -> None:
        self.ground_truth = ground_truth
        self.execution_config = execution_config
        self.lens_config = lens_config
        self.run_id = ground_truth.run_id
        self.run_dir = OUTPUT_BASE / self.run_id
        self.prompts_dir = self.run_dir / "manual_prompts"
        self.charts_dir = self.prompts_dir / "charts"
        self.responses_dir = self.prompts_dir / "responses"
        self.analyst_outputs_dir = self.run_dir / "analyst_outputs"

    def generate(self) -> Path:
        """
        Create the full prompt pack on disk.
        Returns the path to the manual_prompts/ directory.
        """
        # Create directory tree
        for d in [self.prompts_dir, self.charts_dir, self.responses_dir,
                  self.analyst_outputs_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Persist ground truth (charts excluded — saved separately as image files)
        gt_dict = self.ground_truth.model_dump(exclude={"charts"}, mode="json")
        (self.run_dir / "ground_truth.json").write_text(
            json.dumps(gt_dict, indent=2, default=str), encoding="utf-8"
        )

        # Persist execution config
        (self.run_dir / "execution_config.json").write_text(
            self.execution_config.model_dump_json(indent=2), encoding="utf-8"
        )

        # Save chart images to charts/
        self._save_charts()

        # Determine which analysts need manual prompts
        manual_analysts = self.execution_config.manual_analysts
        total = len(self.execution_config.analysts)

        # Pre-load lens content (same for all analysts)
        lens_content = load_active_lens_contracts(self.lens_config)
        timestamp = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")

        # Generate analyst prompt files and response stubs
        for i, analyst in enumerate(manual_analysts):
            slot_number = self.execution_config.analysts.index(analyst) + 1
            persona_name = analyst.persona.value.upper()
            persona_content = load_persona_prompt(analyst.persona)

            prompt_text = _build_analyst_prompt_file(
                analyst_number=slot_number,
                total_analysts=total,
                persona_name=persona_name,
                persona_content=persona_content,
                lens_content=lens_content,
                ground_truth=self.ground_truth,
                run_id=self.run_id,
                timestamp=timestamp,
            )

            prompt_filename = f"analyst_{slot_number}_{persona_name}.txt"
            (self.prompts_dir / prompt_filename).write_text(prompt_text, encoding="utf-8")

            # Empty response stub
            response_filename = f"analyst_{slot_number}_response.json"
            response_path = self.responses_dir / response_filename
            if not response_path.exists():
                response_path.write_text("", encoding="utf-8")

        # README
        readme_text = _build_readme(
            run_id=self.run_id,
            instrument=self.ground_truth.instrument,
            session=self.ground_truth.session,
            timestamp=timestamp,
            analyst_configs=manual_analysts,
        )
        (self.prompts_dir / "README.txt").write_text(readme_text, encoding="utf-8")

        return self.prompts_dir

    def write_arbiter_prompt_file(self, arbiter_prompt_body: str) -> Path:
        """
        Write the arbiter_prompt.txt file. Called after all analyst responses
        are collected — the Arbiter should never be generated before that.
        """
        content = _build_arbiter_prompt_file(self.run_id, arbiter_prompt_body)
        path = self.prompts_dir / "arbiter_prompt.txt"
        path.write_text(content, encoding="utf-8")
        return path

    def _save_charts(self) -> None:
        """Decode base64 chart images and save them to charts/ directory."""
        for timeframe, b64_data in self.ground_truth.charts.items():
            if not b64_data:
                continue
            try:
                img_bytes = base64.b64decode(b64_data)
                filename = f"{timeframe}_screenshot.png"
                (self.charts_dir / filename).write_bytes(img_bytes)
            except Exception as e:
                print(f"[WARN] Could not save chart '{timeframe}': {e}")
