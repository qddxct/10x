from __future__ import annotations


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def summarize_returns(pnls: list[float], *, stake: float) -> dict[str, float | int]:
    bets = len(pnls)
    hits = sum(1 for pnl in pnls if pnl > 0)
    total_pnl = round(sum(pnls), 4)
    return {
        "bets": bets,
        "hits": hits,
        "hit_rate": safe_div(hits, bets),
        "pnl": total_pnl,
        "roi": safe_div(total_pnl, bets * stake),
    }


def max_losing_streak(results: list[bool]) -> int:
    current = 0
    longest = 0
    for hit in results:
        if hit:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def percentile_rank(value: float | None, samples: list[float]) -> float:
    if value is None or not samples:
        return 0.0
    return sum(1 for sample in samples if sample <= value) / len(samples)


def quantile(samples: list[float], q: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]
