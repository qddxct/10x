from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable

from app.research.metrics import max_losing_streak, summarize_returns
from app.research.types import ResearchCandidate

BucketFn = Callable[[ResearchCandidate], str]


def _range(value: float | None, ranges: list[tuple[float, float | None, str]]) -> str:
    if value is None:
        return "未知"
    for low, high, label in ranges:
        if high is None and value >= low:
            return label
        if high is not None and low <= value <= high:
            return label
    return "其他"


def _direction(value: float | None, positive_label: str, negative_label: str) -> str:
    if value is None:
        return "未知"
    if value > 0:
        return positive_label
    if value < 0:
        return negative_label
    return "均势"


FACTOR_DEFS: list[tuple[str, BucketFn]] = [
    ("league", lambda c: c.league),
    (
        "draw_odds_range",
        lambda c: _range(
            c.had_d,
            [(3.10, 3.29, "3.10-3.29"), (3.30, 3.49, "3.30-3.49"), (3.50, None, "3.50+")],
        ),
    ),
    (
        "handicap_draw_odds_range",
        lambda c: _range(
            c.hhad_d,
            [(3.10, 3.39, "3.10-3.39"), (3.40, 3.69, "3.40-3.69"), (3.70, None, "3.70+")],
        ),
    ),
    (
        "abs_hcap_range",
        lambda c: _range(
            c.abs_hcap,
            [(0.0, 0.0, "0"), (0.25, 0.25, "0.25"), (0.50, 0.50, "0.50"), (0.75, None, "0.75+")],
        ),
    ),
    (
        "rank_gap_range",
        lambda c: _range(c.rank_gap, [(0, 4, "0-4"), (5, 9, "5-9"), (10, None, "10+")]),
    ),
    (
        "recent_draw_sum",
        lambda c: _range(
            c.recent_draw_sum, [(0, 0.49, "低"), (0.50, 0.79, "中"), (0.80, None, "高")]
        ),
    ),
    (
        "recent_low_scoring_sum",
        lambda c: _range(
            c.recent_low_scoring_sum, [(0, 0.99, "低"), (1.00, 1.39, "中"), (1.40, None, "高")]
        ),
    ),
    (
        "h2h_draw_rate",
        lambda c: _range(
            c.h2h_draw_rate, [(0, 0.24, "低"), (0.25, 0.34, "中"), (0.35, None, "高")]
        ),
    ),
    (
        "h2h_one_goal_margin_rate",
        lambda c: _range(
            c.h2h_one_goal_margin_rate, [(0, 0.24, "低"), (0.25, 0.34, "中"), (0.35, None, "高")]
        ),
    ),
    ("home_recent_goal_diff", lambda c: _direction(c.home_recent_goal_diff, "主队强", "主队弱")),
    ("away_recent_goal_diff", lambda c: _direction(c.away_recent_goal_diff, "客队强", "客队弱")),
]


def build_factor_buckets(
    candidates: Iterable[ResearchCandidate], *, stake: float = 100.0
) -> list[dict]:
    rows = list(candidates)
    out: list[dict] = []
    for factor, bucket_fn in FACTOR_DEFS:
        grouped: dict[str, list[ResearchCandidate]] = defaultdict(list)
        for candidate in rows:
            grouped[bucket_fn(candidate)].append(candidate)
        for label, items in sorted(grouped.items()):
            pnls = [(item.odds - 1) * stake if item.is_hit else -stake for item in items]
            summary = summarize_returns(pnls, stake=stake)
            out.append(
                {
                    "factor": factor,
                    "label": label,
                    "bets": summary["bets"],
                    "hits": summary["hits"],
                    "hit_rate": summary["hit_rate"],
                    "avg_odds": sum(item.odds for item in items) / len(items),
                    "pnl": summary["pnl"],
                    "roi": summary["roi"],
                    "max_losing_streak": max_losing_streak([item.is_hit for item in items]),
                    "sample_note": "可参考" if len(items) >= 30 else "观察样本",
                }
            )
    return out
