# V3.4 二串一组单选择器回测报告

## 1. 摘要
| best_strategy | best_strategy_combo_count | best_strategy_pnl | best_strategy_return | best_strategy_roi | best_strategy_stake | candidates | constrained_model_roi_percentile | constrained_random_roi_avg | date_from | date_to | full_market_model_roi_percentile | full_market_random_roi_avg | model_config_id | model_name | model_roi_percentile_vs_random | random_label | random_roi_avg | strategy_rules |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| frequency_selector | 139 | 6911.62 | 20811.62 | 0.4972388489208633 | 13900.0 | 561 | 0.819 | 0.2375428086330939 | 2024-09-28 | 2026-04-22 | 0.994 | -0.2206860057553957 | 8 | empirical-v32-filtered-candidate | 0.819 | 候选池约束随机 | 0.2375428086330939 | {'strategy': 'frequency_selector', 'combo_odds_range': '10-14', 'excluded_leagues': ['德甲', '澳超'], 'ticket_window': '两天滚动组单', 'frequency': '每个滚动窗口最多一单, 已入选比赛不重复使用', 'mixed_bet_policy': '允许平/让平混合, 但不额外加分'} |

## 2. 策略表现
| strategy | combo_count | hit_count | hit_rate | roi | avg_combo_odds | coverage_rate | max_losing_streak |
| --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_selector | 149 | 14 | 0.09395973154362416 | 0.03761006711409396 | 11.573628187919464 | 0.26048951048951047 | 34 |
| conservative_selector | 116 | 8 | 0.06896551724137931 | -0.22920258620689654 | 11.382859482758617 | 0.20279720279720279 | 54 |
| frequency_selector | 139 | 18 | 0.12949640287769784 | 0.4972388489208633 | 11.933307913669063 | 0.243006993006993 | 16 |

## 3. 随机对照
| strategy | label | roi_avg | roi_p80 | roi_p90 | roi_p95 | model_roi_percentile | max_losing_streak_avg |
| --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_selector | 全市场随机 | -0.2110042966442952 | -0.0013187919463087247 | 0.15208053691275167 | 0.27976510067114096 | 0.828 | 43.78 |
| balanced_selector | 候选池约束随机 | 0.2450380583892616 | 0.4954208053691275 | 0.6087275167785235 | 0.7151006711409396 | 0.249 | 28.941 |
| conservative_selector | 全市场随机 | -0.19635332844827563 | 0.06073275862068966 | 0.2197155172413793 | 0.3189051724137931 | 0.472 | 39.42 |
| conservative_selector | 候选池约束随机 | 0.23130631896551707 | 0.5122905172413793 | 0.7004827586206896 | 0.8271594827586206 | 0.084 | 27.575 |
| frequency_selector | 全市场随机 | -0.2206860057553957 | -0.011615107913669064 | 0.13671223021582735 | 0.22659712230215825 | 0.994 | 43.264 |
| frequency_selector | 候选池约束随机 | 0.2375428086330939 | 0.47102158273381295 | 0.6050791366906475 | 0.7449510791366907 | 0.819 | 28.702 |

## 4. 结论提示
- 本报告只优化组单选择器, 不改变 V3.2 单场候选规则。
- 若策略没有超过约束随机 60% 分位, 不应进入生产推荐。
