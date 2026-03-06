"""
Input sanitisation for user-supplied market parameters.

Prevents prompt injection by validating and constraining all fields that are
interpolated into LLM prompts. Every field that flows into a prompt template
must pass through one of these validators first.

Audit ref: Security Finding #2 (CWE-94 — Prompt Injection via User-Controlled Fields)
"""
import re
from typing import Optional

# ── Allowed value sets ───────────────────────────────────────────────────────

ALLOWED_INSTRUMENTS = re.compile(r"^[A-Za-z0-9._/]{1,20}$")
ALLOWED_SESSIONS = frozenset({
    "NY", "London", "Asia", "Tokyo", "Sydney",
    "ny", "london", "asia", "tokyo", "sydney",
})
ALLOWED_REGIMES = frozenset({
    "trending", "ranging", "unknown",
    "Trending", "Ranging", "Unknown",
})
ALLOWED_NEWS_RISK = re.compile(r"^[A-Za-z0-9_ /-]{0,100}$")
ALLOWED_NO_TRADE_WINDOW = re.compile(r"^[A-Za-z0-9_ /-]{1,50}$")

# Max length for free-text fields that reach prompts
_MAX_FREETEXT_LEN = 200


def sanitise_instrument(value: str) -> str:
    """Validate instrument name (e.g. XAUUSD, NAS100, BTC/USD)."""
    value = value.strip()
    if not ALLOWED_INSTRUMENTS.match(value):
        raise ValueError(
            f"Invalid instrument '{value[:40]}': must be 1-20 alphanumeric/._/ characters."
        )
    return value


def sanitise_session(value: str) -> str:
    """Validate session name against known trading sessions."""
    value = value.strip()
    if value not in ALLOWED_SESSIONS:
        raise ValueError(
            f"Invalid session '{value[:40]}': must be one of {sorted(ALLOWED_SESSIONS)}."
        )
    return value


def sanitise_market_regime(value: str) -> str:
    """Validate market regime against known values."""
    value = value.strip()
    if value not in ALLOWED_REGIMES:
        raise ValueError(
            f"Invalid market_regime '{value[:40]}': must be one of {sorted(ALLOWED_REGIMES)}."
        )
    return value


def sanitise_news_risk(value: str) -> str:
    """Validate news_risk field — short alphanumeric descriptor."""
    value = value.strip()
    if not ALLOWED_NEWS_RISK.match(value):
        raise ValueError(
            f"Invalid news_risk: must be alphanumeric/spaces/dashes, max 100 chars."
        )
    return value


def sanitise_no_trade_windows(windows: list[str]) -> list[str]:
    """Validate each no-trade window name."""
    result = []
    for w in windows:
        w = w.strip()
        if not ALLOWED_NO_TRADE_WINDOW.match(w):
            raise ValueError(
                f"Invalid no_trade_window '{w[:40]}': must be alphanumeric/spaces/dashes, 1-50 chars."
            )
        result.append(w)
    return result


def sanitise_open_positions(positions: list) -> list:
    """Validate open_positions — must be a list of dicts or simple values, serialised length bounded."""
    import json
    serialised = json.dumps(positions)
    if len(serialised) > 2000:
        raise ValueError(
            f"open_positions JSON too large ({len(serialised)} chars, max 2000)."
        )
    return positions


def sanitise_freetext(value: str, field_name: str, max_len: int = _MAX_FREETEXT_LEN) -> str:
    """Generic sanitiser for short free-text fields that reach prompts."""
    value = value.strip()
    if len(value) > max_len:
        raise ValueError(
            f"{field_name} too long ({len(value)} chars, max {max_len})."
        )
    # Strip any control characters except newline/tab
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return value
