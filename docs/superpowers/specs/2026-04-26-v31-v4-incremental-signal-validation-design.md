# V3.1/V4 增量信号验证设计

日期: 2026-04-26
状态: Draft，等待人工审阅

## 1. 背景

当前模型状态:

| 模型 | 状态 | 说明 |
| --- | --- | --- |
| default | 保留 | 基线模型 |
| empirical-v2-d104-h104-clean | 当前 active | 继续作为默认观察模型 |
| empirical-v3-candidate | 候选观察 | HDRAW_A-only，只推荐高置信让球平 |

V3 的经验结论:

1. 让平主规则 HDRAW_A 在完整样本上表现最好。
2. HDRAW_C 和 DRAW_A 在首轮实现后为负，已经暂停。
3. 当前 V3 推荐量很少，47 注，ROI 高但样本小。
4. 当前 V3 没有使用交锋、近期比分、进攻/防守强度、联赛属性、赔率变化等维度。
5. 下一步不能直接加权堆维度，必须先验证新增维度是否有样本外增益。

本设计的核心原则:

```text
先分析，不盲改。
平 / 让平分通道。
新增维度必须证明能提升 ROI、降低回撤，且不过度缩小样本。
```

## 2. 目标

建立一套增量信号验证流程，用于判断哪些新维度值得进入 V3.1 或 V4。

目标包括:

1. 拆分 `Draw Channel` 和 `Handicap Draw Channel` 独立验证。
2. 对当前 HDRAW_A 的 47 注做亏损窗口诊断。
3. 对普通平重新建研究样本，不再沿用旧的普通平假设。
4. 验证新增维度是否能改善历史回测表现。
5. 输出可审计的分析报告，再决定是否写实现计划。

非目标:

1. 不直接修改当前 v2/v3 模型逻辑。
2. 不直接激活 v3。
3. 不做黑盒机器学习。
4. 不以单个联赛或单个时间窗口的偶然收益作为上线依据。
5. 不使用任何赛后泄漏数据。

## 3. 通道拆分

### 3.1 Draw Channel: 普通平

普通平要回答的问题:

```text
两队是否接近？
比赛是否不容易拉开？
平赔是否给了足够价格？
```

候选基础样本:

1. 所有有赛果、赔率、球队状态的完整历史比赛。
2. 以 `result = draw` 作为命中。
3. 结算赔率使用 `had_d`，缺失时才回退 Titan007 平赔。

普通平禁止直接借用让平规则。它需要单独验证:

1. 浅盘口。
2. 低比分倾向。
3. 强弱接近。
4. 欧赔均衡。
5. 联赛平局结构。

### 3.2 Handicap Draw Channel: 让平

让平要回答的问题:

```text
强弱是否存在？
强队是否可能只赢一球？
弱队是否有韧性但不够赢？
盘口和让平赔率是否给了足够回报？
```

候选基础样本:

1. 当前 HDRAW_A 的 47 注。
2. HDRAW_A 邻近样本，比如盘口 0.75~1.25、排名差 4~18、让平赔率 3.3~4.2。
3. 以 `handicap_result = draw` 作为命中。
4. 结算赔率使用 `hhad_d`，缺失时才回退 Titan007 让平赔率。

让平通道优先研究如何过滤亏损窗口，而不是盲目扩量。

## 4. 新增维度优先级

### 4.1 第一优先级: 进攻/防守强度

需要验证的字段:

```text
home_goals_for_per_match
home_goals_against_per_match
away_goals_for_per_match
away_goals_against_per_match
home_home_goals_for_per_match
home_home_goals_against_per_match
away_away_goals_for_per_match
away_away_goals_against_per_match
recent_goals_for_per_match
recent_goals_against_per_match
```

验证假设:

1. 强队火力过强时，让平容易被打穿，应过滤。
2. 弱队客场防守不崩时，让平更有价值。
3. 普通平更偏向双方进攻一般、失球不极端的结构。

验收口径:

1. 对 HDRAW_A，能降低亏损窗口或提升 ROI。
2. 对普通平，能找到比全样本普通平更高 ROI 的窄规则。
3. 样本不能低到无法观察，单规则原则上不少于 25 注；低于 25 注只能作为观察，不进入模型。

### 4.2 第二优先级: 一球胜负分布

需要验证的字段:

```text
home_win_by_1_count
home_win_by_2plus_count
home_home_win_by_1_count
home_home_win_by_2plus_count
away_loss_by_1_count
away_loss_by_2plus_count
away_away_loss_by_1_count
away_away_loss_by_2plus_count
```

验证假设:

1. 让平最直接的信号是强队小胜、弱队小负。
2. `win_by_1` 和 `loss_by_1` 比排名更贴近让平。
3. 如果强队大量 `win_by_2plus`，则让平风险升高。

验收口径:

1. 能解释 HDRAW_A 中哪些比赛更像一球胜。
2. 能过滤明显穿盘风险。
3. 不依赖赛后数据，必须是赛前历史分布。

### 4.3 第三优先级: 近期比分状态

需要验证的字段:

```text
home_recent_scores
away_recent_scores
home_recent_goal_diff
away_recent_goal_diff
home_recent_win_by_1_count
away_recent_loss_by_1_count
home_recent_big_win_count
away_recent_big_loss_count
```

验证假设:

1. 近况不能只看 W/D/L，要看比分和净胜球。
2. 强队近期连续大胜时，让平可能变差。
3. 弱队近期连续大败时，让平可能变差。
4. 强队近期小胜多、弱队近期小负多时，让平可能更好。

风险:

近期样本很小，容易噪声过大。该维度必须经过窗口验证，不能只看全样本。

### 4.4 第四优先级: 赔率/盘口变化

需要验证的字段:

```text
open_win_odds
close_win_odds
open_draw_odds
close_draw_odds
open_lose_odds
close_lose_odds
open_handicap_value
close_handicap_value
open_handicap_draw_odds
close_handicap_draw_odds
odds_move_direction
handicap_move_direction
```

验证假设:

1. 主胜降赔但盘口不继续加深，可能是强队热但穿盘不足。
2. 盘口升深但让平赔率仍高，可能有交易价值。
3. 让平赔率快速下行可能说明价值已经被吃掉。

数据要求:

1. 必须有历史初赔/临场赔快照。
2. 不能用赛后更新赔率。
3. 如果当前库只有单一赔率快照，本阶段只能写数据缺口，不能硬分析。

### 4.5 第五优先级: 联赛分组

需要验证的字段:

```text
league_name
country_or_region
competition_type
season_phase
```

验证假设:

1. 不同联赛的让平结构不同。
2. 高强弱分化联赛和低比分联赛不能共用完全相同阈值。
3. 杯赛、欧战前后、赛季末可能需要单独处理。

验收口径:

1. 先做联赛分组统计，不直接写死黑名单。
2. 单联赛样本太小则聚合为联赛组。
3. 只有长期稳定拖累 ROI 的组才考虑过滤。

### 4.6 第六优先级: 交锋记录

需要验证的字段:

```text
h2h_home_wins
h2h_draws
h2h_away_wins
h2h_goal_diff
h2h_close_game_count
```

验证假设:

1. 交锋可能反映风格克制。
2. 但交锋样本通常很小，时间跨度大，噪声高。
3. 交锋只能作为弱信号或过滤器，不能作为主规则。

验收口径:

1. 不接受只因 h2h 平局多就提高普通平。
2. 必须验证 h2h 是否在相同盘口结构下仍有效。

### 4.7 第七优先级: 赛程压力和阵容伤停

这些维度价值可能很高，但数据成本也高。

候选字段:

```text
home_days_since_last_match
away_days_since_last_match
home_days_to_next_match
away_days_to_next_match
home_travel_pressure
away_travel_pressure
home_key_absences
away_key_absences
```

本阶段处理方式:

1. 如果没有稳定历史数据，不进入统计。
2. 先记录数据缺口。
3. 后续单独设计抓取和标准化方案。

## 5. 分析方法

### 5.1 基础数据集

必须生成三个数据集:

1. `all_complete_matches`: 完整历史样本。
2. `draw_candidates`: 普通平研究样本。
3. `hdraw_candidates`: 让平研究样本，包含 HDRAW_A 和邻近结构。

每行至少包含:

```text
match_id
match_date
league
home_team
away_team
result
handicap_result
had_d
hhad_d
win_odds
draw_odds
lose_odds
handicap_value
handicap_draw_odds
rank_gap
season_draw_sum
venue_draw_sum
新增候选维度
```

### 5.2 单维度分析

对每个候选维度做:

1. 分桶统计。
2. bets / hits / hit_rate / ROI / avg_odds。
3. 按时间窗口拆分。
4. 按 bet_type 拆分。

禁止只看命中率。必须同时看 ROI。

### 5.3 组合规则分析

组合规则必须遵守:

1. 最多 3 个新增条件。
2. 每条规则必须有业务解释。
3. 每条规则必须和现有基线对比。
4. 不允许为了追求历史 ROI 组合过多小条件。

### 5.4 Walk-forward 验证

至少输出:

1. 全样本表现。
2. 90 天非重叠窗口表现。
3. 按自然季度表现。
4. 最近 180 天表现。

通过标准:

1. 全样本 ROI 高于对应基线。
2. 至少 70% 有效窗口 ROI 不低于基线。
3. 不靠单个窗口贡献超过总利润 50%。
4. 样本量不能低于预设下限。

## 6. 输出报告

需要生成:

```text
docs/analysis/2026-04-26-v31-v4-incremental-signal-validation.md
```

报告结构:

1. 数据完整性。
2. 当前基线。
3. Draw Channel 单独分析。
4. Handicap Draw Channel 单独分析。
5. 新增维度单变量表现。
6. 候选组合规则。
7. Walk-forward 结果。
8. 推荐进入模型的维度。
9. 不推荐进入模型的维度。
10. 数据缺口和下一步抓取建议。

## 7. 决策标准

新增维度进入模型前必须满足:

1. 来源稳定。
2. 无数据泄漏。
3. 有明确业务解释。
4. 在全样本和窗口中都优于基线。
5. 不把样本压缩到不可观察。
6. 不与现有维度重复表达同一件事。

如果只满足部分条件，只能进入观察清单，不能进入模型。

## 8. 数据缺口清单

当前需要确认数据库是否已有:

1. 历史比分明细，用于计算一球胜负分布。
2. 近 5/10 场比分，而不只是 W/D/L 字符串。
3. 进球/失球统计。
4. 初赔/临场赔变化轨迹。
5. 历史盘口变化轨迹。
6. 稳定的赛程压力字段。
7. 稳定的伤停字段。

如果没有，先做缺口报告，不临时拼凑不可靠数据。

## 9. 验收标准

本阶段完成条件:

1. 设计文档经人工确认。
2. 只新增分析脚本和分析报告，不修改推荐模型。
3. 报告明确指出哪些维度建议进入 V3.1/V4，哪些不建议。
4. 每个建议都有数据表和窗口验证支撑。
5. 如果没有足够证据，结论必须允许“不升级模型”。

## 10. 自检

- 已拆分普通平和让平两个通道。
- 没有要求直接改模型。
- 明确新增维度必须先验证。
- 明确普通平不能硬塞进让平模型。
- 明确数据泄漏边界。
- 明确样本量和窗口稳定性要求。
