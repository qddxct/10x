# Titan007 结构化近期比分补数设计

日期: 2026-04-26
状态: Draft，等待人工审阅

## 1. 背景

当前球队状态表 `sporttery_match_team_stats` 已经通过 Titan007 历史分析页抓取赛前状态，避免了竞彩网历史球队状态永远显示最新状态的数据泄漏问题。

Titan007 分析页里已有以下 JS 数组:

| 数组 | 含义 | 当前使用情况 |
| --- | --- | --- |
| `h_data` | 主队近期比赛，全场景 | 只统计胜/平/负和 W/D/L 字符串 |
| `a_data` | 客队近期比赛，全场景 | 只统计胜/平/负和 W/D/L 字符串 |
| `h2_data` | 主队近期主场比赛 | 只统计主场胜/平/负 |
| `a2_data` | 客队近期客场比赛 | 只统计客场胜/平/负 |
| `v_data` | 双方历史交锋 | 只统计交锋胜/平/负 |

但让平模型真正需要的是:

```text
强队是否常常只赢一球？
弱队是否常常只输一球？
强队近期是否火力过强容易打穿？
弱队近期是否防线崩盘容易被打穿？
```

这些问题不能只靠 W/D/L 回答，必须补结构化比分、进球、失球和一球胜负分布。

## 2. 目标

本阶段目标是把 Titan007 分析页中已经存在的近期比赛数组转成可分析字段，并回填历史数据。

目标:

1. 从 `h_data/a_data/h2_data/a2_data/v_data` 中解析比分。
2. 计算近期进球、失球、净胜球、一球胜负、大胜大负等聚合指标。
3. 字段写入 `sporttery_match_team_stats`，作为赛前快照的一部分。
4. 回填历史完整样本。
5. 重新跑只读增量信号验证，判断这些字段是否改善 V3/V4。

非目标:

1. 不修改当前 v2/v3 推荐逻辑。
2. 不激活任何新模型。
3. 不使用赛后刷新后的球队状态页面。
4. 不抓取伤停、赛程压力、赔率变化轨迹；这些另开设计。
5. 不把新字段直接用于模型，必须先分析。

## 3. 数据来源

继续使用当前历史抓取链路:

```text
https://zq.titan007.com/analysis/{titan007_match_id}cn.htm
```

必须满足:

1. 历史比赛回填只用对应比赛的 Titan007 analysis 页面。
2. 不回退到竞彩网球队状态接口。
3. 如果页面缺字段，记录为空，不用当前页面或人工补值。

## 4. 比分解析假设

当前代码已经确认 Titan007 数组中第 12 位是结果标记:

```text
row[12] = 1   胜
row[12] = 0   平
row[12] = -1  负
```

下一步需要通过样本页面和测试确认比分字段位置。根据 Titan007 历史比赛数组常见结构，候选字段可能包含:

```text
主队进球
客队进球
半场比分
比赛日期
联赛
主队名
客队名
```

实现原则:

1. 不猜字段写入数据库。
2. 先在解析器中增加受测试保护的 `_parse_score_from_row()`。
3. 用真实 HTML 样本或 fixture 固定字段位置。
4. 如果无法稳定解析比分，则只输出数据缺口报告，不写迁移。

## 5. 新增字段设计

字段放在 `sporttery_match_team_stats`，因为这些都是赛前球队状态快照的聚合结果。

### 5.1 主队近期全场景

```text
home_recent_matches_count
home_recent_goals_for
home_recent_goals_against
home_recent_goal_diff
home_recent_win_by_1
home_recent_win_by_2plus
home_recent_loss_by_1
home_recent_loss_by_2plus
home_recent_draw_score_count
home_recent_low_scoring_count
home_recent_high_scoring_count
```

说明:

- `recent` 默认取 `h_data` 前 6 场，与当前 `home_recent_form` 口径一致。
- `low_scoring` 定义为总进球 <= 2。
- `high_scoring` 定义为总进球 >= 4。

### 5.2 客队近期全场景

```text
away_recent_matches_count
away_recent_goals_for
away_recent_goals_against
away_recent_goal_diff
away_recent_win_by_1
away_recent_win_by_2plus
away_recent_loss_by_1
away_recent_loss_by_2plus
away_recent_draw_score_count
away_recent_low_scoring_count
away_recent_high_scoring_count
```

### 5.3 主队主场近期

```text
home_home_recent_matches_count
home_home_recent_goals_for
home_home_recent_goals_against
home_home_recent_goal_diff
home_home_recent_win_by_1
home_home_recent_win_by_2plus
home_home_recent_loss_by_1
home_home_recent_loss_by_2plus
```

### 5.4 客队客场近期

```text
away_away_recent_matches_count
away_away_recent_goals_for
away_away_recent_goals_against
away_away_recent_goal_diff
away_away_recent_win_by_1
away_away_recent_win_by_2plus
away_away_recent_loss_by_1
away_away_recent_loss_by_2plus
```

### 5.5 交锋比分结构

```text
h2h_matches_count
h2h_home_goals_for
h2h_home_goals_against
h2h_goal_diff
h2h_draw_score_count
h2h_one_goal_margin_count
h2h_low_scoring_count
h2h_high_scoring_count
```

说明:

- H2H 仍然只作为弱信号。
- 不允许因为 H2H 平局多就直接推荐普通平。
- 交锋字段主要用于解释和过滤，不作为主规则。

## 6. 派生指标

分析脚本可以基于存储字段再派生比率:

```text
home_recent_goals_for_per_match
home_recent_goals_against_per_match
away_recent_goals_for_per_match
away_recent_goals_against_per_match
home_recent_win_by_1_rate
away_recent_loss_by_1_rate
home_home_recent_win_by_1_rate
away_away_recent_loss_by_1_rate
h2h_one_goal_margin_rate
```

这些比率不一定入库，可以在分析脚本中计算。

## 7. 迁移策略

新增 Alembic migration:

```text
0010_add_titan007_recent_score_features.py
```

要求:

1. 所有新增字段 nullable。
2. 不改已有字段语义。
3. 不删除旧字段。
4. downgrade 删除新增字段。
5. MySQL 和测试 SQLite 都能通过。

## 8. 解析器改造

修改:

```text
backend/app/scrapers/titan007/analysis.py
```

新增内部结构:

```text
TitanScoreAgg
_parse_score_from_row(row)
_score_agg(rows, limit=6)
_h2h_score_agg(rows)
```

`TitanTeamStats` dataclass 增加新字段。

解析原则:

1. 单行无法解析比分时跳过该行。
2. 聚合计数只基于成功解析比分的行。
3. W/D/L 原有逻辑保持不变。
4. 不因为新增字段失败影响旧字段解析。

## 9. 回填策略

修改或新增脚本:

```text
backend/app/scripts/backfill.py
```

或新增专用脚本:

```text
backend/app/scripts/backfill_titan_recent_scores.py
```

建议新增专用脚本，降低对现有 backfill 的影响。

脚本能力:

1. 按日期范围扫描已有比赛。
2. 找到有 titan007_match_id 映射的比赛。
3. 重新抓取 analysis 页面。
4. 只更新 `sporttery_match_team_stats` 新增字段和原有可重算字段。
5. 输出总数、成功数、缺失数、失败原因。

如果当前库没有保存 `titan007_match_id`，需要先确认能否通过已有 JcResult 映射重新获得。不能靠球队名模糊匹配强行更新。

## 10. 数据质量验证

必须做三类验证:

### 10.1 单元测试

覆盖:

1. 比分字段解析。
2. 进球/失球聚合。
3. 一球胜负计数。
4. 无比分行跳过。
5. 原有 W/D/L 解析不回归。

### 10.2 抽样网页验证

随机抽取 20 场有新字段的历史比赛:

1. 打开 Titan007 analysis 页面。
2. 对比近期比分表。
3. 验证入库聚合值。
4. 输出 PASS/FAIL 明细。

### 10.3 分析验证

回填后重新运行:

```text
docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

或生成新版:

```text
docs/analysis/2026-04-26-v31-v4-recent-score-signal-validation.md
```

重点看:

1. HDRAW_A 中能否过滤亏损窗口。
2. 普通平是否出现正 ROI 组合规则。
3. 一球胜负分布是否比排名更有解释力。

## 11. 验收标准

本阶段完成条件:

1. 迁移成功。
2. 解析器测试通过。
3. 回填脚本完成历史数据更新。
4. 数据质量抽样通过率 >= 95%。
5. 生成新版分析报告。
6. 明确结论: 是否值得进入 V3.1/V4 模型设计。

## 12. 风险

1. Titan007 数组字段位置可能随页面版本变化。
2. 部分比赛 analysis 页面缺少近期比分。
3. H2H 时间跨度长，可能噪声很大。
4. 近 6 场样本较小，容易过拟合。
5. 如果没有 titan007_match_id 持久化，回填映射会更复杂。

## 13. 自检

- 文档为中文。
- 没有直接修改模型。
- 优先复用 Titan007 历史 analysis 页面。
- 明确先确认比分字段位置再入库。
- 明确迁移、回填、抽样验证和分析报告。
