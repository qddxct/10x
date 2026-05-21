"""ScoringService: read DB, compute, upsert `match_scores`."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.engine.empirical_v32 import empirical_v32_decision
from app.engine.kelly import kelly_pct, suggest_bet_type
from app.engine.scoring import (
    DEFAULT_WEIGHTS,
    asian_score,
    compression_score,
    empirical_draw_score,
    empirical_handicap_draw_score,
    euro_score,
    goals_score,
    infer_competition_type,
    intent_score,
    team_stats_score,
    total_score,
)
from app.models import (
    ModelConfig,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchScore,
    SportteryMatchTeamStats,
)

logger = logging.getLogger(__name__)

_SOURCE_PRIORITY = ("titan007", "sporttery", "other")


def _pick_odds(odds: list[SportteryMatchOdds]) -> SportteryMatchOdds | None:
    if not odds:
        return None
    by_source = {o.source: o for o in odds}
    for src in _SOURCE_PRIORITY:
        if src in by_source:
            return by_source[src]
    return odds[0]


def _team_stats_to_dict(stats: SportteryMatchTeamStats | None) -> dict | None:
    if stats is None:
        return None
    return {
        "home_rank": stats.home_rank,
        "away_rank": stats.away_rank,
        "home_season_wins": stats.home_season_wins,
        "home_season_draws": stats.home_season_draws,
        "home_season_losses": stats.home_season_losses,
        "away_season_wins": stats.away_season_wins,
        "away_season_draws": stats.away_season_draws,
        "away_season_losses": stats.away_season_losses,
        "home_home_wins": stats.home_home_wins,
        "home_home_draws": stats.home_home_draws,
        "home_home_losses": stats.home_home_losses,
        "away_away_wins": stats.away_away_wins,
        "away_away_draws": stats.away_away_draws,
        "away_away_losses": stats.away_away_losses,
        "home_recent_form": stats.home_recent_form,
        "away_recent_form": stats.away_recent_form,
        "h2h_home_wins": stats.h2h_home_wins,
        "h2h_draws": stats.h2h_draws,
        "h2h_away_wins": stats.h2h_away_wins,
    }


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_bet_type(
    *,
    asian_handicap: str | None,
    handicap_value,
    draw_odds,
    handicap_draw_odds,
    max_draw_handicap_abs: float,
) -> str | None:
    """Pick the market direction to show even when a row is not recommended."""
    suggested = suggest_bet_type(
        asian_handicap=asian_handicap,
        draw_odds=draw_odds,
        handicap_draw_odds=handicap_draw_odds,
        total_score=120,
        min_draw_score=0,
        min_handicap_score=0,
        max_draw_handicap_abs=max_draw_handicap_abs,
    )
    if suggested is not None:
        return suggested

    numeric_hcap = _to_float(handicap_value)
    if numeric_hcap is None:
        numeric_hcap = _to_float(asian_handicap)
    if numeric_hcap is not None:
        return "draw" if abs(numeric_hcap) <= max_draw_handicap_abs else "handicap_draw"

    if asian_handicap in {"平手", "平半"}:
        return "draw"
    if asian_handicap:
        return "handicap_draw"
    if draw_odds is not None:
        return "draw"
    if handicap_draw_odds is not None:
        return "handicap_draw"
    return None


class ScoringService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def compute_for_match(
        self,
        match_id: int,
        model_config_id: int,
        *,
        dry_run: bool = False,
    ) -> SportteryMatchScore | None:
        match = self._db.get(SportteryMatch, match_id)
        if match is None:
            return None
        cfg = self._db.get(ModelConfig, model_config_id)
        if cfg is None:
            return None

        odds_list = (
            self._db.query(SportteryMatchOdds)
            .filter(SportteryMatchOdds.match_id == match_id)
            .all()
        )
        chosen = _pick_odds(odds_list)
        if chosen is None:
            logger.info("compute_for_match skipped match_id=%s: no odds", match_id)
            return None

        stats = (
            self._db.query(SportteryMatchTeamStats)
            .filter(SportteryMatchTeamStats.match_id == match_id)
            .one_or_none()
        )

        league_name = match.league.name if match.league is not None else None
        ctype = match.competition_type or infer_competition_type(
            league_name, match.round
        )

        parts = {
            "euro": euro_score(
                win=chosen.win_odds, draw=chosen.draw_odds, lose=chosen.lose_odds
            ),
            "asian": asian_score(
                handicap_value=chosen.handicap_value,
                asian_handicap=chosen.asian_handicap,
            ),
            "goals": goals_score(
                chosen.total_goals,
                draw_odds=chosen.draw_odds,
                handicap_value=chosen.handicap_value,
            ),
            "intent": intent_score(ctype, match.round),
            "compression": compression_score(chosen.draw_odds),
            "team_stats": team_stats_score(_team_stats_to_dict(stats)),
        }

        weights = cfg.weights_json or DEFAULT_WEIGHTS
        normalized = {
            k: float(weights.get(k, DEFAULT_WEIGHTS[k])) / DEFAULT_WEIGHTS[k]
            for k in DEFAULT_WEIGHTS
        }
        total = total_score(parts, weights=normalized)

        thresholds = cfg.thresholds_json or {}
        recommend = int(thresholds.get("recommend_total_score", 84))
        draw_min = int(thresholds.get("draw_min_score", recommend))
        hcap_min = int(thresholds.get("handicap_draw_min_score", recommend - 6))
        draw_hcap_abs_max = float(thresholds.get("draw_handicap_abs_max", 0.25))
        hcap_draw_odds = chosen.draw_handicap_odds or match.hhad_d

        strategy = thresholds.get("strategy")
        if strategy == "empirical_v32_filtered":
            diagnostic_total = total_score(parts)
            decision = empirical_v32_decision(match=match, odds=chosen, stats=stats)
            if decision is None:
                total = diagnostic_total
                bet_type = _display_bet_type(
                    asian_handicap=chosen.asian_handicap,
                    handicap_value=chosen.handicap_value,
                    draw_odds=chosen.draw_odds,
                    handicap_draw_odds=hcap_draw_odds,
                    max_draw_handicap_abs=draw_hcap_abs_max,
                )
                kpct = 0.0
                is_recommended = False
            else:
                total = decision.total_score
                bet_type = decision.bet_type
                kpct = float(decision.kelly_pct)
                is_recommended = True
        elif strategy == "empirical_v1":
            stats_dict = _team_stats_to_dict(stats)
            draw_signal = empirical_draw_score(
                stats_dict,
                draw_odds=chosen.draw_odds,
                handicap_value=chosen.handicap_value,
                league_name=league_name,
            )
            handicap_signal = empirical_handicap_draw_score(
                stats_dict,
                handicap_value=chosen.handicap_value,
                draw_odds=chosen.draw_odds,
                handicap_draw_odds=hcap_draw_odds,
            )
            total = max(draw_signal, handicap_signal)
            recommended_bet_type = None
            if draw_signal >= draw_min and draw_signal >= handicap_signal:
                recommended_bet_type = "draw"
                total = draw_signal
            elif handicap_signal >= hcap_min:
                recommended_bet_type = "handicap_draw"
                total = handicap_signal
            elif draw_signal >= draw_min:
                recommended_bet_type = "draw"
                total = draw_signal
            bet_type = recommended_bet_type or _display_bet_type(
                asian_handicap=chosen.asian_handicap,
                handicap_value=chosen.handicap_value,
                draw_odds=chosen.draw_odds,
                handicap_draw_odds=hcap_draw_odds,
                max_draw_handicap_abs=draw_hcap_abs_max,
            )
            kpct = kelly_pct(total, cfg.kelly_bands_json or {})
            is_recommended = total >= recommend and recommended_bet_type is not None
        else:
            recommended_bet_type = suggest_bet_type(
                asian_handicap=chosen.asian_handicap,
                draw_odds=chosen.draw_odds,
                handicap_draw_odds=hcap_draw_odds,
                total_score=total,
                min_draw_score=draw_min,
                min_handicap_score=hcap_min,
                max_draw_handicap_abs=draw_hcap_abs_max,
            )
            bet_type = recommended_bet_type or _display_bet_type(
                asian_handicap=chosen.asian_handicap,
                handicap_value=chosen.handicap_value,
                draw_odds=chosen.draw_odds,
                handicap_draw_odds=hcap_draw_odds,
                max_draw_handicap_abs=draw_hcap_abs_max,
            )
            kpct = kelly_pct(total, cfg.kelly_bands_json or {})
            is_recommended = total >= recommend and recommended_bet_type is not None

        if dry_run:
            return SportteryMatchScore(
                match_id=match_id,
                model_config_id=model_config_id,
                user_id=None,
                euro_score=parts["euro"],
                asian_score=parts["asian"],
                goals_score=parts["goals"],
                intent_score=parts["intent"],
                compression_score=parts["compression"],
                team_stats_score=parts["team_stats"],
                total_score=total,
                bet_type=bet_type,
                kelly_pct=Decimal(str(round(kpct, 4))) if kpct else Decimal("0.0000"),
                is_recommended=is_recommended,
            )

        return self._upsert(
            match_id=match_id,
            model_config_id=model_config_id,
            parts=parts,
            total=total,
            bet_type=bet_type,
            kelly=kpct,
            is_recommended=is_recommended,
        )

    def compute_for_date(
        self, target_date: date, model_config_id: int
    ) -> list[SportteryMatchScore]:
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)
        matches = (
            self._db.query(SportteryMatch)
            .filter(and_(SportteryMatch.match_date >= start, SportteryMatch.match_date < end))
            .all()
        )
        results: list[SportteryMatchScore] = []
        for m in matches:
            score = self.compute_for_match(m.id, model_config_id)
            if score is not None:
                results.append(score)
        return results

    def _upsert(
        self,
        *,
        match_id: int,
        model_config_id: int,
        parts: dict,
        total: int,
        bet_type: str | None,
        kelly: float,
        is_recommended: bool,
    ) -> SportteryMatchScore:
        existing = (
            self._db.query(SportteryMatchScore)
            .filter(
                SportteryMatchScore.match_id == match_id,
                SportteryMatchScore.model_config_id == model_config_id,
            )
            .one_or_none()
        )
        kelly_dec = Decimal(str(round(kelly, 4))) if kelly else Decimal("0.0000")

        if existing is None:
            existing = SportteryMatchScore(
                match_id=match_id,
                model_config_id=model_config_id,
                user_id=None,
            )
            self._db.add(existing)

        existing.euro_score = parts["euro"]
        existing.asian_score = parts["asian"]
        existing.goals_score = parts["goals"]
        existing.intent_score = parts["intent"]
        existing.compression_score = parts["compression"]
        existing.team_stats_score = parts["team_stats"]
        existing.total_score = total
        existing.bet_type = bet_type
        existing.kelly_pct = kelly_dec
        existing.is_recommended = is_recommended

        self._db.commit()
        self._db.refresh(existing)
        return existing
