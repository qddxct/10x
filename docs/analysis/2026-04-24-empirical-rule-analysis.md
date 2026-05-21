# 2026-04-24 Empirical Rule Analysis

## Scope

Goal: improve ordinary draw and handicap-draw hit probability using historical
match results, Titan007/Macau odds, Sporttery settlement odds, and team snapshot
data.

Run:

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 PYTHONPATH=backend \
  backend/.venv/bin/python -m app.scripts.analyze_rules --top 8 --min-rule-bets 25
```

Dataset at analysis time:

| item | count |
| --- | ---: |
| rows with odds/results/team stats | 2376 |
| draw settlement bets | 2321 |
| handicap-draw settlement bets | 2376 |

## Baseline

| target | bets | hit_rate | ROI |
| --- | ---: | ---: | ---: |
| draw | 2321 | 26.24% | -7.71% |
| handicap_draw | 2376 | 23.74% | -13.78% |

## Strong Draw Signals

Ordinary draw is driven mainly by team draw tendency, especially exact venue
split:

| condition | bets | hit_rate | ROI |
| --- | ---: | ---: | ---: |
| home home-draw rate + away away-draw rate >= 0.65 | 444 | 49.10% | +72.27% |
| season draw-rate sum >= 0.65 | 210 | 45.24% | +59.25% |
| season draw-rate sum >= 0.65 and venue draw-rate sum >= 0.55 | 163 | 52.15% | +83.41% |
| above + Macau draw odds 2.8-3.2 | 37 | 64.86% | +96.16% |

Negative draw filters:

| condition | hit_rate | ROI |
| --- | ---: | ---: |
| venue draw-rate sum < 0.35 | 9.68% | -65.65% |
| season draw-rate sum < 0.35 | 7.50% | -70.83% |
| Macau draw odds >= 3.6 | 21.25% | -11.23% |

## Strong Handicap-Draw Signals

Handicap draw behaves more like a one-goal-margin model than an ordinary draw
model. It prefers a stronger-side handicap and lower draw inertia:

| condition | bets | hit_rate | ROI |
| --- | ---: | ---: | ---: |
| hcap 1.0/1.25 and venue draw-rate sum < 0.45 | 109 | 37.61% | +32.50% |
| hcap 1.25 and season draw-rate sum < 0.45 | 35 | 45.71% | +62.17% |
| hcap 0/0.25 + Macau draw odds 3.0-3.2 + home not hot | 130 | 32.31% | +22.25% |

Negative handicap-draw filters:

| condition | hit_rate | ROI |
| --- | ---: | ---: |
| venue draw-rate sum >= 0.65 | 15.30% | -44.26% |
| season draw-rate sum >= 0.65 | 18.06% | -34.33% |

## Implemented Candidate

Config name: `empirical-v1-d90-h85`

Status: created in DB, not active.

Strategy:

```json
{
  "strategy": "empirical_v1",
  "recommend_total_score": 85,
  "draw_min_score": 90,
  "handicap_draw_min_score": 85,
  "min_total_score": 85
}
```

Full historical backtest:

| metric | value |
| --- | ---: |
| backtest id | 20 |
| bets | 390 |
| hits | 171 |
| hit_rate | 43.85% |
| fixed ROI | +47.66% |
| fixed P/L | +18586.00 |
| draw bets | 179 / 97 hits |
| handicap_draw bets | 211 / 74 hits |

Time split:

| window | bets | hit_rate | ROI |
| --- | ---: | ---: | ---: |
| <= 2025-12-31 | 275 | 41.82% | +42.28% |
| >= 2026-01-01 | 115 | 48.70% | +60.50% |

## Caution

The team-stat signal is very strong. Before activating, verify that
`sporttery_match_team_stats` values are true pre-match snapshots and not
post-match refreshed standings. If they are post-match values, this model has
data leakage and must be rebuilt from pre-match-only data.
