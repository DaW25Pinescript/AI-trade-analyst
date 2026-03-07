"""Phase 3E prompt builder: assembles LLM context from StructureDigest + packet.

The LLM never receives the raw structure block. It gets:
- StructureDigest.to_prompt_dict() — pre-digested summary
- Selected scalar fields from features.core and state_summary
"""

from __future__ import annotations

import json

from analyst.contracts import StructureDigest
from market_data_officer.officer.contracts import MarketPacketV2


SYSTEM_PROMPT = (
    "You are a disciplined ICT-style market analyst. You reason over structured market state only.\n"
    "You do not re-derive structure from raw price data. You do not interpret charts.\n"
    "Your structural knowledge comes exclusively from the structure digest provided.\n"
    "\n"
    "Your output must always contain two parts:\n"
    "1. A JSON verdict block matching the AnalystVerdict schema exactly.\n"
    "2. A JSON reasoning block matching the ReasoningBlock schema exactly.\n"
    "\n"
    "Output only valid JSON. No preamble. No markdown. No commentary outside the JSON.\n"
    "\n"
    "Your response must be a single JSON object with two top-level keys: \"verdict\" and \"reasoning\".\n"
    "\n"
    "AnalystVerdict schema:\n"
    "{\n"
    "  \"instrument\": string,\n"
    "  \"as_of_utc\": string,\n"
    "  \"verdict\": \"long_bias\" | \"short_bias\" | \"no_trade\" | \"conditional\" | \"no_data\",\n"
    "  \"confidence\": \"high\" | \"moderate\" | \"low\" | \"none\",\n"
    "  \"structure_gate\": string (must match digest value exactly),\n"
    "  \"htf_bias\": string | null,\n"
    "  \"ltf_structure_alignment\": \"aligned\" | \"mixed\" | \"conflicted\" | \"unknown\",\n"
    "  \"active_fvg_context\": string | null,\n"
    "  \"recent_sweep_signal\": string | null,\n"
    "  \"structure_supports\": [string],\n"
    "  \"structure_conflicts\": [string],\n"
    "  \"no_trade_flags\": [string],\n"
    "  \"caution_flags\": [string]\n"
    "}\n"
    "\n"
    "ReasoningBlock schema:\n"
    "{\n"
    "  \"summary\": string (2-4 sentences),\n"
    "  \"htf_context\": string,\n"
    "  \"liquidity_context\": string,\n"
    "  \"fvg_context\": string,\n"
    "  \"sweep_context\": string,\n"
    "  \"verdict_rationale\": string\n"
    "}\n"
)


def build_user_prompt(
    digest: StructureDigest,
    packet: MarketPacketV2,
) -> str:
    """Build the user prompt for the LLM analyst.

    Args:
        digest: Pre-computed StructureDigest.
        packet: MarketPacketV2 for supplementary context.

    Returns:
        Formatted user prompt string.
    """
    core = packet.features.core
    summary = packet.state_summary

    digest_json = json.dumps(digest.to_prompt_dict(), indent=2)

    parts = [
        f"Instrument: {digest.instrument}",
        f"As of: {digest.as_of_utc}",
        "",
        "--- STRUCTURE DIGEST ---",
        digest_json,
        "",
        "--- MARKET CONTEXT ---",
        f"Session: {summary.session_context}",
        f"Volatility: {summary.volatility_regime}",
        f"Momentum: {summary.momentum_state}",
        f"ATR (14): {core.atr_14}",
        f"MA50 / MA200: {core.ma_50} / {core.ma_200}",
    ]

    if digest.has_hard_no_trade():
        parts.extend([
            "",
            "--- HARD CONSTRAINTS ---",
            f"HARD NO-TRADE FLAGS PRESENT: {digest.no_trade_flags}",
            'You must set verdict = "no_trade" and confidence = "none".',
            "Do not override this constraint.",
        ])

    parts.extend([
        "",
        "Produce the AnalystVerdict and ReasoningBlock JSON now.",
    ])

    return "\n".join(parts)
