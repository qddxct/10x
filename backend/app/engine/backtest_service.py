"""BacktestService: read matches in a date range, run scoring + bet simulation,
persist aggregated results to `backtest_sessions`."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.engine.backtest import (
    BetOutcome,
    aggregate,
    decide_outcome,
    simulate_bet,
)
from app.engine.service import ScoringService, _pick_odds
from app.models import (
    BacktestSession,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchResult,
    SportteryMatchScore,
)

logger = logging.getLogger(__name__)


def _odds_for_bet(
    match: SportteryMatch,
    odds: SportteryMatchOdds,
    bet_type: str,
) -> Decimal | None:
    """Return settlement odds for a bet.

    The scoring model uses Titan007/Macau odds as probability inputs.  For
    money results we settle against Sporttery official odds stored on the match
    row, falling back to the model odds only for legacy fixtures without the
    newer HAD/HHAD columns populated.
    """
    if bet_type == "draw":
        return match.had_d or odds.draw_odds
    if bet_type == "handicap_draw":
        return match.hhad_d or odds.draw_handicap_odds
    return None


class BacktestService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def run(
        self,
        *,
        model_config_id: int,
        date_from: date,
        date_to: date,
        mode: str = "both",
        initial_capital: Decimal = Decimal("10000"),
        fixed_stake: Decimal = Decimal("100"),
        user_id: int | None = None,
    ) -> BacktestSession:
        start = datetime.combine(date_from, time.min)
        end = datetime.combine(date_to, time.max) + timedelta(microseconds=1)

        matches: list[SportteryMatch] = (
            self._db.query(SportteryMatch)
            .filter(SportteryMatch.match_date >= start, SportteryMatch.match_date < end)
            .order_by(SportteryMatch.match_date.asc())
            .all()
        )

        scoring = ScoringService(self._db)
        outcomes: list[BetOutcome] = []
        bets_detail: list[dict] = []
        capital = Decimal(initial_capital)

        for match in matches:
            result: SportteryMatchResult | None = (
                self._db.query(SportteryMatchResult)
                .filter(SportteryMatchResult.match_id == match.id)
                .one_or_none()
            )
            if result is None:
                continue

            score: SportteryMatchScore | None = (
                self._db.query(SportteryMatchScore)
                .filter(
                    SportteryMatchScore.match_id == match.id,
                    SportteryMatchScore.model_config_id == model_config_id,
                )
                .one_or_none()
            )
            if score is None:
                score = scoring.compute_for_match(
                    match.id, model_config_id, dry_run=True
                )
            if score is None or not score.is_recommended or score.bet_type is None:
                continue

            odds_list = (
                self._db.query(SportteryMatchOdds)
                .filter(SportteryMatchOdds.match_id == match.id)
                .all()
            )
            chosen = _pick_odds(odds_list)
            if chosen is None:
                continue

            bet_odds = _odds_for_bet(match, chosen, score.bet_type)
            if bet_odds is None:
                continue

            is_hit = decide_outcome(
                bet_type=score.bet_type,
                asian_handicap=chosen.asian_handicap,
                result=result.result,
                handicap_result=result.handicap_result,
            )
            kelly_pct_val = Decimal(score.kelly_pct or 0)
            pnl_fixed, pnl_kelly, stake_kelly = simulate_bet(
                odds=Decimal(bet_odds),
                kelly_pct=kelly_pct_val,
                current_capital=capital,
                is_hit=is_hit,
                stake_fixed=Decimal(fixed_stake),
            )
            capital = capital + pnl_kelly

            outcomes.append(
                BetOutcome(
                    score_id=score.id,
                    match_id=match.id,
                    match_date=match.match_date.date(),
                    league=match.league.name if match.league else "",
                    total_score=int(score.total_score),
                    bet_type=score.bet_type,
                    odds=Decimal(bet_odds),
                    kelly_pct=kelly_pct_val,
                    stake_fixed=Decimal(fixed_stake),
                    stake_kelly=stake_kelly,
                    pnl_fixed=pnl_fixed,
                    pnl_kelly=pnl_kelly,
                    is_hit=is_hit,
                )
            )
            bets_detail.append(
                {
                    "match_id": match.id,
                    "match_date": match.match_date.date().isoformat(),
                    "league": match.league.name if match.league else "",
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "bet_type": score.bet_type,
                    "handicap_value": (
                        str(chosen.handicap_value)
                        if chosen.handicap_value is not None
                        else None
                    ),
                    "total_score": int(score.total_score),
                    "odds": str(Decimal(bet_odds).quantize(Decimal("0.01"))),
                    "stake_fixed": str(Decimal(fixed_stake).quantize(Decimal("0.01"))),
                    "stake_kelly": str(stake_kelly),
                    "is_hit": is_hit,
                    "home_score": result.home_score,
                    "away_score": result.away_score,
                    "pnl_fixed": str(pnl_fixed),
                    "pnl_kelly": str(pnl_kelly),
                }
            )

        stats = aggregate(outcomes, initial_capital=Decimal(initial_capital))

        return self._persist(
            model_config_id=model_config_id,
            date_from=date_from,
            date_to=date_to,
            mode=mode,
            initial_capital=Decimal(initial_capital),
            fixed_stake=Decimal(fixed_stake),
            bets_detail=bets_detail,
            stats=stats,
            user_id=user_id,
        )

    def _persist(
        self,
        *,
        model_config_id: int,
        date_from: date,
        date_to: date,
        mode: str,
        initial_capital: Decimal,
        fixed_stake: Decimal,
        bets_detail: list[dict],
        stats,
        user_id: int | None = None,
    ) -> BacktestSession:
        session = BacktestSession(
            user_id=user_id,
            model_config_id=model_config_id,
            date_from=date_from,
            date_to=date_to,
            total_bets=stats.total_bets,
            hit_count=stats.hit_count,
            hit_rate=Decimal(stats.hit_rate).quantize(Decimal("0.0001")),
            roi=Decimal(stats.roi_fixed).quantize(Decimal("0.0001")),
            profit_loss=Decimal(stats.profit_loss_fixed).quantize(Decimal("0.01")),
            kelly_profit_loss=Decimal(stats.profit_loss_kelly).quantize(
                Decimal("0.01")
            ),
            kelly_roi=Decimal(stats.roi_kelly).quantize(Decimal("0.0001")),
            mode=mode,
            initial_capital=initial_capital,
            fixed_stake=fixed_stake,
            bets_detail=bets_detail or None,
            results_by_score=_decimalize(stats.by_score_band),
            results_by_league=_decimalize(stats.by_league),
            equity_curve=_decimalize(stats.equity_curve),
        )
        self._db.add(session)
        self._db.commit()
        self._db.refresh(session)
        return session


def _decimalize(obj):
    """Recursively convert Decimal values into JSON-friendly floats/strings."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimalize(v) for v in obj]
    return obj
