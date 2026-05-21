"""Pure scoring functions for the 6-dimensional model.

References the project spec and the "平/让平竞彩交易模型手册 V1.0".
Each function is total order: same inputs -> same output, no DB / IO.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

DEFAULT_WEIGHTS: dict[str, int] = {
    "euro": 25,
    "asian": 20,
    "goals": 20,
    "intent": 15,
    "compression": 20,
    "team_stats": 20,
}

ASIAN_BUCKETS: dict[str, int] = {
    "平手": 20,
    "平半": 15,
    "半球": 5,
}

HANDICAP_SCORE_MAP: list[tuple[float, int]] = [
    (0.0, 20),
    (0.25, 18),
    (0.5, 12),
    (1.0, 8),
    (1.5, 3),
]

_CUP_KEYWORDS = ("欧冠", "欧联", "亚冠", "世界杯", "杯赛", "美洲杯", "欧洲杯")


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None


def euro_score(*, win, draw, lose) -> int:
    """Score European odds structure (closer = higher).

    Spec: 0-25.
    Rule (from manual §4.1):
    - 胜/负 2.30-2.80 且 平 3.00-3.40 → 25
    - 三项离散度越小 → 越高分
    """
    w = _to_decimal(win)
    d = _to_decimal(draw)
    l_ = _to_decimal(lose)
    if not (w and d and l_):
        return 0

    in_sweet_spot = (
        Decimal("2.30") <= w <= Decimal("2.80")
        and Decimal("3.00") <= d <= Decimal("3.40")
        and Decimal("2.30") <= l_ <= Decimal("2.80")
    )
    if in_sweet_spot:
        return 25

    values = [w, d, l_]
    mean = sum(values) / 3
    max_abs_dev = max(abs(v - mean) for v in values)
    spread = float(max_abs_dev / mean)

    if spread <= 0.10:
        return 25
    if spread <= 0.20:
        return 18
    if spread <= 0.35:
        return 10
    if spread <= 0.60:
        return 5
    return 0


def asian_score(handicap_value=None, asian_handicap: str | None = None) -> int:
    """Score Asian handicap depth (shallow = better for draw).

    Accepts either a numeric handicap_value or a Chinese text label.
    Shallow handicaps score higher because they signal balanced strength.
    """
    if asian_handicap is None and isinstance(handicap_value, str):
        asian_handicap = handicap_value

    if asian_handicap and isinstance(asian_handicap, str):
        bucket = ASIAN_BUCKETS.get(asian_handicap.strip())
        if bucket is not None:
            return bucket

    hv = _to_decimal(handicap_value)
    if hv is None:
        return 0

    abs_hv = float(abs(hv))
    for threshold, score in HANDICAP_SCORE_MAP:
        if abs_hv <= threshold + 0.001:
            return score
    return 0


def goals_score(total_goals=None, *, draw_odds=None, handicap_value=None) -> int:
    """Score expected goal volume; low-scoring games favor draws.

    Uses total_goals line when available.  Falls back to a proxy
    derived from draw_odds and handicap_value (Chinese HHAD market).
    """
    g = _to_decimal(total_goals)
    if g is not None:
        if g <= Decimal("2.25"):
            return 20
        if g < Decimal("2.75"):
            return 10
        return 0

    d = _to_decimal(draw_odds)
    hv = _to_decimal(handicap_value)
    if d is None and hv is None:
        return 0

    score = 0
    if d is not None and d <= Decimal("3.20"):
        score += 10
    if hv is not None and abs(hv) <= Decimal("1"):
        score += 10
    return min(20, score)


def compression_score(draw_odds) -> int:
    d = _to_decimal(draw_odds)
    if d is None:
        return 0
    if d <= Decimal("3.20"):
        return 20
    if d < Decimal("3.60"):
        return 10
    return 0


def intent_score(competition_type: str | None, round_text: str | None) -> int:
    if competition_type in {
        "cup",
        "knockout_first_leg",
        "knockout_second_leg",
    }:
        return 15
    if round_text and ("首回合" in round_text or "次回合" in round_text):
        return 15
    return 5


def _form_balance(form: str | None) -> float:
    """Return 0..1, higher when form is mixed (contains draws or alternating)."""
    if not form:
        return 0.0
    form = form.upper()
    total = len(form)
    if total == 0:
        return 0.0
    draws = form.count("D")
    wins = form.count("W")
    losses = form.count("L")
    diversity = 1.0 - (max(wins, losses) / total)
    return (draws / total) * 0.5 + diversity * 0.5


def team_stats_score(stats: Mapping | None) -> int:
    if not stats:
        return 0

    score = 0.0

    hr = stats.get("home_rank")
    ar = stats.get("away_rank")
    if hr is not None and ar is not None:
        gap = abs(hr - ar)
        if gap <= 2:
            score += 8
        elif gap <= 5:
            score += 6
        elif gap <= 10:
            score += 3

    home_form = _form_balance(stats.get("home_recent_form"))
    away_form = _form_balance(stats.get("away_recent_form"))
    score += (home_form + away_form) * 4

    h_sd = stats.get("home_season_draws") or 0
    h_sw = stats.get("home_season_wins") or 0
    h_sl = stats.get("home_season_losses") or 0
    a_sd = stats.get("away_season_draws") or 0
    a_sw = stats.get("away_season_wins") or 0
    a_sl = stats.get("away_season_losses") or 0
    home_total = h_sd + h_sw + h_sl
    away_total = a_sd + a_sw + a_sl
    if home_total > 0 and away_total > 0:
        home_draw_rate = h_sd / home_total
        away_draw_rate = a_sd / away_total
        score += min(4.0, (home_draw_rate + away_draw_rate) * 10)

    return max(0, min(20, int(round(score))))


def _rate(numerator, denominator) -> float | None:
    if numerator is None or not denominator:
        return None
    return float(numerator) / float(denominator)


def _sum_present(*values) -> int:
    return sum(int(v or 0) for v in values)


def _form_rate(form: str | None, char: str) -> float | None:
    if not form:
        return None
    text = form.upper()
    if not text:
        return None
    return text.count(char) / len(text)


def _draw_context(stats: Mapping | None) -> dict[str, float | None]:
    if not stats:
        return {
            "season_draw_sum": None,
            "venue_draw_sum": None,
            "recent_draw_sum": None,
            "home_recent_win_rate": None,
            "away_recent_loss_rate": None,
            "rank_gap": None,
        }

    home_season_total = _sum_present(
        stats.get("home_season_wins"),
        stats.get("home_season_draws"),
        stats.get("home_season_losses"),
    )
    away_season_total = _sum_present(
        stats.get("away_season_wins"),
        stats.get("away_season_draws"),
        stats.get("away_season_losses"),
    )
    home_venue_total = _sum_present(
        stats.get("home_home_wins"),
        stats.get("home_home_draws"),
        stats.get("home_home_losses"),
    )
    away_venue_total = _sum_present(
        stats.get("away_away_wins"),
        stats.get("away_away_draws"),
        stats.get("away_away_losses"),
    )

    home_season_draw = _rate(stats.get("home_season_draws"), home_season_total)
    away_season_draw = _rate(stats.get("away_season_draws"), away_season_total)
    home_venue_draw = _rate(stats.get("home_home_draws"), home_venue_total)
    away_venue_draw = _rate(stats.get("away_away_draws"), away_venue_total)
    home_recent_draw = _form_rate(stats.get("home_recent_form"), "D")
    away_recent_draw = _form_rate(stats.get("away_recent_form"), "D")

    rank_gap = None
    if stats.get("home_rank") is not None and stats.get("away_rank") is not None:
        rank_gap = float(abs(stats["home_rank"] - stats["away_rank"]))

    return {
        "season_draw_sum": (
            home_season_draw + away_season_draw
            if home_season_draw is not None and away_season_draw is not None
            else None
        ),
        "venue_draw_sum": (
            home_venue_draw + away_venue_draw
            if home_venue_draw is not None and away_venue_draw is not None
            else None
        ),
        "recent_draw_sum": (
            home_recent_draw + away_recent_draw
            if home_recent_draw is not None and away_recent_draw is not None
            else None
        ),
        "home_recent_win_rate": _form_rate(stats.get("home_recent_form"), "W"),
        "away_recent_loss_rate": _form_rate(stats.get("away_recent_form"), "L"),
        "rank_gap": rank_gap,
    }


def empirical_draw_score(
    stats: Mapping | None,
    *,
    draw_odds=None,
    handicap_value=None,
    league_name: str | None = None,
) -> int:
    """Score draw candidates from historical feature analysis.

    Main signal: both teams already draw often, especially in the exact venue
    split (home-at-home + away-away). Odds and ranking only act as filters.
    """
    ctx = _draw_context(stats)
    d = _to_decimal(draw_odds)
    hv = _to_decimal(handicap_value)
    score = 0

    venue_sum = ctx["venue_draw_sum"]
    if venue_sum is not None:
        if venue_sum >= 0.65:
            score += 45
        elif venue_sum >= 0.55:
            score += 25
        elif venue_sum < 0.35:
            score -= 25

    season_sum = ctx["season_draw_sum"]
    if season_sum is not None:
        if season_sum >= 0.65:
            score += 35
        elif season_sum >= 0.55:
            score += 20
        elif season_sum < 0.35:
            score -= 25

    if d is not None:
        if Decimal("2.80") <= d < Decimal("3.20"):
            score += 20
        elif Decimal("3.20") <= d < Decimal("3.40"):
            score += 12
        elif d >= Decimal("3.60"):
            score -= 10

    rank_gap = ctx["rank_gap"]
    if rank_gap is not None:
        if rank_gap <= 5:
            score += 10
        elif rank_gap >= 11:
            score -= 10

    recent_sum = ctx["recent_draw_sum"]
    if recent_sum is not None and recent_sum >= 0.5:
        score += 5

    if hv is not None and abs(hv) <= Decimal("0.25"):
        score += 5

    if league_name in {"葡超", "德甲", "韩职", "瑞超", "日职", "意甲", "日乙"}:
        score += 5
    if league_name in {"西甲", "英冠", "英超", "英甲"}:
        score -= 5

    return max(0, min(120, score))


def empirical_handicap_draw_score(
    stats: Mapping | None,
    *,
    handicap_value=None,
    draw_odds=None,
    handicap_draw_odds=None,
) -> int:
    """Score handicap-draw candidates from historical feature analysis.

    Handicap draw behaves closer to a one-goal-margin model than to an ordinary
    draw model. It prefers deeper 1.0/1.25 handicaps and lower draw inertia.
    """
    ctx = _draw_context(stats)
    hv = _to_decimal(handicap_value)
    d = _to_decimal(draw_odds)
    hdo = _to_decimal(handicap_draw_odds)
    score = 0

    if hv is not None:
        abs_hv = abs(hv)
        if Decimal("1.00") <= abs_hv <= Decimal("1.25"):
            score += 35
        elif abs_hv == Decimal("0.50"):
            score += 15
        elif abs_hv <= Decimal("0.25"):
            score += 5
        elif abs_hv >= Decimal("1.75"):
            score -= 10

    venue_sum = ctx["venue_draw_sum"]
    if venue_sum is not None:
        if venue_sum < 0.45:
            score += 30
        elif venue_sum >= 0.65:
            score -= 25

    season_sum = ctx["season_draw_sum"]
    if season_sum is not None:
        if season_sum < 0.45:
            score += 20
        elif season_sum >= 0.65:
            score -= 20

    if d is not None and Decimal("3.00") <= d < Decimal("3.20"):
        score += 10

    if ctx["home_recent_win_rate"] is not None and ctx["home_recent_win_rate"] <= 0.5:
        score += 8
    if ctx["away_recent_loss_rate"] is not None and ctx["away_recent_loss_rate"] <= 0.5:
        score += 8

    rank_gap = ctx["rank_gap"]
    if rank_gap is not None and rank_gap >= 6:
        score += 6

    if hdo is not None and hdo >= Decimal("3.50"):
        score += 8

    return max(0, min(120, score))


def infer_competition_type(league_name: str | None, round_text: str | None) -> str:
    if round_text:
        if "首回合" in round_text:
            return "knockout_first_leg"
        if "次回合" in round_text:
            return "knockout_second_leg"
    if league_name and any(k in league_name for k in _CUP_KEYWORDS):
        return "cup"
    return "league"


def total_score(
    parts: Mapping[str, int], *, weights: Mapping[str, float] | None = None
) -> int:
    if weights is None:
        return int(sum(parts.get(k, 0) for k in DEFAULT_WEIGHTS))
    return int(
        round(sum(parts.get(k, 0) * float(weights.get(k, 0)) for k in DEFAULT_WEIGHTS))
    )
