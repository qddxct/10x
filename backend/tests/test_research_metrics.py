from app.research.metrics import max_losing_streak, percentile_rank, summarize_returns


def test_summarize_returns_calculates_roi_and_hit_rate():
    summary = summarize_returns([260.0, -100.0, -100.0], stake=100.0)
    assert summary["bets"] == 3
    assert summary["hits"] == 1
    assert summary["hit_rate"] == 1 / 3
    assert summary["pnl"] == 60.0
    assert summary["roi"] == 0.2


def test_max_losing_streak_counts_consecutive_misses():
    assert max_losing_streak([False, False, True, False, False, False]) == 3
    assert max_losing_streak([True, True]) == 0


def test_percentile_rank_uses_less_or_equal_position():
    assert percentile_rank(5.0, [1.0, 3.0, 5.0, 7.0]) == 0.75
