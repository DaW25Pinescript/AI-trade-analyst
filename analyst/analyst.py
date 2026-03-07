"""Phase 3E LLM analyst: call, parse, validate.

Receives StructureDigest (never raw structure block).
Produces AnalystVerdict + ReasoningBlock.
Post-parse validates schema compliance and hard constraint enforcement.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from analyst.contracts import (
    AnalystVerdict,
    ReasoningBlock,
    StructureDigest,
)
from analyst.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from market_data_officer.officer.contracts import MarketPacketV2

VALID_VERDICTS = {"long_bias", "short_bias", "no_trade", "conditional", "no_data"}
VALID_CONFIDENCES = {"high", "moderate", "low", "none"}
VALID_LTF_ALIGNMENTS = {"aligned", "mixed", "conflicted", "unknown"}


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the LLM API and return the raw response text.

    Uses litellm for multi-provider support. Falls back to a simple
    openai-compatible call if litellm is not available.
    """
    model = os.environ.get("ANALYST_LLM_MODEL", "gpt-4o-mini")

    try:
        import litellm
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except ImportError:
        pass

    # Fallback: try openai directly
    try:
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except ImportError:
        raise RuntimeError(
            "No LLM client available. Install litellm or openai: "
            "pip install litellm"
        )


def parse_llm_response(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse the LLM JSON response into verdict and reasoning dicts.

    The LLM should return a single JSON object with "verdict" and "reasoning" keys.
    Handles common issues like markdown code fences.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    parsed = json.loads(text)

    if "verdict" not in parsed:
        raise ValueError("LLM response missing 'verdict' key")
    if "reasoning" not in parsed:
        raise ValueError("LLM response missing 'reasoning' key")

    return parsed["verdict"], parsed["reasoning"]


def _to_verdict(data: dict[str, Any], digest: StructureDigest) -> AnalystVerdict:
    """Convert parsed dict to AnalystVerdict dataclass."""
    return AnalystVerdict(
        instrument=data.get("instrument", digest.instrument),
        as_of_utc=data.get("as_of_utc", digest.as_of_utc),
        verdict=data["verdict"],
        confidence=data["confidence"],
        structure_gate=data.get("structure_gate", digest.structure_gate),
        htf_bias=data.get("htf_bias", digest.htf_bias),
        ltf_structure_alignment=data.get("ltf_structure_alignment", "unknown"),
        active_fvg_context=data.get("active_fvg_context", digest.active_fvg_context),
        recent_sweep_signal=data.get("recent_sweep_signal", digest.recent_sweep_signal),
        structure_supports=data.get("structure_supports", []),
        structure_conflicts=data.get("structure_conflicts", []),
        no_trade_flags=data.get("no_trade_flags", []),
        caution_flags=data.get("caution_flags", []),
    )


def _to_reasoning(data: dict[str, Any]) -> ReasoningBlock:
    """Convert parsed dict to ReasoningBlock dataclass."""
    return ReasoningBlock(
        summary=data.get("summary", ""),
        htf_context=data.get("htf_context", ""),
        liquidity_context=data.get("liquidity_context", ""),
        fvg_context=data.get("fvg_context", ""),
        sweep_context=data.get("sweep_context", ""),
        verdict_rationale=data.get("verdict_rationale", ""),
    )


def validate_verdict(verdict: AnalystVerdict, digest: StructureDigest) -> None:
    """Post-parse validation of LLM verdict against digest constraints.

    Raises ValueError on any violation.
    """
    if verdict.verdict not in VALID_VERDICTS:
        raise ValueError(f"Invalid verdict value: {verdict.verdict}")

    if verdict.confidence not in VALID_CONFIDENCES:
        raise ValueError(f"Invalid confidence value: {verdict.confidence}")

    if verdict.ltf_structure_alignment not in VALID_LTF_ALIGNMENTS:
        raise ValueError(
            f"Invalid ltf_structure_alignment: {verdict.ltf_structure_alignment}"
        )

    # Structure gate must match digest
    if verdict.structure_gate != digest.structure_gate:
        raise ValueError(
            f"structure_gate mismatch: verdict={verdict.structure_gate}, "
            f"digest={digest.structure_gate}"
        )

    # Hard no-trade enforcement
    if digest.has_hard_no_trade():
        if verdict.verdict != "no_trade":
            raise ValueError(
                f"LLM overrode hard no-trade flag. "
                f"Flags: {digest.no_trade_flags}. Verdict: {verdict.verdict}"
            )
        if verdict.confidence != "none":
            raise ValueError("no_trade verdict must have confidence=none")

    # No-trade flags from digest must appear in verdict
    for flag in digest.no_trade_flags:
        if flag not in verdict.no_trade_flags:
            raise ValueError(
                f"Digest no_trade_flag '{flag}' missing from verdict.no_trade_flags"
            )

    # supports and conflicts must be lists
    if not isinstance(verdict.structure_supports, list):
        raise ValueError("structure_supports must be a list")
    if not isinstance(verdict.structure_conflicts, list):
        raise ValueError("structure_conflicts must be a list")


def run_analyst_llm(
    digest: StructureDigest,
    packet: MarketPacketV2,
) -> tuple[AnalystVerdict, ReasoningBlock]:
    """Run the full LLM analyst pipeline: prompt → call → parse → validate.

    Args:
        digest: Pre-computed StructureDigest.
        packet: MarketPacketV2 for supplementary context.

    Returns:
        (AnalystVerdict, ReasoningBlock) tuple.
    """
    user_prompt = build_user_prompt(digest, packet)
    raw_response = call_llm(SYSTEM_PROMPT, user_prompt)

    verdict_data, reasoning_data = parse_llm_response(raw_response)

    verdict = _to_verdict(verdict_data, digest)
    reasoning = _to_reasoning(reasoning_data)

    validate_verdict(verdict, digest)

    return verdict, reasoning
