from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from app.engine.service import ScoringService
from app.models import (
    League,
    ModelConfig,
    SportteryMatch,
    SportteryMatchOdds,
    SportteryMatchScore,
    SportteryMatchTeamStats,
)
from app.scripts.seed import DEFAULT_KELLY_BANDS, DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS
from sqlalchemy.orm import Session


@pytest.fixture
def config(db: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="default",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json=dict(DEFAULT_THRESHOLDS),
        kelly_bands_json=dict(DEFAULT_KELLY_BANDS),
    )
    db.add(cfg)
    db.flush()
    return cfg


@pytest.fixture
def league(db: Session) -> League:
    lg = League(name="英超")
    db.add(lg)
    db.flush()
    return lg


def _logical_id(dt: datetime, seq: int) -> int:
    weekday = (dt.weekday() + 1) % 7
    return int(dt.strftime("%Y%m%d") + str(weekday) + f"{seq:03d}")


def _make_match(
    db: Session, league: League, *, offset_hours: int = 24, seq: int = 1
) -> SportteryMatch:
    match_date = datetime.utcnow() + timedelta(hours=offset_hours)
    m = SportteryMatch(
        id=_logical_id(match_date, seq),
        league_id=league.id,
        home_team="H",
        away_team="A",
        match_date=match_date,
        status="scheduled",
    )
    db.add(m)
    db.flush()
    return m


def _add_odds(
    db: Session, match: SportteryMatch, *, source: str = "sporttery"
) -> SportteryMatchOdds:
    o = SportteryMatchOdds(
        match_id=match.id,
        source=source,
        win_odds=Decimal("2.50"),
        draw_odds=Decimal("3.10"),
        lose_odds=Decimal("2.60"),
        handicap_value=Decimal("0.0"),
        draw_handicap_odds=Decimal("3.60"),
        asian_handicap="平手",
        total_goals=Decimal("2.25"),
        scraped_at=datetime.utcnow(),
    )
    db.add(o)
    db.flush()
    return o


def _add_team_stats(db: Session, match: SportteryMatch) -> SportteryMatchTeamStats:
    ts = SportteryMatchTeamStats(
        match_id=match.id,
        home_rank=5,
        away_rank=6,
        home_season_wins=10,
        home_season_draws=8,
        home_season_losses=6,
        away_season_wins=9,
        away_season_draws=9,
        away_season_losses=7,
        home_recent_form="WDDLW",
        away_recent_form="DDWLL",
        scraped_at=datetime.utcnow(),
    )
    db.add(ts)
    db.flush()
    return ts


def test_compute_for_match_full_data(db: Session, config: ModelConfig, league: League):
    match = _make_match(db, league)
    _add_odds(db, match)
    _add_team_stats(db, match)
    db.commit()

    svc = ScoringService(db)
    score = svc.compute_for_match(match.id, config.id)

    assert score is not None
    assert score.match_id == match.id
    assert score.model_config_id == config.id
    assert score.user_id is None
    assert 0 < score.total_score <= 120
    assert score.euro_score > 0
    assert score.asian_score == 20
    assert score.goals_score == 20
    assert score.compression_score == 20
    assert score.team_stats_score > 0
    assert score.bet_type in {"draw", "handicap_draw", None}


def test_compute_for_match_is_idempotent(
    db: Session, config: ModelConfig, league: League
):
    match = _make_match(db, league)
    _add_odds(db, match)
    _add_team_stats(db, match)
    db.commit()

    svc = ScoringService(db)
    s1 = svc.compute_for_match(match.id, config.id)
    s2 = svc.compute_for_match(match.id, config.id)

    assert s1.id == s2.id
    assert db.query(SportteryMatchScore).count() == 1


def test_compute_for_match_without_odds_returns_none(
    db: Session, config: ModelConfig, league: League
):
    match = _make_match(db, league)
    db.commit()

    svc = ScoringService(db)
    score = svc.compute_for_match(match.id, config.id)
    assert score is None


def test_compute_for_match_prefers_sporttery_source(
    db: Session, config: ModelConfig, league: League
):
    match = _make_match(db, league)
    _add_odds(db, match, source="titan007")
    oddss = _add_odds(db, match, source="sporttery")
    oddss.draw_odds = Decimal("3.00")
    db.commit()

    svc = ScoringService(db)
    score = svc.compute_for_match(match.id, config.id)
    assert score.compression_score == 20


def test_is_recommended_flag_uses_thresholds(
    db: Session, config: ModelConfig, league: League
):
    match = _make_match(db, league)
    _add_odds(db, match)
    _add_team_stats(db, match)
    db.commit()

    svc = ScoringService(db)
    score = svc.compute_for_match(match.id, config.id)

    threshold = config.thresholds_json["recommend_total_score"]
    assert score.is_recommended == (score.total_score >= threshold)


def test_empirical_v32_hdraw_rule_scores_like_history(db: Session, league: League):
    cfg = ModelConfig(
        name="empirical-v32-filtered-candidate",
        weights_json={
            "euro": 1,
            "asian": 1,
            "goals": 1,
            "intent": 1,
            "compression": 1,
            "team_stats": 1,
        },
        thresholds_json={
            "strategy": "empirical_v32_filtered",
            "recommend_total_score": 100,
            "draw_min_score": 100,
            "handicap_draw_min_score": 100,
        },
        kelly_bands_json={
            "research_low": {"min_score": 100, "max_score": 107, "kelly_pct": 0.006},
            "research_mid": {"min_score": 108, "max_score": 113, "kelly_pct": 0.010},
            "research_high": {"min_score": 114, "max_score": 120, "kelly_pct": 0.015},
        },
    )
    db.add(cfg)
    match = _make_match(db, league)
    match.hhad_d = Decimal("3.60")
    odds = _add_odds(db, match)
    odds.handicap_value = Decimal("-1.00")
    odds.asian_handicap = "-1.00"
    ts = _add_team_stats(db, match)
    ts.home_rank = 2
    ts.away_rank = 12
    ts.home_season_wins = 8
    ts.home_season_draws = 7
    ts.home_season_losses = 5
    ts.away_season_wins = 7
    ts.away_season_draws = 7
    ts.away_season_losses = 6
    ts.home_home_wins = 3
    ts.home_home_draws = 4
    ts.home_home_losses = 3
    ts.away_away_wins = 3
    ts.away_away_draws = 4
    ts.away_away_losses = 3
    db.commit()

    score = ScoringService(db).compute_for_match(match.id, cfg.id)

    assert score is not None
    assert score.bet_type == "handicap_draw"
    assert score.total_score == 116
    assert score.team_stats_score > 0
    assert score.euro_score > 0
    assert score.kelly_pct == Decimal("0.0150")
    assert score.is_recommended is True


def test_empirical_v32_non_candidate_keeps_diagnostic_score_and_bet_direction(
    db: Session, league: League
):
    cfg = ModelConfig(
        name="empirical-v32-filtered-candidate",
        weights_json={
            "euro": 1,
            "asian": 1,
            "goals": 1,
            "intent": 1,
            "compression": 1,
            "team_stats": 1,
        },
        thresholds_json={
            "strategy": "empirical_v32_filtered",
            "recommend_total_score": 100,
            "draw_min_score": 100,
            "handicap_draw_min_score": 100,
        },
        kelly_bands_json={
            "research_low": {"min_score": 100, "max_score": 107, "kelly_pct": 0.006},
            "research_mid": {"min_score": 108, "max_score": 113, "kelly_pct": 0.010},
            "research_high": {"min_score": 114, "max_score": 120, "kelly_pct": 0.015},
        },
    )
    db.add(cfg)
    match = _make_match(db, league)
    _add_odds(db, match)
    _add_team_stats(db, match)
    db.commit()

    score = ScoringService(db).compute_for_match(match.id, cfg.id)

    assert score is not None
    assert 0 < score.total_score <= 120
    assert score.bet_type in {"draw", "handicap_draw"}
    assert score.kelly_pct == Decimal("0.0000")
    assert score.is_recommended is False


def test_empirical_v32_non_candidate_updates_stale_score(db: Session, league: League):
    cfg = ModelConfig(
        name="empirical-v32-filtered-candidate",
        weights_json={
            "euro": 1,
            "asian": 1,
            "goals": 1,
            "intent": 1,
            "compression": 1,
            "team_stats": 1,
        },
        thresholds_json={
            "strategy": "empirical_v32_filtered",
            "recommend_total_score": 100,
            "draw_min_score": 100,
            "handicap_draw_min_score": 100,
        },
        kelly_bands_json={
            "research_low": {"min_score": 100, "max_score": 107, "kelly_pct": 0.006},
            "research_mid": {"min_score": 108, "max_score": 113, "kelly_pct": 0.010},
            "research_high": {"min_score": 114, "max_score": 120, "kelly_pct": 0.015},
        },
    )
    db.add(cfg)
    match = _make_match(db, league)
    _add_odds(db, match)
    _add_team_stats(db, match)
    db.flush()
    db.add(
        SportteryMatchScore(
            match_id=match.id,
            model_config_id=cfg.id,
            euro_score=0,
            asian_score=0,
            goals_score=0,
            intent_score=0,
            compression_score=0,
            team_stats_score=108,
            total_score=108,
            bet_type="draw",
            kelly_pct=Decimal("0.0100"),
            is_recommended=True,
        )
    )
    db.commit()

    score = ScoringService(db).compute_for_match(match.id, cfg.id)

    assert score is not None
    assert db.query(SportteryMatchScore).count() == 1
    assert score.bet_type in {"draw", "handicap_draw"}
    assert score.is_recommended is False
    assert score.total_score != 108


def test_compute_for_date_filters_scheduled(db: Session, config: ModelConfig, league):
    m1 = _make_match(db, league, offset_hours=2, seq=1)
    m2 = _make_match(db, league, offset_hours=4, seq=2)
    _add_odds(db, m1)
    _add_odds(db, m2)
    _add_team_stats(db, m1)
    db.commit()

    svc = ScoringService(db)
    target_date = (datetime.utcnow() + timedelta(hours=2)).date()
    results = svc.compute_for_date(target_date, config.id)

    assert len(results) == 2
    assert all(r is not None for r in results)
