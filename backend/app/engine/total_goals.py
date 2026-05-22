from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import exp

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import (
    League,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchTeamStats,
    TotalGoalRecommendation,
)

MODEL_VERSION = "tg-v1"
RECOMMEND_SCORE = 78


@dataclass(frozen=True)
class TotalGoalDecision:
    target_goals: int
    total_score: int
    confidence_pct: Decimal
    bet_odds: Decimal | None
    is_recommended: bool
    explanation: dict


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(count, total) -> float | None:
    if count is None or not total:
        return None
    return max(0.0, min(1.0, float(count) / float(total)))


def _avg_total(goals_for, goals_against, matches) -> float | None:
    if not matches:
        return None
    total = (goals_for or 0) + (goals_against or 0)
    return total / float(matches)


def _weighted_average(items: list[tuple[float | None, float]]) -> float | None:
    usable = [(value, weight) for value, weight in items if value is not None and weight > 0]
    if not usable:
        return None
    weight_sum = sum(weight for _value, weight in usable)
    return sum(value * weight for value, weight in usable) / weight_sum


def _ttg_odds(match: SportteryMatch, target: int) -> Decimal | None:
    return getattr(match, f"ttg_{target}", None)


def _target_label(targets: list[int]) -> str:
    return ",".join("7+" if t == 7 else str(t) for t in targets)


def _target_odds(match: SportteryMatch, targets: list[int]) -> dict[str, str]:
    odds: dict[str, str] = {}
    for target in targets:
        value = _ttg_odds(match, target)
        if value is not None:
            odds["7+" if target == 7 else str(target)] = str(value)
    return odds


def _representative_odds(match: SportteryMatch, targets: list[int]) -> Decimal | None:
    values = [_ttg_odds(match, target) for target in targets]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return min(present)


def _nearest_goal(value: float) -> int:
    return max(0, min(7, int(round(value))))


def _poisson_prob(lam: float, k: int) -> float:
    if k >= 7:
        return max(0.0, 1.0 - sum(_poisson_prob(lam, n) for n in range(7)))
    numerator = exp(-lam) * (lam**k)
    denom = 1
    for n in range(2, k + 1):
        denom *= n
    return numerator / denom


def _score_market_fit(target: int, market_line: float | None) -> int:
    if market_line is None:
        return 12
    distance = abs(target - market_line)
    if distance <= 0.35:
        return 25
    if distance <= 0.75:
        return 21
    if distance <= 1.15:
        return 14
    if distance <= 1.75:
        return 7
    return 0


def _score_distance(target: int, expected: float | None, max_score: int) -> int:
    if expected is None:
        return max_score // 2
    distance = abs(target - expected)
    if distance <= 0.35:
        return max_score
    if distance <= 0.75:
        return round(max_score * 0.82)
    if distance <= 1.15:
        return round(max_score * 0.55)
    if distance <= 1.75:
        return round(max_score * 0.25)
    return 0


def _score_odds_value(target: int, odds: Decimal | None, expected_goals: float) -> int:
    if odds is None:
        return 6
    odd = float(odds)
    if odd <= 1.0:
        return 0
    model_prob = _poisson_prob(max(0.4, expected_goals), target)
    implied_prob = 1.0 / odd
    edge = model_prob - implied_prob
    if edge >= 0.05:
        return 15
    if edge >= 0.02:
        return 12
    if edge >= -0.01:
        return 9
    if edge >= -0.04:
        return 5
    return 1


def _score_multi_odds_value(targets: list[int], match: SportteryMatch, expected_goals: float) -> int:
    values = [(_ttg_odds(match, target), target) for target in targets]
    present = [(odds, target) for odds, target in values if odds is not None]
    if len(present) != len(targets):
        return 6

    model_prob = sum(_poisson_prob(max(0.4, expected_goals), target) for _odds, target in present)
    # Multi-selecting total goals is a cover bet.  Stake is split across the
    # selected scores, so use the harmonic view of implied probability.
    implied_prob = sum(1.0 / float(odds) for odds, _target in present)
    edge = model_prob - implied_prob
    if edge >= 0.08:
        return 15
    if edge >= 0.04:
        return 12
    if edge >= 0.00:
        return 9
    if edge >= -0.05:
        return 5
    return 1


def _score_stability(target: int, expected_goals: float, low_rate: float | None, high_rate: float | None) -> int:
    score = 10
    if target <= 2 and low_rate is not None:
        score += 5 if low_rate >= 0.48 else 2 if low_rate >= 0.38 else -4
    if target >= 4 and high_rate is not None:
        score += 5 if high_rate >= 0.36 else 1 if high_rate >= 0.25 else -5
    if target in {2, 3}:
        score += 2
    if abs(target - expected_goals) > 1.25:
        score -= 6
    return max(0, min(15, score))


def decide_total_goals(
    *,
    match: SportteryMatch,
    odds: SportteryMatchOdds | None,
    stats: SportteryMatchTeamStats | None,
) -> TotalGoalDecision:
    market_line = _to_float(odds.total_goals if odds is not None else None)

    home_recent = away_recent = venue_home = venue_away = h2h = None
    low_rate = high_rate = None
    if stats is not None:
        home_recent = _avg_total(
            stats.home_recent_goals_for,
            stats.home_recent_goals_against,
            stats.home_recent_matches_count,
        )
        away_recent = _avg_total(
            stats.away_recent_goals_for,
            stats.away_recent_goals_against,
            stats.away_recent_matches_count,
        )
        venue_home = _avg_total(
            stats.home_home_recent_goals_for,
            stats.home_home_recent_goals_against,
            stats.home_home_recent_matches_count,
        )
        venue_away = _avg_total(
            stats.away_away_recent_goals_for,
            stats.away_away_recent_goals_against,
            stats.away_away_recent_matches_count,
        )
        h2h = _avg_total(stats.h2h_home_goals_for, stats.h2h_home_goals_against, stats.h2h_matches_count)
        home_low = _ratio(stats.home_recent_low_scoring_count, stats.home_recent_matches_count)
        away_low = _ratio(stats.away_recent_low_scoring_count, stats.away_recent_matches_count)
        h2h_low = _ratio(stats.h2h_low_scoring_count, stats.h2h_matches_count)
        home_high = _ratio(stats.home_recent_high_scoring_count, stats.home_recent_matches_count)
        away_high = _ratio(stats.away_recent_high_scoring_count, stats.away_recent_matches_count)
        h2h_high = _ratio(stats.h2h_high_scoring_count, stats.h2h_matches_count)
        low_rate = _weighted_average([(home_low, 0.4), (away_low, 0.4), (h2h_low, 0.2)])
        high_rate = _weighted_average([(home_high, 0.4), (away_high, 0.4), (h2h_high, 0.2)])

    recent_expected = _weighted_average([(home_recent, 0.5), (away_recent, 0.5)])
    venue_expected = _weighted_average([(venue_home, 0.5), (venue_away, 0.5)])
    expected_goals = _weighted_average(
        [
            (market_line, 0.45),
            (recent_expected, 0.25),
            (venue_expected, 0.15),
            (h2h, 0.15),
        ]
    )
    if expected_goals is None:
        expected_goals = 2.5

    target = _nearest_goal(expected_goals)
    if low_rate is not None and low_rate >= 0.58 and target > 2:
        target = 2
    elif high_rate is not None and high_rate >= 0.42 and target < 3:
        target = 3

    targets = [target]
    if target == 2 and (expected_goals <= 2.65 or (low_rate is not None and low_rate >= 0.48)):
        targets = [1, 2]
    elif target == 1:
        targets = [1, 2]
    elif target == 3 and low_rate is not None and low_rate >= 0.52:
        targets = [2, 3]

    odds_value = _representative_odds(match, targets)
    parts = {
        "market_fit": _score_market_fit(target, market_line),
        "recent_profile": _score_distance(target, recent_expected, 25),
        "venue_h2h": round(
            (_score_distance(target, venue_expected, 10) + _score_distance(target, h2h, 10))
        ),
        "odds_value": _score_multi_odds_value(targets, match, expected_goals)
        if len(targets) > 1
        else _score_odds_value(target, odds_value, expected_goals),
        "stability": _score_stability(target, expected_goals, low_rate, high_rate),
    }
    if targets == [1, 2]:
        parts["stability"] = min(15, parts["stability"] + 3)
    score = max(0, min(100, sum(parts.values())))
    confidence = Decimal(str(round(min(92.0, max(35.0, 45.0 + score * 0.45)), 2)))
    explanation = {
        "model": MODEL_VERSION,
        "target_label": _target_label(targets),
        "target_goals": targets,
        "target_odds": _target_odds(match, targets),
        "expected_goals": round(expected_goals, 2),
        "market_line": market_line,
        "recent_expected": round(recent_expected, 2) if recent_expected is not None else None,
        "venue_expected": round(venue_expected, 2) if venue_expected is not None else None,
        "h2h_expected": round(h2h, 2) if h2h is not None else None,
        "low_rate": round(low_rate, 3) if low_rate is not None else None,
        "high_rate": round(high_rate, 3) if high_rate is not None else None,
        "parts": parts,
    }
    return TotalGoalDecision(
        target_goals=target,
        total_score=score,
        confidence_pct=confidence,
        bet_odds=odds_value,
        is_recommended=score >= RECOMMEND_SCORE and odds_value is not None,
        explanation=explanation,
    )


class TotalGoalService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def compute_for_match(self, match_id: int) -> TotalGoalRecommendation | None:
        match = self._db.get(SportteryMatch, match_id)
        if match is None:
            return None
        odds = (
            self._db.query(SportteryMatchOdds)
            .filter(SportteryMatchOdds.match_id == match_id)
            .order_by(SportteryMatchOdds.source.asc(), SportteryMatchOdds.scraped_at.desc())
            .first()
        )
        stats = (
            self._db.query(SportteryMatchTeamStats)
            .filter(SportteryMatchTeamStats.match_id == match_id)
            .one_or_none()
        )
        decision = decide_total_goals(match=match, odds=odds, stats=stats)
        existing = (
            self._db.query(TotalGoalRecommendation)
            .filter(
                TotalGoalRecommendation.match_id == match_id,
                TotalGoalRecommendation.model_version == MODEL_VERSION,
            )
            .one_or_none()
        )
        if existing is None:
            existing = TotalGoalRecommendation(match_id=match_id, model_version=MODEL_VERSION)
            self._db.add(existing)

        existing.target_goals = decision.target_goals
        existing.total_score = decision.total_score
        existing.confidence_pct = decision.confidence_pct
        existing.bet_odds = decision.bet_odds
        existing.is_recommended = decision.is_recommended
        existing.explanation_json = decision.explanation
        self._db.commit()
        self._db.refresh(existing)
        return existing

    def compute_for_date(self, target_date: date) -> list[TotalGoalRecommendation]:
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)
        matches = (
            self._db.query(SportteryMatch)
            .filter(and_(SportteryMatch.match_date >= start, SportteryMatch.match_date < end))
            .all()
        )
        rows: list[TotalGoalRecommendation] = []
        for match in matches:
            row = self.compute_for_match(match.id)
            if row is not None:
                rows.append(row)
        return rows
