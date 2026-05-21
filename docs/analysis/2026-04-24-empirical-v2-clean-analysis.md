# Empirical V2 Clean-Data Analysis

Date: 2026-04-24

Historical `team_stats` leakage was removed by replacing Sporttery historical
team status snapshots with Titan007 `analysis/{match_id}cn.htm` data. The old
`empirical_v1` result is no longer valid.

## Data Quality

- Matches: 2400
- Titan-refreshed `team_stats`: 2387
- Backtest-ready sample (`result + titan007 odds + clean team_stats`): 2376
- Old leaked `team_stats` rows remaining: 0

Random 10-row live re-parse check against Titan007 `cn.htm`: 10/10 matched all
stored team-status fields.

## Clean-Data Direction Changes

The previous high-draw-rate ordinary-draw signal reversed after leakage removal:

- Ordinary draw baseline: 2321 bets, 26.24% hit, -7.71% ROI
- Handicap draw baseline: 2376 bets, 23.74% hit, -13.78% ROI
- Ordinary draw `venue_draw_sum >= 0.65`: -34.21% ROI
- Ordinary draw `season_draw_sum >= 0.65 && venue_draw_sum >= 0.55`: -41.53% ROI

V2 therefore does not reward high historical draw rates for ordinary draws.

## V2 Rules

Config: `empirical-v2-d104-h104-clean`

Thresholds:

```json
{
  "strategy": "empirical_v2",
  "recommend_total_score": 104,
  "draw_min_score": 104,
  "handicap_draw_min_score": 104,
  "min_total_score": 104
}
```

Ordinary draw:

- Rank gap <= 2 plus balanced/low draw odds market signals.
- Positive league filter for historically useful draw leagues.
- Penalize very high season/venue draw-rate sums.

Handicap draw:

- Primary: handicap 1.25 plus low season/venue draw inertia.
- Secondary: handicap 0/0.25 plus Macau draw odds 3.0-3.2 and home side not hot.

## Backtest

Fixed stake: 100

| window | backtest id | bets | hits | hit rate | fixed ROI | fixed P/L | Kelly ROI | Kelly P/L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all 2025-03-28..2026-04-22 | 22 | 299 | 111 | 37.12% | 29.23% | 8739.00 | 219.76% | 21975.69 |
| train <= 2025-12-31 | 23 | 221 | 81 | 36.65% | 27.38% | 6052.00 | 122.71% | 12271.42 |
| test >= 2026-01-01 | 24 | 78 | 30 | 38.46% | 34.45% | 2687.00 | 43.57% | 4357.24 |

All-window bet mix:

- Draw: 82 bets, 36 hits
- Handicap draw: 217 bets, 75 hits

## Notes

The backtest is promising but still rule-mined from the same historical corpus.
Before activating this as the production model, review upcoming-day picks for
reasonableness and continue monitoring post-activation live results separately.
