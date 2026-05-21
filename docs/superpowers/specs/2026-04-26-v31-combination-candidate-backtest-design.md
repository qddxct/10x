# V3.1 组合候选规则回测设计

日期: 2026-04-26
状态: Draft，等待人工审阅

## 1. 背景

基于 `docs/analysis/2026-04-26-v31-v4-recent-score-signal-validation.md`，我们已经确认历史数据质量和新增 Titan007 近期比分字段可用。

当前结论很清楚:

1. 单变量信号不足以上线。
2. 普通平通道出现了多个接近盈亏平衡或小幅改善的弱信号，适合组合验证。
3. 让平通道仍只有 `HDRAW_A 当前规则` 明显正收益，但样本只有 47 注，必须验证能否稳健扩容或过滤。
4. 本阶段允许写入研究模型 score，让历史回测页面可以直接查看效果；但不接今日推荐，不改变 active 模型。

本设计文档的目的，是定义 V3.1 组合候选规则的研究边界、候选规则、回测输出和通过标准。

## 2. 核心目标

V3.1 的目标不是马上生成新模型推荐，而是回答三个问题:

1. 普通平是否能通过多弱信号交集，把全样本 `-8.70% ROI` 改善到可研究区间。
2. 让平是否能在保留 `HDRAW_A` 优势的前提下，扩大样本或降低回撤。
3. 新增近期比分字段是否只是在单变量中好看，还是在组合条件下仍然有效。

成功的 V3.1 候选规则必须满足:

1. 样本量不低于 40 注；少于 40 注只允许标记为观察规则。
2. 全样本 ROI 明显优于同通道全样本基线。
3. 90 天窗口不能只靠单一窗口贡献收益。
4. 规则可解释，能用赛前数据复现。
5. 每条规则输出独立命中明细，并写入 score 备注，便于在回测页面和 CSV 中同时抽查。

## 3. 非目标和硬约束

本阶段明确不做:

1. 不新增或激活生产模型。
2. 不生成今日推荐。
3. 不把候选模型设为 active。
4. 不改 `app.engine.scoring` 的线上打分逻辑。
5. 不改回测页面默认行为。
6. 不做黑盒机器学习。
7. 不使用赔率变化、伤停、赛程压力，因为当前历史数据未覆盖这些维度。

允许做:

1. 新增候选模型配置 `empirical-v31-combination-candidate`，`is_active = false`。
2. 新增候选规则纯函数和测试。
3. 写入该候选模型对应的历史 `sporttery_match_scores`，用于回测页面查看。
4. 生成 Markdown 回测报告。
5. 生成 CSV/JSON 明细文件，供人工检查。
6. 清理并重算该候选模型的历史 score。

关键边界:

```text
可以写研究 score。
不能写生产推荐。
不能激活候选模型。
不能影响 default / empirical-v2-d104-h104-clean。
```

## 4. 数据口径

样本范围:

```text
2024-09-28 至 2026-04-22
```

入样条件:

1. 比赛已完赛。
2. 有赛果。
3. 有结算赔率。
4. 有 Titan007 `analysis/{id}cn.htm` 解析出的球队状态字段。
5. 有新增结构化近期比分字段。

结算口径:

| 通道 | 命中字段 | 结算赔率 |
| --- | --- | --- |
| 普通平 | `result == draw` | 优先 `had_d` |
| 让平 | `handicap_result == draw` | 优先 `hhad_d` |

说明:

1. 候选规则回测只评估单关固定 100 元投注。
2. Kelly 不作为本阶段主指标，因为当前没有独立概率校准。
3. 缺少结算赔率的比赛不参与该通道统计。

## 5. 派生特征

候选规则必须只使用以下赛前可复现特征。

### 5.1 已有基础特征

```text
abs_hcap
rank_gap
season_draw_sum
venue_draw_sum
home_recent_win_rate
home_recent_draw_rate
away_recent_loss_rate
away_recent_draw_rate
recent_draw_sum
h2h_draw_rate
```

### 5.2 新增近期比分特征

```text
home_recent_win_by_1_rate
away_recent_loss_by_1_rate
home_recent_gf_per_match
away_recent_ga_per_match
home_home_recent_win_by_1_rate
away_away_recent_loss_by_1_rate
h2h_one_goal_margin_rate
recent_low_scoring_sum
```

### 5.3 可选联赛特征

```text
league
competition_type
```

联赛特征只能作为报告分组或候选过滤器，不允许直接写死小样本联赛黑名单。单联赛少于 80 场时，只能放入“观察”分组。

## 6. 普通平候选组合规则

普通平的设计方向是“比赛接近 + 不容易打穿 + 价格不过分差”。它不是主战场，但报告显示多个弱信号组合后值得验证。

### DRAW_V31_A: H2H 平局 + 浅/中浅盘口

意图: 验证 `H2H 平局率 >= 0.35` 在盘口不过深时是否仍有效。

条件:

```text
h2h_draw_rate >= 0.35
abs_hcap <= 0.75
had_d is not null
had_d <= 3.80
```

依据:

1. `H2H 平局率 >= 0.35` 单变量 ROI 为 `-1.53%`，显著好于普通平全样本 `-8.70%`。
2. 深盘普通平长期不友好，必须限制盘口。

失败标准:

1. 样本少于 40 注。
2. 90 天窗口大多数低于普通平全样本窗口。
3. 命中率没有高于普通平全样本 `25.86%`。

### DRAW_V31_B: 一球差交锋 + 近期低比分

意图: 验证“历史对抗接近 + 近期总进球偏低”是否能提高普通平质量。

条件:

```text
h2h_one_goal_margin_rate >= 0.35
recent_low_scoring_sum >= 1.00
abs_hcap <= 0.75
had_d is not null
```

依据:

1. `H2H 一球差率 >= 0.35` 单变量 ROI 为 `-4.46%`。
2. `低比分倾向和 >= 1.00` 单变量 ROI 为 `-6.83%`。
3. 两者单独都不够，但方向符合普通平逻辑。

失败标准:

1. ROI 不优于任一单变量。
2. 只在一个窗口盈利。
3. 平均赔率过低导致风险回报不足。

### DRAW_V31_C: 近期平率 + 平赔甜区

意图: 验证近期 W/D/L 平率与价格甜区的交集，而不是单看近况。

条件:

```text
recent_draw_sum >= 0.50
3.00 <= had_d <= 3.40
abs_hcap <= 0.75
```

依据:

1. `近期平率和 >= 0.50` 单变量 ROI 为 `-4.77%`。
2. 平赔 `3.00-3.20` 命中率较高但 ROI 仍负，说明价格区间不能单独使用。

失败标准:

1. 全样本 ROI 仍低于 `-5%`。
2. 90 天窗口没有明显改善。

### DRAW_V31_D: 普通平强交集观察规则

意图: 用更窄条件观察普通平是否存在小样本高质量区域。

条件:

```text
h2h_draw_rate >= 0.35
recent_draw_sum >= 0.50
recent_low_scoring_sum >= 1.00
abs_hcap <= 0.50
3.00 <= had_d <= 3.60
```

说明:

该规则预计样本可能很少。若样本少于 40 注，只记录为观察，不允许进入后续模型。

## 7. 让平候选组合规则

让平的设计方向是“强队可赢但不易大胜，弱队可输但不易崩”。`HDRAW_A` 仍是核心种子。

### HDRAW_V31_A0: 当前 HDRAW_A 基线复刻

意图: 固化当前强规则作为对照组。

条件:

```text
1.00 <= abs_hcap <= 1.25
6 <= rank_gap <= 15
hhad_d >= 3.50
venue_draw_sum >= 0.35
season_draw_sum >= 0.35
```

输出:

1. 全样本指标。
2. 90 天窗口指标。
3. 命中明细。
4. 与既有报告 `47 注 / ROI 29.91%` 对齐检查。

### HDRAW_V31_A1: HDRAW_A + 一球形态过滤

意图: 验证新增一球胜负字段是否能过滤 HDRAW_A 中不适合让平的场次。

条件:

```text
命中 HDRAW_V31_A0
home_recent_win_by_1_rate >= 0.17
away_recent_loss_by_1_rate >= 0.17
```

依据:

1. 让平命中本质是让球后一球差。
2. 单变量“主近一球胜 + 客近一球负”样本 332，ROI `-5.14%`，不够上线，但适合做 HDRAW_A 的附加过滤。

失败标准:

1. ROI 低于 HDRAW_A0。
2. 样本少于 25 注且无法解释。
3. 过滤后只剩单一窗口盈利。

### HDRAW_V31_A2: HDRAW_A + 客队防守不崩

意图: 验证弱队防守稳定性是否能减少强队打穿风险。

条件:

```text
命中 HDRAW_V31_A0
away_recent_ga_per_match <= 1.60
away_recent_loss_by_2plus_rate <= 0.34
```

补充派生字段:

```text
away_recent_loss_by_2plus_rate = away_recent_loss_by_2plus / away_recent_matches_count
```

依据:

1. 让平怕强队赢两球以上。
2. 报告中 `away_recent_ga < 0.8` 的让平单变量 ROI 接近盈亏平衡，但不能单独使用。

失败标准:

1. ROI 不高于 HDRAW_A0。
2. 过滤主要来自极少数联赛。

### HDRAW_V31_B: 一球盘扩容规则

意图: 尝试在 `0.75 ~ 1.25` 盘口附近扩容，但必须用新增字段控制风险。

条件:

```text
0.75 <= abs_hcap <= 1.25
6 <= rank_gap <= 18
hhad_d >= 3.40
home_recent_win_by_1_rate >= 0.17
away_recent_loss_by_1_rate >= 0.17
away_recent_ga_per_match <= 1.80
season_draw_sum >= 0.35
venue_draw_sum >= 0.35
```

说明:

这是唯一允许扩容的让平规则。它不能直接进入推荐，只能在候选回测中和 HDRAW_A0/A1/A2 比较。

失败标准:

1. 全样本 ROI 低于 `0%`。
2. 90 天正 ROI 窗口少于 4/7。
3. 推荐数大幅增加但收益被稀释。

### HDRAW_V31_C: 深强弱差观察规则

意图: 验证报告中 `rank_gap >= 16` 的让平正收益是否可复现，不直接上线。

条件:

```text
rank_gap >= 16
1.00 <= abs_hcap <= 1.50
hhad_d >= 3.40
away_recent_ga_per_match <= 1.60
```

说明:

该规则风险很高，因为强弱差过大容易打穿。只能作为观察规则，用来判断是否存在“强队只小胜”的特殊结构。

## 8. 组合规则冲突处理

候选回测阶段允许同一场比赛命中多条候选规则，但报告必须提供两种视图:

1. `raw_rule_view`: 每条规则独立统计，允许重叠。
2. `portfolio_view`: 同一通道同一场只下注一次，按优先级去重。

普通平优先级:

```text
DRAW_V31_D > DRAW_V31_A > DRAW_V31_B > DRAW_V31_C
```

让平优先级:

```text
HDRAW_V31_A1 > HDRAW_V31_A2 > HDRAW_V31_A0 > HDRAW_V31_B > HDRAW_V31_C
```

跨通道冲突:

1. 若同一场同时命中普通平和让平，候选回测中分别统计。
2. `portfolio_view` 默认允许两通道分别成组合，因为这是研究视图。
3. 写入 `sporttery_match_scores` 时同一场只能有一个 `bet_type`，本阶段默认让平优先。
4. 如果后续要进入真实模型，必须再设计更严格的单场唯一投注选择逻辑。

## 9. Score 写入和回测页面集成

V3.1 候选规则需要进入现有历史回测页面，因此本阶段要写入独立候选模型 score。

模型配置:

```text
name = empirical-v31-combination-candidate
thresholds_json.strategy = empirical_v31_combination
is_active = false
```

score 写入规则:

1. 每场比赛、每个模型配置只保留一条 `sporttery_match_scores`。
2. 如果同一场同时命中普通平和让平，先按本阶段规则优先级选择一个推荐方向写入 score。
3. 默认优先让平，因为当前让平结构更强；若普通平规则命中而让平未命中，则写普通平。
4. 命中候选规则时 `is_recommended = true`。
5. 未命中候选规则时默认不生成 0 分占位行；实施时优先只写命中场，避免无意义行过多。

推荐方向优先级:

```text
HDRAW_V31_A1
HDRAW_V31_A2
HDRAW_V31_A0
HDRAW_V31_B
HDRAW_V31_C
DRAW_V31_D
DRAW_V31_A
DRAW_V31_B
DRAW_V31_C
```

score 分数语义:

| 规则层级 | total_score | kelly_pct | 说明 |
| --- | ---: | ---: | --- |
| HDRAW_V31_A1/A2 | 116 | 0.015 | HDRAW_A 强规则附加过滤 |
| HDRAW_V31_A0 | 112 | 0.012 | 当前 HDRAW_A 基线 |
| HDRAW_V31_B | 108 | 0.010 | 一球盘扩容研究 |
| HDRAW_V31_C | 104 | 0.008 | 深强弱差观察 |
| DRAW_V31_D | 106 | 0.008 | 普通平强交集观察 |
| DRAW_V31_A/B/C | 102 | 0.006 | 普通平组合研究 |

说明:

1. `total_score` 是规则优先级和展示排序，不是校准概率。
2. `kelly_pct` 是保守展示值，不代表真实 Kelly。
3. `notes` 必须写入命中规则、关键特征和“V3.1 candidate only”标记。
4. 生成脚本需要支持 `--replace`，先删除该模型在指定日期范围内的旧 score，再重算，避免重复迭代污染。

回测页面使用方式:

1. 先运行 V3.1 历史 score 生成脚本。
2. 在历史回测页面模型下拉框选择 `empirical-v31-combination-candidate`。
3. 按 90 天窗口运行回测。
4. 在下注明细中查看 `bet_type`、让球数、赔率、命中结果和备注。

## 10. 回测输出

脚本应生成一份 Markdown 报告:

```text
docs/analysis/2026-04-26-v31-combination-candidate-backtest.md
```

报告必须包含:

1. 数据范围与样本覆盖率。
2. 全样本基线: 普通平全样本、让平全样本、HDRAW_A0。
3. 每条候选规则独立表现。
4. 每条候选规则 90 天窗口表现。
5. 去重后的普通平组合表现。
6. 去重后的让平组合表现。
7. 规则重叠矩阵。
8. 命中明细文件路径。
9. 是否值得进入 V3.1 模型的结论。
10. score 写入摘要和候选模型配置 ID。

明细文件:

```text
docs/analysis/v31-combination-candidates.csv
```

明细字段:

```text
match_id,match_date,league,home_team,away_team,rule_name,channel,bet_type,odds,hit,pnl,hcap,rank_gap,had_d,hhad_d,home_recent_win_by_1_rate,away_recent_loss_by_1_rate,away_recent_ga_per_match,h2h_draw_rate,h2h_one_goal_margin_rate,recent_low_scoring_sum
```

score 写入摘要字段:

```text
model_config_id
scored_matches
recommended_scores
draw_scores
handicap_draw_scores
replaced_old_scores
```

## 11. 通过标准

### 11.1 普通平进入下一阶段的标准

至少一条普通平组合规则满足:

1. 样本量 `>= 80`。
2. 全样本 ROI `>= 0%`，或 ROI 比普通平全样本至少提升 8 个百分点。
3. 命中率高于普通平全样本 `25.86%`。
4. 90 天窗口中至少 4 个窗口优于普通平全样本窗口。
5. 不依赖单一联赛贡献超过 35% 利润。

### 11.2 让平进入下一阶段的标准

至少一条让平组合规则满足:

1. 样本量 `>= 40`。
2. ROI 不低于 HDRAW_A0 的 70%，且样本量明显更高；或 ROI 高于 HDRAW_A0。
3. 90 天正 ROI 窗口不少于 5/7。
4. 最大回撤窗口小于让平全样本窗口。
5. 不靠单一窗口贡献超过 50% 利润。

### 11.3 失败后的处理

如果所有组合规则失败:

1. 保留 V3.1 候选模型配置和回测记录作为研究痕迹。
2. 保留报告作为研究记录。
3. 可以清理该候选模型 score 后重做下一版。
4. 下一阶段优先补赔率变化、赛程压力、伤停，而不是继续堆当前字段。

## 12. 测试要求

必须覆盖:

1. 派生字段计算，包括除零和缺失值。
2. 每条候选规则的命中和不命中样例。
3. 重叠规则去重逻辑。
4. 90 天窗口切分。
5. CSV 明细字段完整性。
6. 候选模型配置创建逻辑，必须 `is_active = false`。
7. score 写入只影响 `empirical-v31-combination-candidate`。
8. `--replace` 只删除指定模型、指定日期范围内的 score。
9. 今日推荐入口不使用该模型。

## 13. 验收标准

文档验收:

1. 本文档经人工确认后，才允许写代码。
2. 实施计划必须保持“候选模型历史回测-only”。
3. 所有输出文档使用中文。

代码验收:

1. 单元测试通过。
2. ruff 通过。
3. 候选回测报告生成。
4. 明细 CSV 生成。
5. 数据库新增或复用 `empirical-v31-combination-candidate`，但 `is_active = false`。
6. 历史 score 写入成功，回测页面可以选择该模型。
7. 不新增今日推荐，不改变 active 模型。

## 14. 自检

- 无占位项。
- 明确禁止接今日推荐。
- 明确允许写候选模型历史 score。
- 明确禁止改变 active 模型。
- 明确区分普通平和让平。
- 明确候选规则、失败标准和通过标准。
- 明确输出报告和明细文件。
