# Empirical V3 Trading Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable `empirical-v3-candidate` model that prioritizes handicap-draw edges, keeps ordinary draws narrow, generates historical scores, and validates results through the existing backtest UI.

**Architecture:** Add pure v3 rule functions in the scoring engine, wire them through `ScoringService` with a new `strategy=empirical_v3`, and seed a new inactive model config. Keep existing `default` and `empirical-v2-d104-h104-clean` untouched. Validation is test-first, then database scoring/backtest report, then browser verification.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Pytest, MySQL in Docker, Next.js frontend, existing backtest/model-config APIs.

---

## Source Design

This plan implements: `docs/superpowers/specs/2026-04-24-empirical-v3-trading-model-design.md`.

Rules to preserve exactly unless the design document is revised first:

| Rule | bet_type | total_score | kelly_pct | Purpose |
| --- | --- | ---: | ---: | --- |
| HDRAW_A | `handicap_draw` | 112 | 0.015 | Primary handicap-draw rule |
| HDRAW_C | null | 0 | 0 | Research-only rule, disabled after first backtest |
| DRAW_A | null | 0 | 0 | Research-only rule, disabled after first backtest |

Revision note: first implementation showed HDRAW_A at +29.91% ROI, while
HDRAW_C and DRAW_A were negative. The candidate implementation must therefore
recommend only HDRAW_A.

## File Structure

Modify these files:

- `backend/app/engine/scoring.py`: add pure v3 context helpers and `empirical_v3_signal()`.
- `backend/app/engine/service.py`: route `strategy=empirical_v3` to the new v3 signal object.
- `backend/app/scripts/seed.py`: add idempotent creation for inactive `empirical-v3-candidate`.
- `backend/app/scripts/analyze_rules.py`: add optional report mode for fixed V3 rule-window validation if not already sufficient after implementation.
- `backend/tests/test_engine_scoring.py`: unit tests for HDRAW_A, HDRAW_C, DRAW_A, hard filters, and missing-data no-bet behavior.
- `backend/tests/test_engine_service.py`: integration tests that v3 chooses the right `bet_type`, score, recommendation flag, and Kelly band.
- `backend/tests/test_seed.py` or existing seed test file if present: idempotent v3 config creation test.
- `docs/analysis/2026-04-24-empirical-v3-backtest-report.md`: generated validation report after running DB scoring and backtests.

Do not modify:

- Historical match/result/odds/team-stat tables manually.
- Existing v2 thresholds or strategy logic.
- Frontend UI unless browser verification proves the existing model dropdown cannot display the new config.

## Task 1: Pure V3 Rule Tests

**Files:**
- Modify: `backend/tests/test_engine_scoring.py`
- Modify: `backend/app/engine/scoring.py`

- [ ] **Step 1: Add failing imports and reusable v3 stats fixtures**

In `backend/tests/test_engine_scoring.py`, extend the scoring import block with:

```python
    empirical_v3_signal,
```

Add these helpers near the empirical tests:

```python
def _v3_rank_gap_stats(*, home_rank=3, away_rank=13, season_draws=5, venue_draws=4):
    return {
        "home_rank": home_rank,
        "away_rank": away_rank,
        "home_season_wins": 10,
        "home_season_draws": season_draws,
        "home_season_losses": 5,
        "away_season_wins": 7,
        "away_season_draws": season_draws,
        "away_season_losses": 8,
        "home_home_wins": 6,
        "home_home_draws": venue_draws,
        "home_home_losses": 4,
        "away_away_wins": 4,
        "away_away_draws": venue_draws,
        "away_away_losses": 6,
        "home_recent_form": "WWDLWD",
        "away_recent_form": "LDWDLW",
    }
```

- [ ] **Step 2: Add failing test for HDRAW_A**

Append:

```python
def test_empirical_v3_signal_hdraw_a_primary_rule():
    signal = empirical_v3_signal(
        _v3_rank_gap_stats(home_rank=2, away_rank=12, season_draws=5, venue_draws=4),
        win_odds=Decimal("1.62"),
        draw_odds=Decimal("3.35"),
        lose_odds=Decimal("5.20"),
        handicap_value=Decimal("1.00"),
        handicap_draw_odds=Decimal("3.55"),
    )

    assert signal.rule == "HDRAW_A"
    assert signal.bet_type == "handicap_draw"
    assert signal.total_score == 112
    assert signal.kelly_pct == Decimal("0.015")
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py::test_empirical_v3_signal_hdraw_a_primary_rule -q
```

Expected: FAIL with import error for `empirical_v3_signal`.

- [ ] **Step 4: Implement v3 dataclass and function skeleton**

In `backend/app/engine/scoring.py`, add imports if missing:

```python
from dataclasses import dataclass
```

Add after `_draw_context()`:

```python
@dataclass(frozen=True)
class EmpiricalV3Signal:
    rule: str | None
    bet_type: str | None
    total_score: int
    kelly_pct: Decimal


def _decimal_between(value: Decimal | None, low: str, high: str) -> bool:
    return value is not None and Decimal(low) <= value <= Decimal(high)


def _odds_balance(win_odds, draw_odds, lose_odds) -> Decimal | None:
    values = [_to_decimal(win_odds), _to_decimal(draw_odds), _to_decimal(lose_odds)]
    if any(value is None for value in values):
        return None
    typed = [value for value in values if value is not None]
    return max(typed) - min(typed)


def empirical_v3_signal(
    stats: Mapping | None,
    *,
    win_odds=None,
    draw_odds=None,
    lose_odds=None,
    handicap_value=None,
    handicap_draw_odds=None,
) -> EmpiricalV3Signal:
    ctx = _draw_context(stats)
    hv = _to_decimal(handicap_value)
    hdo = _to_decimal(handicap_draw_odds)
    d = _to_decimal(draw_odds)
    w = _to_decimal(win_odds)
    l = _to_decimal(lose_odds)
    abs_hv = abs(hv) if hv is not None else None
    rank_gap = ctx["rank_gap"]
    season_sum = ctx["season_draw_sum"]
    venue_sum = ctx["venue_draw_sum"]
    balance = _odds_balance(win_odds, draw_odds, lose_odds)

    hdraw_blocked = (
        abs_hv is None
        or abs_hv >= Decimal("1.50")
        or (venue_sum is not None and venue_sum < 0.35)
        or (season_sum is not None and season_sum < 0.35)
    )
    draw_blocked = (
        d is None
        or d >= Decimal("3.80")
        or (balance is not None and balance >= Decimal("4.00"))
        or (abs_hv is not None and abs_hv >= Decimal("1.50"))
        or (venue_sum is not None and venue_sum >= 0.65)
    )

    if (
        not hdraw_blocked
        and _decimal_between(abs_hv, "1.00", "1.25")
        and rank_gap is not None
        and 6 <= rank_gap <= 15
        and hdo is not None
        and hdo >= Decimal("3.50")
    ):
        return EmpiricalV3Signal("HDRAW_A", "handicap_draw", 112, Decimal("0.015"))

    return EmpiricalV3Signal(None, None, 0, Decimal("0.000"))
```

- [ ] **Step 5: Run HDRAW_A test to verify it passes**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py::test_empirical_v3_signal_hdraw_a_primary_rule -q
```

Expected: PASS.

## Task 2: Complete V3 Rule Coverage

**Files:**
- Modify: `backend/tests/test_engine_scoring.py`
- Modify: `backend/app/engine/scoring.py`

- [ ] **Step 1: Add failing tests for HDRAW_C and DRAW_A**

Append:

```python
def test_empirical_v3_signal_hdraw_c_secondary_rule():
    signal = empirical_v3_signal(
        _v3_rank_gap_stats(home_rank=4, away_rank=14, season_draws=5, venue_draws=4),
        win_odds=Decimal("1.78"),
        draw_odds=Decimal("3.30"),
        lose_odds=Decimal("4.30"),
        handicap_value=Decimal("0.75"),
        handicap_draw_odds=Decimal("3.35"),
    )

    assert signal.rule == "HDRAW_C"
    assert signal.bet_type == "handicap_draw"
    assert signal.total_score == 106
    assert signal.kelly_pct == Decimal("0.010")


def test_empirical_v3_signal_draw_a_narrow_ordinary_draw_rule():
    signal = empirical_v3_signal(
        _v3_rank_gap_stats(home_rank=7, away_rank=10, season_draws=5, venue_draws=4),
        win_odds=Decimal("2.45"),
        draw_odds=Decimal("3.10"),
        lose_odds=Decimal("2.55"),
        handicap_value=Decimal("0.25"),
        handicap_draw_odds=Decimal("3.20"),
    )

    assert signal.rule == "DRAW_A"
    assert signal.bet_type == "draw"
    assert signal.total_score == 104
    assert signal.kelly_pct == Decimal("0.008")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py -k "empirical_v3_signal_hdraw_c or empirical_v3_signal_draw_a" -q
```

Expected: FAIL because only HDRAW_A is implemented.

- [ ] **Step 3: Implement HDRAW_C and DRAW_A branches**

In `empirical_v3_signal()`, insert after the HDRAW_A branch:

```python
    if (
        not hdraw_blocked
        and _decimal_between(abs_hv, "0.75", "1.25")
        and rank_gap is not None
        and 6 <= rank_gap <= 15
        and hdo is not None
        and hdo >= Decimal("3.30")
    ):
        return EmpiricalV3Signal("HDRAW_C", "handicap_draw", 106, Decimal("0.010"))

    if (
        not draw_blocked
        and w is not None
        and Decimal("2.30") <= w <= Decimal("2.80")
        and l is not None
        and Decimal("2.30") <= l <= Decimal("2.80")
        and d is not None
        and Decimal("3.00") <= d <= Decimal("3.20")
        and abs_hv is not None
        and abs_hv <= Decimal("0.25")
    ):
        return EmpiricalV3Signal("DRAW_A", "draw", 104, Decimal("0.008"))
```

- [ ] **Step 4: Run rule tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py -k "empirical_v3_signal" -q
```

Expected: PASS for all v3 signal tests added so far.

## Task 3: Hard Filter Tests

**Files:**
- Modify: `backend/tests/test_engine_scoring.py`
- Modify: `backend/app/engine/scoring.py`

- [ ] **Step 1: Add failing tests for hard filters and missing rank**

Append:

```python
def test_empirical_v3_signal_hdraw_rejects_deep_handicap():
    signal = empirical_v3_signal(
        _v3_rank_gap_stats(home_rank=2, away_rank=12, season_draws=5, venue_draws=4),
        win_odds=Decimal("1.35"),
        draw_odds=Decimal("4.10"),
        lose_odds=Decimal("7.20"),
        handicap_value=Decimal("1.50"),
        handicap_draw_odds=Decimal("3.80"),
    )

    assert signal.rule is None
    assert signal.bet_type is None
    assert signal.total_score == 0


def test_empirical_v3_signal_hdraw_rejects_low_draw_inertia():
    signal = empirical_v3_signal(
        _v3_rank_gap_stats(home_rank=2, away_rank=12, season_draws=1, venue_draws=1),
        win_odds=Decimal("1.62"),
        draw_odds=Decimal("3.35"),
        lose_odds=Decimal("5.20"),
        handicap_value=Decimal("1.00"),
        handicap_draw_odds=Decimal("3.55"),
    )

    assert signal.rule is None
    assert signal.bet_type is None
    assert signal.total_score == 0


def test_empirical_v3_signal_draw_rejects_high_draw_price_and_wide_market():
    signal = empirical_v3_signal(
        _v3_rank_gap_stats(home_rank=7, away_rank=10, season_draws=5, venue_draws=4),
        win_odds=Decimal("1.30"),
        draw_odds=Decimal("3.90"),
        lose_odds=Decimal("6.20"),
        handicap_value=Decimal("0.25"),
        handicap_draw_odds=Decimal("3.20"),
    )

    assert signal.rule is None
    assert signal.bet_type is None
    assert signal.total_score == 0


def test_empirical_v3_signal_requires_rank_gap_for_hdraw_rules():
    signal = empirical_v3_signal(
        _v3_rank_gap_stats(home_rank=None, away_rank=12, season_draws=5, venue_draws=4),
        win_odds=Decimal("1.62"),
        draw_odds=Decimal("3.35"),
        lose_odds=Decimal("5.20"),
        handicap_value=Decimal("1.00"),
        handicap_draw_odds=Decimal("3.55"),
    )

    assert signal.rule is None
    assert signal.bet_type is None
    assert signal.total_score == 0
```

- [ ] **Step 2: Run tests to verify current behavior**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py -k "empirical_v3_signal" -q
```

Expected: PASS if filters from Task 1 are correct; if any fail, fix only the branch condition causing the failure.

- [ ] **Step 3: Run entire scoring test file**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py -q
```

Expected: PASS. Existing non-v3 tests must remain unchanged.

## Task 4: Wire V3 Into ScoringService

**Files:**
- Modify: `backend/tests/test_engine_service.py`
- Modify: `backend/app/engine/service.py`
- Modify: `backend/app/engine/scoring.py` only if imports expose issues

- [ ] **Step 1: Add failing service test for v3 handicap-draw recommendation**

In `backend/tests/test_engine_service.py`, add fixture:

```python
@pytest.fixture
def empirical_v3_config(db: Session) -> ModelConfig:
    cfg = ModelConfig(
        name="empirical-v3-candidate",
        weights_json=dict(DEFAULT_WEIGHTS),
        thresholds_json={
            **DEFAULT_THRESHOLDS,
            "strategy": "empirical_v3",
            "recommend_total_score": 104,
            "draw_min_score": 104,
            "handicap_draw_min_score": 104,
        },
        kelly_bands_json={
            "draw_a": {"min_score": 104, "max_score": 105, "kelly_pct": 0.008},
            "hdraw_c": {"min_score": 106, "max_score": 111, "kelly_pct": 0.010},
            "hdraw_a": {"min_score": 112, "max_score": 120, "kelly_pct": 0.015},
        },
    )
    db.add(cfg)
    db.flush()
    return cfg
```

Add helper:

```python
def _add_v3_hdraw_team_stats(db: Session, match: SportteryMatch) -> SportteryMatchTeamStats:
    ts = SportteryMatchTeamStats(
        match_id=match.id,
        home_rank=2,
        away_rank=12,
        home_season_wins=10,
        home_season_draws=5,
        home_season_losses=5,
        away_season_wins=7,
        away_season_draws=5,
        away_season_losses=8,
        home_home_wins=6,
        home_home_draws=4,
        home_home_losses=4,
        away_away_wins=4,
        away_away_draws=4,
        away_away_losses=6,
        home_recent_form="WWDLWD",
        away_recent_form="LDWDLW",
        scraped_at=datetime.utcnow(),
    )
    db.add(ts)
    db.flush()
    return ts
```

Add test:

```python
def test_compute_for_match_empirical_v3_uses_rule_signal(
    db: Session, empirical_v3_config: ModelConfig, league: League
):
    match = _make_match(db, league)
    odds = _add_odds(db, match, source="titan007")
    odds.win_odds = Decimal("1.62")
    odds.draw_odds = Decimal("3.35")
    odds.lose_odds = Decimal("5.20")
    odds.handicap_value = Decimal("1.00")
    odds.draw_handicap_odds = Decimal("3.55")
    match.hhad_d = Decimal("3.55")
    _add_v3_hdraw_team_stats(db, match)
    db.commit()

    score = ScoringService(db).compute_for_match(match.id, empirical_v3_config.id)

    assert score is not None
    assert score.total_score == 112
    assert score.bet_type == "handicap_draw"
    assert score.kelly_pct == Decimal("0.0150")
    assert score.is_recommended is True
```

- [ ] **Step 2: Run service test to verify it fails**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_service.py::test_compute_for_match_empirical_v3_uses_rule_signal -q
```

Expected: FAIL because `strategy=empirical_v3` is not wired.

- [ ] **Step 3: Import v3 signal and wire strategy**

In `backend/app/engine/service.py`, add import:

```python
    empirical_v3_signal,
```

Change strategy branch from:

```python
        if strategy in {"empirical_v1", "empirical_v2"}:
```

to:

```python
        if strategy == "empirical_v3":
            stats_dict = _team_stats_to_dict(stats)
            signal = empirical_v3_signal(
                stats_dict,
                win_odds=chosen.win_odds,
                draw_odds=chosen.draw_odds,
                lose_odds=chosen.lose_odds,
                handicap_value=chosen.handicap_value,
                handicap_draw_odds=hcap_draw_odds,
            )
            total = signal.total_score
            bet_type = signal.bet_type
            kpct = float(signal.kelly_pct)
            is_recommended = total >= recommend and bet_type is not None

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

        if strategy in {"empirical_v1", "empirical_v2"}:
```

- [ ] **Step 4: Run service tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_service.py -q
```

Expected: PASS.

## Task 5: Seed Inactive V3 Model Config

**Files:**
- Modify: `backend/app/scripts/seed.py`
- Create or modify: `backend/tests/test_seed.py`

- [ ] **Step 1: Locate existing seed tests**

Run:

```bash
cd backend && rg -n "ensure_default_config|scripts.seed|DEFAULT_CONFIG_NAME" tests app -S
```

Expected: either an existing seed test file appears or no dedicated seed tests exist.

- [ ] **Step 2: Add failing test for idempotent v3 config**

If no seed test file exists, create `backend/tests/test_seed.py` with:

```python
from __future__ import annotations

from app.models import ModelConfig
from app.scripts.seed import ensure_empirical_v3_config
from sqlalchemy.orm import Session


def test_ensure_empirical_v3_config_creates_inactive_candidate(db: Session):
    cfg = ensure_empirical_v3_config(db)

    assert cfg.name == "empirical-v3-candidate"
    assert cfg.is_active is False
    assert cfg.thresholds_json["strategy"] == "empirical_v3"
    assert cfg.thresholds_json["recommend_total_score"] == 104
    assert cfg.kelly_bands_json["hdraw_a"]["kelly_pct"] == 0.015


def test_ensure_empirical_v3_config_is_idempotent(db: Session):
    first = ensure_empirical_v3_config(db)
    second = ensure_empirical_v3_config(db)

    assert first.id == second.id
    assert db.query(ModelConfig).filter(ModelConfig.name == "empirical-v3-candidate").count() == 1
```

- [ ] **Step 3: Run seed tests to verify they fail**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_seed.py -q
```

Expected: FAIL because `ensure_empirical_v3_config` does not exist.

- [ ] **Step 4: Implement seed constants and function**

In `backend/app/scripts/seed.py`, add after default constants:

```python
EMPIRICAL_V3_CONFIG_NAME = "empirical-v3-candidate"

EMPIRICAL_V3_THRESHOLDS: dict[str, Any] = {
    **DEFAULT_THRESHOLDS,
    "strategy": "empirical_v3",
    "recommend_total_score": 104,
    "draw_min_score": 104,
    "handicap_draw_min_score": 104,
}

EMPIRICAL_V3_KELLY_BANDS: dict[str, Any] = {
    "draw_a": {"min_score": 104, "max_score": 105, "kelly_pct": 0.008},
    "hdraw_c": {"min_score": 106, "max_score": 111, "kelly_pct": 0.010},
    "hdraw_a": {"min_score": 112, "max_score": 120, "kelly_pct": 0.015},
}
```

Add function after `ensure_default_config()`:

```python
def ensure_empirical_v3_config(db: Session) -> ModelConfig:
    existing = (
        db.query(ModelConfig)
        .filter(ModelConfig.name == EMPIRICAL_V3_CONFIG_NAME)
        .one_or_none()
    )
    if existing is not None:
        logger.info("empirical v3 ModelConfig exists id=%s, skip", existing.id)
        return existing

    cfg = ModelConfig(
        name=EMPIRICAL_V3_CONFIG_NAME,
        created_by=None,
        weights_json=DEFAULT_WEIGHTS,
        thresholds_json=EMPIRICAL_V3_THRESHOLDS,
        kelly_bands_json=EMPIRICAL_V3_KELLY_BANDS,
        scrape_schedule_json=DEFAULT_SCRAPE_SCHEDULE,
        is_active=False,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    logger.info("created empirical v3 ModelConfig id=%s active=%s", cfg.id, cfg.is_active)
    return cfg
```

In `main()`, call after `ensure_default_config(db)`:

```python
        ensure_empirical_v3_config(db)
```

- [ ] **Step 5: Run seed tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_seed.py -q
```

Expected: PASS.

## Task 6: Full Backend Verification

**Files:**
- No source changes unless tests expose defects.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py tests/test_engine_service.py tests/test_seed.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint for changed backend files**

Run:

```bash
cd backend && .venv/bin/python -m ruff check app/engine/scoring.py app/engine/service.py app/scripts/seed.py tests/test_engine_scoring.py tests/test_engine_service.py tests/test_seed.py
```

Expected: PASS.

- [ ] **Step 3: If lint reports formatting/import issues, apply only the reported fixes**

Run:

```bash
cd backend && .venv/bin/python -m ruff check app/engine/scoring.py app/engine/service.py app/scripts/seed.py tests/test_engine_scoring.py tests/test_engine_service.py tests/test_seed.py --fix
```

Expected: fixes only formatting/import-order problems.

- [ ] **Step 4: Re-run targeted tests after any fix**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py tests/test_engine_service.py tests/test_seed.py -q
```

Expected: PASS.

## Task 7: Create V3 Config In Database And Generate Scores

**Files:**
- Database writes only.
- No source changes unless commands reveal missing script capability.

- [ ] **Step 1: Run seed inside backend container**

Run:

```bash
docker compose exec backend python -m app.scripts.seed
```

Expected: logs include either `created empirical v3 ModelConfig` or `empirical v3 ModelConfig exists`.

- [ ] **Step 2: Confirm model configs**

Run:

```bash
docker compose exec mysql mysql -uroot -proot sporttery -e "select id,name,is_active,JSON_EXTRACT(thresholds_json,'$.strategy') strategy from model_configs order by id;"
```

Expected: rows include `default`, `empirical-v2-d104-h104-clean`, and `empirical-v3-candidate`; v3 is inactive.

- [ ] **Step 3: Generate historical v3 scores for complete history**

Use the existing score generation command if present. First locate it:

```bash
rg -n "compute_for_date|generate.*score|scores" backend/app/scripts backend/app -S
```

If no script exists, create a small script in `backend/app/scripts/score_history.py` with:

```python
from __future__ import annotations

import argparse
from datetime import date, datetime, time

from sqlalchemy import and_

from app.core.database import SessionLocal
from app.engine.service import ScoringService
from app.models import ModelConfig, SportteryMatch, SportteryMatchResult, SportteryMatchTeamStats


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    start_dt = datetime.combine(_parse_date(args.start), time.min)
    end_dt = datetime.combine(_parse_date(args.end), time.max)

    with SessionLocal() as db:
        cfg = db.query(ModelConfig).filter(ModelConfig.name == args.model).one()
        rows = (
            db.query(SportteryMatch)
            .join(SportteryMatchResult, SportteryMatchResult.match_id == SportteryMatch.id)
            .join(SportteryMatchTeamStats, SportteryMatchTeamStats.match_id == SportteryMatch.id)
            .filter(and_(SportteryMatch.match_date >= start_dt, SportteryMatch.match_date <= end_dt))
            .order_by(SportteryMatch.match_date.asc())
            .all()
        )
        svc = ScoringService(db)
        scored = 0
        recommended = 0
        for match in rows:
            score = svc.compute_for_match(match.id, cfg.id)
            if score is not None:
                scored += 1
                if score.is_recommended:
                    recommended += 1
        db.commit()
        print(f"model={cfg.name} matches={len(rows)} scored={scored} recommended={recommended}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run:

```bash
docker compose exec backend python -m app.scripts.score_history --model empirical-v3-candidate --start 2024-09-28 --end 2026-04-22
```

Expected: `scored` is close to complete sample count and `recommended` is substantially lower than total scored.

## Task 8: Backtest Report

**Files:**
- Create: `docs/analysis/2026-04-24-empirical-v3-backtest-report.md`
- Optional modify: `backend/app/scripts/analyze_rules.py` or create `backend/app/scripts/backtest_model_windows.py` if no existing script can produce the required comparison.

- [ ] **Step 1: Run full-history backtest from API or script**

Preferred: use existing backtest API/UI if available. If script support is missing, create `backend/app/scripts/backtest_model_windows.py` with parameters:

```bash
python -m app.scripts.backtest_model_windows --models default empirical-v2-d104-h104-clean empirical-v3-candidate --start 2024-09-28 --end 2026-04-22 --window-days 90
```

The script must print Markdown tables with:

```text
model | window_start | window_end | bets | hits | hit_rate | fixed_roi | kelly_roi | pnl
```

- [ ] **Step 2: Generate comparison report**

Create `docs/analysis/2026-04-24-empirical-v3-backtest-report.md` with this exact structure:

```markdown
# Empirical V3 Backtest Report

日期：2026-04-24
数据范围：2024-09-28 至 2026-04-22

## 1. 样本完整性

| 指标 | 数量 |
| --- | ---: |
| 完整比赛样本 | 使用 score_history 输出中的 matches 数值 |
| v3 已评分 | 使用 score_history 输出中的 scored 数值 |
| v3 推荐 | 使用 score_history 输出中的 recommended 数值 |

## 2. 全样本对比

| 模型 | 下注数 | 命中 | 命中率 | 固定 ROI | Kelly ROI | 盈亏 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| default | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 |
| empirical-v2-d104-h104-clean | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 |
| empirical-v3-candidate | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 |

## 3. 90 天窗口对比

| 窗口 | default ROI | v2 ROI | v3 ROI | v3 下注数 | v3 命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 每个 90 天窗口 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 |

## 4. V3 分 bet_type

| bet_type | 下注数 | 命中 | 命中率 | 固定 ROI | Kelly ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| draw | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 |
| handicap_draw | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 | 使用实际回测输出 |

## 5. 结论

- 是否通过“全样本 ROI 高于 default/v2”：是/否。
- 是否通过“至少 70% 有效 90 天窗口 ROI 不低于 v2”：是/否。
- 是否存在单窗口贡献超过总利润 50%：是/否。
- DRAW_A 是否建议保留：保留/关闭。
```

- [ ] **Step 3: Verify report has no placeholders**

Run:

```bash
rg -n "占位符|未填写|待补充" docs/analysis/2026-04-24-empirical-v3-backtest-report.md
```

Expected: no output.

## Task 9: Browser Verification

**Files:**
- No source changes unless UI cannot display existing API data.

- [ ] **Step 1: Open backtest page in the in-app browser**

Navigate to:

```text
http://localhost:3000/backtest
```

Expected: page loads.

- [ ] **Step 2: Confirm model dropdown contains v3**

Expected dropdown includes:

```text
empirical-v3-candidate
```

- [ ] **Step 3: Run a 90-day backtest for v3**

Use:

```text
开始日期：2026/01/23
结束日期：2026/04/22
模型配置：empirical-v3-candidate
资金模式：两者兼顾
每场固定投注金额：100
初始本金：10000
```

Expected: history list includes a new v3 backtest row with backtest time and model name.

- [ ] **Step 4: Open v3 detail and verify bet details**

Expected:

- `bet_type=让球平` or clear Chinese label.
- Handicap-draw rows display the handicap number.
- Score/ROI summary renders without console errors.

- [ ] **Step 5: If UI cannot show v3 without code changes, stop and update this plan**

Do not silently patch frontend. Add a new task to this plan first, then get user approval.

## Task 10: Final Verification And Handoff

**Files:**
- No source changes expected.

- [ ] **Step 1: Run final targeted backend verification**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_engine_scoring.py tests/test_engine_service.py tests/test_seed.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests only if UI code changed**

Run:

```bash
cd frontend && npm test -- --runInBand
```

Expected: PASS if frontend changed. Skip and record “not needed” if no frontend files changed.

- [ ] **Step 3: Summarize changed files**

Run:

```bash
git diff -- backend/app/engine/scoring.py backend/app/engine/service.py backend/app/scripts/seed.py backend/tests/test_engine_scoring.py backend/tests/test_engine_service.py backend/tests/test_seed.py docs/analysis/2026-04-24-empirical-v3-backtest-report.md
```

Expected: diff contains only v3-related changes.

- [ ] **Step 4: Do not commit unless user asks**

Because the current worktree already has many unrelated modified and untracked files, do not run `git add` or `git commit` unless the user explicitly requests it.

## Self-Review

Spec coverage:

- V3 candidate model only: covered by Task 5.
- HDRAW_A, HDRAW_C, DRAW_A: covered by Tasks 1 and 2.
- Hard filters: covered by Task 3.
- No leakage data: covered by using only existing scoring service inputs from historical Titan007-derived team stats and odds.
- Backtest validation: covered by Task 8.
- Browser verification: covered by Task 9.
- No overwrite of default/v2: covered by Task 5 and Task 10.

Placeholder scan:

- The report template states exactly which command output supplies each field. Task 8 Step 3 rejects generic placeholder wording before acceptance.
- No implementation step depends on unspecified code.

Type consistency:

- `empirical_v3_signal()` returns `EmpiricalV3Signal` with `rule`, `bet_type`, `total_score`, and `kelly_pct`.
- `ScoringService` persists `kelly_pct` as four-decimal `Decimal`, matching existing behavior.
- Strategy name is consistently `empirical_v3`; model name is consistently `empirical-v3-candidate`.
