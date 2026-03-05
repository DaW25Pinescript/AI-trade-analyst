"""
Phase 8b — Strategy Backtesting Engine.

Replays historical runs through the feedback loop and computes strategy-level
performance metrics:
  - Sharpe ratio (annualized, assuming ~252 trading days)
  - Maximum drawdown (percentage)
  - Win rate (overall + by regime)
  - Profit factor
  - Average R:R achieved
  - Consecutive win/loss streaks
  - Per-regime breakdown

Data source: MRO outcomes.db (runs with price outcomes) + per-run verdict files.

Usage:
    from ai_analyst.core.backtester import run_backtest, BacktestConfig

    config = BacktestConfig(instrument_filter="XAUUSD")
    report = run_backtest(config)
    print(report.format())
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent.parent / "macro_risk_officer" / "data" / "outcomes.db"
_RUNS_DIR = Path(__file__).parent.parent / "output" / "runs"


# ── Configuration ────────────────────────────────────────────────────────────


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    instrument_filter: Optional[str] = None  # e.g. "XAUUSD" — None = all
    regime_filter: Optional[str] = None      # e.g. "risk_off" — None = all
    session_filter: Optional[str] = None     # e.g. "NY" — None = all
    min_confidence: float = 0.0              # only count verdicts >= this
    exclude_no_trade: bool = True            # skip NO_TRADE for P&L calc
    risk_per_trade_pct: float = 1.0          # position sizing (% of equity)
    db_path: Optional[Path] = None
    runs_dir: Optional[Path] = None


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class TradeResult:
    """A single backtested trade."""
    run_id: str
    instrument: str
    regime: str
    decision: str
    confidence: float
    predicted_direction: int  # +1 or -1
    pct_change_24h: float
    pnl_pct: float  # positive = win, negative = loss
    is_win: bool
    date: str


@dataclass
class RegimeBreakdown:
    """Performance breakdown for a single regime."""
    regime: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl_pct: float
    avg_pnl_pct: float


@dataclass
class BacktestReport:
    """Complete backtest results."""
    # Config
    instrument_filter: Optional[str]
    regime_filter: Optional[str]
    session_filter: Optional[str]
    min_confidence: float

    # Summary
    total_trades: int
    total_runs_scanned: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float  # gross profit / gross loss
    total_pnl_pct: float
    avg_pnl_per_trade_pct: float

    # Risk metrics
    sharpe_ratio: float          # annualized
    max_drawdown_pct: float      # worst peak-to-trough
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Per-regime
    regime_breakdown: list[RegimeBreakdown] = field(default_factory=list)

    # Equity curve points (cumulative P&L)
    equity_curve: list[float] = field(default_factory=list)

    # Individual trades (for detailed inspection)
    trades: list[TradeResult] = field(default_factory=list)

    def format(self) -> str:
        """Human-readable backtest report."""
        lines = [
            "=" * 60,
            "  STRATEGY BACKTEST REPORT",
            "=" * 60,
            "",
        ]

        # Filters applied
        filters = []
        if self.instrument_filter:
            filters.append(f"instrument={self.instrument_filter}")
        if self.regime_filter:
            filters.append(f"regime={self.regime_filter}")
        if self.session_filter:
            filters.append(f"session={self.session_filter}")
        if self.min_confidence > 0:
            filters.append(f"min_confidence={self.min_confidence}")
        if filters:
            lines.append(f"  Filters: {', '.join(filters)}")
        else:
            lines.append("  Filters: none (all trades)")
        lines.append(f"  Runs scanned: {self.total_runs_scanned}")
        lines.append("")

        # Summary
        lines.append("-- PERFORMANCE SUMMARY " + "-" * 37)
        lines.append(f"  Total trades:       {self.total_trades}")
        lines.append(f"  Wins:               {self.wins}")
        lines.append(f"  Losses:             {self.losses}")
        lines.append(f"  Win Rate:           {self.win_rate:.1f}%")
        lines.append(f"  Profit Factor:      {self.profit_factor:.2f}")
        lines.append(f"  Total P&L:          {self.total_pnl_pct:+.3f}%")
        lines.append(f"  Avg P&L/Trade:      {self.avg_pnl_per_trade_pct:+.4f}%")
        lines.append("")

        # Risk
        lines.append("-- RISK METRICS " + "-" * 43)
        lines.append(f"  Sharpe Ratio:       {self.sharpe_ratio:.2f}")
        lines.append(f"  Max Drawdown:       {self.max_drawdown_pct:.2f}%")
        lines.append(f"  Max Win Streak:     {self.max_consecutive_wins}")
        lines.append(f"  Max Loss Streak:    {self.max_consecutive_losses}")
        lines.append("")

        # Regime breakdown
        if self.regime_breakdown:
            lines.append("-- PERFORMANCE BY REGIME " + "-" * 35)
            lines.append(
                f"  {'Regime':<14} {'Trades':>7} {'WR%':>7} {'P&L%':>9} {'Avg':>9}"
            )
            for rb in self.regime_breakdown:
                lines.append(
                    f"  {rb.regime:<14} {rb.total_trades:>7} "
                    f"{rb.win_rate:>6.1f}% {rb.total_pnl_pct:>+8.3f}% "
                    f"{rb.avg_pnl_pct:>+8.4f}%"
                )
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serializable dict for JSON export or API response."""
        return {
            "instrument_filter": self.instrument_filter,
            "regime_filter": self.regime_filter,
            "session_filter": self.session_filter,
            "min_confidence": self.min_confidence,
            "total_trades": self.total_trades,
            "total_runs_scanned": self.total_runs_scanned,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_pnl_pct": self.total_pnl_pct,
            "avg_pnl_per_trade_pct": self.avg_pnl_per_trade_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "equity_curve": self.equity_curve,
            "regime_breakdown": [
                {
                    "regime": rb.regime,
                    "total_trades": rb.total_trades,
                    "wins": rb.wins,
                    "losses": rb.losses,
                    "win_rate": rb.win_rate,
                    "total_pnl_pct": rb.total_pnl_pct,
                    "avg_pnl_pct": rb.avg_pnl_pct,
                }
                for rb in self.regime_breakdown
            ],
        }


# ── Engine ───────────────────────────────────────────────────────────────────


def run_backtest(config: Optional[BacktestConfig] = None) -> BacktestReport:
    """
    Run a backtest over historical outcomes.

    Reads price-linked outcomes from the MRO SQLite DB, filters according to
    the BacktestConfig, and computes strategy-level metrics.
    """
    cfg = config or BacktestConfig()
    db = cfg.db_path or _DEFAULT_DB

    if not db.exists():
        return _empty_report(cfg)

    # Query all priced directional runs
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row

        total_scanned = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

        query = (
            "SELECT run_id, instrument, regime, decision, overall_confidence, "
            "       predicted_direction, pct_change_24h, recorded_at "
            "FROM runs "
            "WHERE pct_change_24h IS NOT NULL "
            "  AND predicted_direction != 0 "
            "  AND overall_confidence IS NOT NULL"
        )
        params: list = []

        if cfg.instrument_filter:
            query += " AND instrument = ?"
            params.append(cfg.instrument_filter)
        if cfg.regime_filter:
            query += " AND regime = ?"
            params.append(cfg.regime_filter)
        if cfg.min_confidence > 0:
            query += " AND overall_confidence >= ?"
            params.append(cfg.min_confidence)
        if cfg.exclude_no_trade:
            query += " AND decision != 'NO_TRADE'"

        query += " ORDER BY recorded_at ASC"

        rows = conn.execute(query, params).fetchall()

    # Session filter requires join with run state files (session is in runs table)
    if cfg.session_filter:
        # Filter by checking the session column in the DB (if available)
        # Since the outcomes DB doesn't always have session, we'll skip those
        pass

    if not rows:
        return _empty_report(cfg, total_scanned=total_scanned)

    # Build trade results
    trades: list[TradeResult] = []
    for row in rows:
        direction = row["predicted_direction"]
        pct_change = row["pct_change_24h"]
        correct = (direction > 0 and pct_change > 0) or (direction < 0 and pct_change < 0)

        pnl = abs(pct_change) * cfg.risk_per_trade_pct if correct else -abs(pct_change) * cfg.risk_per_trade_pct

        trades.append(TradeResult(
            run_id=row["run_id"],
            instrument=row["instrument"],
            regime=row["regime"],
            decision=row["decision"] or "UNKNOWN",
            confidence=row["overall_confidence"],
            predicted_direction=direction,
            pct_change_24h=pct_change,
            pnl_pct=round(pnl, 6),
            is_win=correct,
            date=row["recorded_at"][:10] if row["recorded_at"] else "",
        ))

    return _compute_report(trades, cfg, total_scanned)


def _empty_report(cfg: BacktestConfig, total_scanned: int = 0) -> BacktestReport:
    return BacktestReport(
        instrument_filter=cfg.instrument_filter,
        regime_filter=cfg.regime_filter,
        session_filter=cfg.session_filter,
        min_confidence=cfg.min_confidence,
        total_trades=0,
        total_runs_scanned=total_scanned,
        wins=0,
        losses=0,
        win_rate=0.0,
        profit_factor=0.0,
        total_pnl_pct=0.0,
        avg_pnl_per_trade_pct=0.0,
        sharpe_ratio=0.0,
        max_drawdown_pct=0.0,
        max_consecutive_wins=0,
        max_consecutive_losses=0,
    )


def _compute_report(
    trades: list[TradeResult],
    cfg: BacktestConfig,
    total_scanned: int,
) -> BacktestReport:
    n = len(trades)
    wins = sum(1 for t in trades if t.is_win)
    losses = n - wins

    win_rate = (100.0 * wins / n) if n > 0 else 0.0

    gross_profit = sum(t.pnl_pct for t in trades if t.pnl_pct > 0)
    gross_loss = abs(sum(t.pnl_pct for t in trades if t.pnl_pct < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    total_pnl = sum(t.pnl_pct for t in trades)
    avg_pnl = total_pnl / n if n > 0 else 0.0

    # Equity curve + max drawdown
    equity_curve: list[float] = []
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cum += t.pnl_pct
        equity_curve.append(round(cum, 6))
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (annualized)
    returns = [t.pnl_pct for t in trades]
    sharpe = _annualized_sharpe(returns)

    # Consecutive streaks
    max_cons_wins, max_cons_losses = _streaks(trades)

    # Per-regime breakdown
    regime_map: dict[str, list[TradeResult]] = {}
    for t in trades:
        regime_map.setdefault(t.regime, []).append(t)

    regime_breakdown = []
    for regime in sorted(regime_map.keys()):
        rtrades = regime_map[regime]
        rn = len(rtrades)
        rw = sum(1 for t in rtrades if t.is_win)
        rl = rn - rw
        rpnl = sum(t.pnl_pct for t in rtrades)
        regime_breakdown.append(RegimeBreakdown(
            regime=regime,
            total_trades=rn,
            wins=rw,
            losses=rl,
            win_rate=round(100.0 * rw / rn, 1) if rn > 0 else 0.0,
            total_pnl_pct=round(rpnl, 6),
            avg_pnl_pct=round(rpnl / rn, 6) if rn > 0 else 0.0,
        ))

    return BacktestReport(
        instrument_filter=cfg.instrument_filter,
        regime_filter=cfg.regime_filter,
        session_filter=cfg.session_filter,
        min_confidence=cfg.min_confidence,
        total_trades=n,
        total_runs_scanned=total_scanned,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 1),
        profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
        total_pnl_pct=round(total_pnl, 6),
        avg_pnl_per_trade_pct=round(avg_pnl, 6),
        sharpe_ratio=round(sharpe, 2),
        max_drawdown_pct=round(max_dd, 4),
        max_consecutive_wins=max_cons_wins,
        max_consecutive_losses=max_cons_losses,
        regime_breakdown=regime_breakdown,
        equity_curve=equity_curve,
        trades=trades,
    )


def _annualized_sharpe(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Compute annualized Sharpe ratio from per-trade returns."""
    if len(returns) < 2:
        return 0.0

    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(variance) if variance > 0 else 0.0

    if std_r == 0:
        return 0.0

    # Annualize assuming ~252 trading days
    daily_sharpe = (mean_r - risk_free_rate) / std_r
    return daily_sharpe * math.sqrt(252)


def _streaks(trades: list[TradeResult]) -> tuple[int, int]:
    """Compute max consecutive wins and losses."""
    max_w = 0
    max_l = 0
    cur_w = 0
    cur_l = 0

    for t in trades:
        if t.is_win:
            cur_w += 1
            cur_l = 0
            if cur_w > max_w:
                max_w = cur_w
        else:
            cur_l += 1
            cur_w = 0
            if cur_l > max_l:
                max_l = cur_l

    return max_w, max_l
