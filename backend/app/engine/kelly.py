"""Kelly fraction lookup + bet type suggestion.

`kelly_bands_json` shape (per ModelConfig):
{
  "low":  {"min_score": 78, "max_score": 84, "kelly_pct": 0.01},
  "mid":  {"min_score": 84, "max_score": 96, "kelly_pct": 0.015},
  "high": {"min_score": 96, "max_score": 120, "kelly_pct": 0.02},
}

Thresholds (from spec section 5):
- draw recommend: total_score >= 84 (70%)
- handicap_draw recommend: total_score >= 78 (65%)
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def kelly_pct(score: int, bands: Mapping[str, Mapping]) -> float:
    """Return the half-Kelly fraction for a given total score.

    Bands are scanned in ascending min_score order; the last matching band wins.
    Returns 0.0 when score is below any band or bands are empty.
    """
    if not bands:
        return 0.0
    best_pct = 0.0
    best_min = -1
    for band in bands.values():
        min_s = band.get("min_score")
        max_s = band.get("max_score")
        pct = band.get("kelly_pct")
        if min_s is None or pct is None:
            continue
        if score >= min_s and (max_s is None or score <= max_s) and min_s > best_min:
            best_min = min_s
            best_pct = float(pct)
    return best_pct


def _is_level_or_quarter(value: str, *, max_abs: float = 0.25) -> bool:
    """Check if handicap is shallow enough for a draw bet.

    The historical data uses numeric strings (``0.00`` / ``0.25``), while older
    fixtures use Chinese labels.  ``max_abs`` lets a tuned ModelConfig tighten
    the draw market from "平手/平半" to "平手 only" without changing old configs.
    """
    if value == "平手":
        return max_abs >= 0.0
    if value == "平半":
        return max_abs >= 0.25
    if value in {"0", "0.0", "0.00"}:
        return max_abs >= 0.0
    v = _to_float(value)
    return v is not None and abs(v) <= max_abs


def suggest_bet_type(
    *,
    asian_handicap: str | None,
    draw_odds=None,
    handicap_draw_odds=None,
    total_score: int,
    min_draw_score: int = 84,
    min_handicap_score: int = 78,
    max_draw_handicap_abs: float = 0.25,
) -> str | None:
    """Return "draw" | "handicap_draw" | None.

    Logic (per plan T3):
    - 平手 / 平半 + score >= min_draw_score → draw
    - 让球 (半球及以上) + 让平赔率 >= 3.5 + score >= min_handicap_score → handicap_draw
    - otherwise → None
    """
    hcap = (asian_handicap or "").strip()
    if not hcap:
        return None

    if (
        _is_level_or_quarter(hcap, max_abs=max_draw_handicap_abs)
        and total_score >= min_draw_score
        and draw_odds is not None
    ):
        return "draw"

    if (
        not _is_level_or_quarter(hcap, max_abs=max_draw_handicap_abs)
        and total_score >= min_handicap_score
    ):
        hdo = _to_float(handicap_draw_odds)
        if hdo is not None and hdo >= 3.5:
            return "handicap_draw"

    return None
