"""Pure functions and dataclasses for the backtest engine.

Provides two P/L accounting modes simultaneously:
- fixed: 1 unit per bet, P/L = odds-1 on hit, -1 on miss.
- kelly: rolling capital, bet = capital * kelly_pct.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class BetOutcome:
    score_id: int
    match_id: int
    match_date: date
    league: str
    total_score: int
    bet_type: str
    odds: Decimal
    kelly_pct: Decimal
    stake_fixed: Decimal
    stake_kelly: Decimal
    pnl_fixed: Decimal
    pnl_kelly: Decimal
    is_hit: bool


@dataclass
class BacktestStats:
    total_bets: int = 0
    hit_count: int = 0
    hit_rate: Decimal = Decimal("0")
    profit_loss_fixed: Decimal = Decimal("0")
    roi_fixed: Decimal = Decimal("0")
    profit_loss_kelly: Decimal = Decimal("0")
    roi_kelly: Decimal = Decimal("0")
    by_score_band: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_league: dict[str, dict[str, Any]] = field(default_factory=dict)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)


SCORE_BANDS: tuple[tuple[int, int, str], ...] = (
    (0, 60, "0-60"),
    (60, 72, "60-72"),
    (72, 78, "72-78"),
    (78, 84, "78-84"),
    (84, 100, "84-100"),
    (100, 120, "100-120"),
)


def decide_outcome(
    bet_type: str,
    asian_handicap: str | None,
    result: str | None,
    handicap_result: str | None = None,
) -> bool:
    """Return True when the recommended bet hits given the match result."""
    if bet_type == "draw":
        return result == "draw"
    if bet_type == "handicap_draw":
        return handicap_result == "draw"
    return False


def simulate_bet(
    *,
    odds: Decimal,
    kelly_pct: Decimal,
    current_capital: Decimal,
    is_hit: bool,
    stake_fixed: Decimal = Decimal("1"),
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (pnl_fixed, pnl_kelly, stake_kelly) for a single bet.

    ``stake_fixed`` is the real amount wagered per bet under the fixed-stake
    mode; defaults to 1 so callers that want unit accounting still work.

    Bankruptcy guard: when current_capital <= 0 the Kelly simulation is
    halted (stake_kelly = 0, pnl_kelly = 0). The fixed-stake accounting still
    applies, because it operates on ``stake_fixed`` decoupled from rolling
    capital.
    """
    if current_capital <= Decimal("0") or kelly_pct <= Decimal("0"):
        stake_kelly = Decimal("0.00")
        pnl_kelly = Decimal("0.00")
    else:
        stake_kelly = (current_capital * kelly_pct).quantize(Decimal("0.01"))
        pnl_kelly = (
            (stake_kelly * (odds - Decimal("1"))).quantize(Decimal("0.01"))
            if is_hit
            else (-stake_kelly).quantize(Decimal("0.01"))
        )
    pnl_fixed = (
        (stake_fixed * (odds - Decimal("1"))).quantize(Decimal("0.01"))
        if is_hit
        else (-stake_fixed).quantize(Decimal("0.01"))
    )
    return pnl_fixed, pnl_kelly, stake_kelly


def _band_for(score: int) -> str:
    for low, high, label in SCORE_BANDS:
        if low <= score < high:
            return label
    return "100-120"


def _empty_bucket() -> dict[str, Any]:
    return {
        "bets": 0,
        "hits": 0,
        "profit_loss_fixed": Decimal("0"),
        "profit_loss_kelly": Decimal("0"),
        "stake_fixed": Decimal("0"),
        "stake_kelly": Decimal("0"),
    }


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    bets = bucket["bets"]
    hits = bucket["hits"]
    stake_fixed = bucket["stake_fixed"]
    stake_kelly = bucket["stake_kelly"]
    hit_rate = Decimal(hits) / Decimal(bets) if bets else Decimal("0")
    roi_fixed = (
        bucket["profit_loss_fixed"] / stake_fixed if stake_fixed else Decimal("0")
    )
    roi_kelly = (
        bucket["profit_loss_kelly"] / stake_kelly if stake_kelly else Decimal("0")
    )
    return {
        "bets": bets,
        "hits": hits,
        "hit_rate": hit_rate,
        "profit_loss_fixed": bucket["profit_loss_fixed"],
        "profit_loss_kelly": bucket["profit_loss_kelly"],
        "roi_fixed": roi_fixed,
        "roi_kelly": roi_kelly,
    }


def aggregate(
    outcomes: Iterable[BetOutcome],
    *,
    initial_capital: Decimal = Decimal("10000"),
) -> BacktestStats:
    """Aggregate bet outcomes into a full BacktestStats summary."""
    outcomes_list = list(outcomes)
    stats = BacktestStats()
    if not outcomes_list:
        return stats

    stats.total_bets = len(outcomes_list)
    stats.hit_count = sum(1 for o in outcomes_list if o.is_hit)
    stats.hit_rate = Decimal(stats.hit_count) / Decimal(stats.total_bets)

    total_stake_fixed = sum((o.stake_fixed for o in outcomes_list), start=Decimal("0"))
    stats.profit_loss_fixed = sum(
        (o.pnl_fixed for o in outcomes_list), start=Decimal("0")
    )
    stats.profit_loss_kelly = sum(
        (o.pnl_kelly for o in outcomes_list), start=Decimal("0")
    )
    stats.roi_fixed = (
        stats.profit_loss_fixed / total_stake_fixed
        if total_stake_fixed
        else Decimal("0")
    )
    stats.roi_kelly = (
        stats.profit_loss_kelly / initial_capital if initial_capital else Decimal("0")
    )

    bands: dict[str, dict[str, Any]] = {}
    leagues: dict[str, dict[str, Any]] = {}
    for o in outcomes_list:
        for bucket_map, key in (
            (bands, _band_for(o.total_score)),
            (leagues, o.league),
        ):
            bucket = bucket_map.setdefault(key, _empty_bucket())
            bucket["bets"] += 1
            if o.is_hit:
                bucket["hits"] += 1
            bucket["stake_fixed"] += o.stake_fixed
            bucket["stake_kelly"] += o.stake_kelly
            bucket["profit_loss_fixed"] += o.pnl_fixed
            bucket["profit_loss_kelly"] += o.pnl_kelly

    stats.by_score_band = {k: _finalize_bucket(v) for k, v in bands.items()}
    stats.by_league = {k: _finalize_bucket(v) for k, v in leagues.items()}

    sorted_outcomes = sorted(outcomes_list, key=lambda o: o.match_date)
    curve: list[dict[str, Any]] = []
    cum_fixed = Decimal("0")
    cum_kelly = Decimal("0")
    current_day: date | None = None
    for o in sorted_outcomes:
        if current_day is None or o.match_date != current_day:
            curve.append(
                {
                    "date": o.match_date.isoformat(),
                    "cumulative_pnl_fixed": cum_fixed + o.pnl_fixed,
                    "cumulative_pnl_kelly": cum_kelly + o.pnl_kelly,
                }
            )
            current_day = o.match_date
        else:
            curve[-1]["cumulative_pnl_fixed"] += o.pnl_fixed
            curve[-1]["cumulative_pnl_kelly"] += o.pnl_kelly
        cum_fixed += o.pnl_fixed
        cum_kelly += o.pnl_kelly
    stats.equity_curve = curve

    return stats
