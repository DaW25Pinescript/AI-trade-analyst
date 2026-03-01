"""
Ticket Draft Builder — v2.0

Maps a FinalVerdict + GroundTruthPacket to a partial ticket_draft dict
that is ready to pre-populate the browser app's ticket form, returned
as part of the POST /analyse response envelope.

The draft is NOT schema-valid on its own — many required ticket fields
need user input (e.g. instrument setup details, exact price levels).
It is a best-effort pre-population. Callers must treat numeric price
fields as Optional[float] and never depend on them being non-null.
"""
import re
from typing import Optional

from ..models.arbiter_output import FinalVerdict
from ..models.ground_truth import GroundTruthPacket

# ── Enum maps ─────────────────────────────────────────────────────────────────

_BIAS_MAP: dict[str, str] = {
    "bullish": "Bullish",
    "bearish": "Bearish",
    "neutral": "Neutral",
    "ranging": "Range",
}

_DECISION_MAP: dict[str, str] = {
    "ENTER_LONG": "LONG",
    "ENTER_SHORT": "SHORT",
    "WAIT_FOR_CONFIRMATION": "WAIT",
    "NO_TRADE": "WAIT",
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _try_parse_price(text: str) -> Optional[float]:
    """
    Extract the first decimal number from a price description string.
    Returns None when no numeric value can be identified.
    """
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _conviction_from_confidence(confidence: float) -> str:
    if confidence >= 0.80:
        return "Very High"
    if confidence >= 0.65:
        return "High"
    if confidence >= 0.50:
        return "Medium"
    return "Low"


def _confluence_score(analyst_agreement_pct: int) -> int:
    """Map 0–100 analyst agreement percentage to a 1–10 confluence scale."""
    return min(10, max(1, round(analyst_agreement_pct / 10)))


# ── Public API ─────────────────────────────────────────────────────────────────


def build_ticket_draft(
    verdict: FinalVerdict,
    packet: GroundTruthPacket,
) -> dict:
    """
    Return a partial ticket_draft dict built from a FinalVerdict +
    GroundTruthPacket. Intended for inclusion in the POST /analyse
    response envelope so the browser app can pre-populate form fields.

    Fields that require human input are included as None or empty strings.
    """
    draft: dict = {}

    # ── Traceability ──────────────────────────────────────────────────────────
    draft["source_run_id"] = packet.run_id
    if packet.source_ticket_id:
        draft["source_ticket_id"] = packet.source_ticket_id

    # ── Enum fields ───────────────────────────────────────────────────────────
    draft["rawAIReadBias"] = _BIAS_MAP.get(verdict.final_bias.lower(), "")
    draft["decisionMode"] = _DECISION_MAP.get(verdict.decision, "WAIT")
    draft["aiEdgeScore"] = round(verdict.overall_confidence, 4)

    conviction = _conviction_from_confidence(verdict.overall_confidence)

    # ── Gate ──────────────────────────────────────────────────────────────────
    if verdict.decision == "NO_TRADE" or not verdict.approved_setups:
        draft["gate"] = {
            "status": "WAIT",
            "waitReasonCode": "",
            "reentryCondition": "; ".join(verdict.no_trade_conditions)
            if verdict.no_trade_conditions
            else "",
            "reentryTime": "",
        }
    else:
        draft["gate"] = {
            "status": "PROCEED",
            "waitReasonCode": "",
            "reentryCondition": "",
            "reentryTime": "",
        }

    # ── Best approved setup ───────────────────────────────────────────────────
    if verdict.approved_setups:
        setup = verdict.approved_setups[0]

        draft["entry"] = {
            "zone": setup.entry_zone,
            "priceMin": None,
            "priceMax": None,
            "notes": f"AI setup type: {setup.type}",
        }

        draft["stop"] = {
            "price": _try_parse_price(setup.stop),
            "logic": "Structure-based + buffer",
            "rationale": setup.stop,
        }

        _labels = ["TP1", "TP2", "TP3"]
        draft["targets"] = [
            {
                "label": _labels[i],
                "price": _try_parse_price(t),
                "rationale": t,
            }
            for i, t in enumerate(setup.targets[:3])
        ]

    # ── Checklist (partial — only fields mappable without user input) ─────────
    draft["checklist"] = {
        "confluenceScore": _confluence_score(verdict.analyst_agreement_pct),
        "conviction": conviction,
    }

    # ── Screenshots (from packet metadata) ───────────────────────────────────
    draft["screenshots"] = {
        "cleanCharts": [
            {
                "timeframe": meta.timeframe,
                "lens": meta.lens,
                "evidenceType": meta.evidence_type,
            }
            for meta in packet.screenshot_metadata
        ],
        "m15Overlay": (
            {
                "timeframe": packet.m15_overlay_metadata.timeframe,
                "lens": packet.m15_overlay_metadata.lens,
                "evidenceType": packet.m15_overlay_metadata.evidence_type,
                "indicatorClaims": packet.m15_overlay_metadata.indicator_claims or [],
                "indicatorSource": packet.m15_overlay_metadata.indicator_source or "",
                "settingsLocked": packet.m15_overlay_metadata.settings_locked or False,
            }
            if packet.m15_overlay_metadata
            else None
        ),
    }

    draft["shadowMode"] = False
    return draft
