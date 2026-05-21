# V3.2 过滤器候选模型设计

日期: 2026-04-26
状态: Draft，基于 V3.1 回测继续收敛

## 1. 背景

V3.1 已经把新增 Titan007 历史比分数据接入候选模型，并写入 `empirical-v31-combination-candidate` 历史 score。回测结果说明:

| 组合 | 下注数 | 命中率 | ROI |
| --- | ---: | ---: | ---: |
| V3.1 全部组合 | 1445 | 30.31% | -0.91% |
| V3.1 普通平组合 | 1386 | 30.16% | -1.88% |
| V3.1 让平组合 | 59 | 33.90% | +21.93% |

V3.1 的价值是证明方向有效，但问题也很明显:

1. 普通平覆盖太宽，下注数过大。
2. `DRAW_V31_C` 明显拖累，独立 ROI 为 `-5.91%`。
3. 前三个 90 天窗口亏损，说明规则还不够抗时间分布。
4. 让平样本少但仍是优势主线。

V3.2 的目标是做第一轮过滤器，不追求扩量，先追求全窗口稳定。

## 2. V3.2 目标

V3.2 只回答一个问题:

```text
把 V3.1 的宽规则收紧后，能否得到一个 90 天窗口更稳定、ROI 为正、并且仍有足够样本的研究模型？
```

初始离线测算选定方案:

```text
普通平: DRAW_V31_D + DRAW_V31_B，且 had_d >= 3.10
让平: HDRAW_V31_A0 + HDRAW_V31_A1 + HDRAW_V31_A2
```

离线估算表现:

| 指标 | 值 |
| --- | ---: |
| 下注数 | 561 |
| 命中率 | 32.44% |
| ROI | +11.27% |
| 90 天窗口正 ROI | 7/7 |

## 3. 模型配置

新增候选模型:

```text
name = empirical-v32-filtered-candidate
thresholds_json.strategy = empirical_v32_filtered
is_active = false
```

说明:

1. 这是研究模型，不接今日推荐。
2. 允许写入历史 `sporttery_match_scores`，用于历史回测页面查看。
3. 不覆盖 V3.1，保留 V3.1 作为对照。
4. 支持 `--replace` 重算该模型指定日期范围内的 score。

## 4. V3.2 规则

### DRAW_V32_CORE: 普通平核心过滤

普通平只保留两个 V3.1 正收益方向:

```text
命中 DRAW_V31_D 或 DRAW_V31_B
had_d >= 3.10
```

其中:

```text
DRAW_V31_D = h2h_draw_rate >= 0.35
             recent_draw_sum >= 0.50
             recent_low_scoring_sum >= 1.00
             abs_hcap <= 0.50
             3.00 <= had_d <= 3.60

DRAW_V31_B = h2h_one_goal_margin_rate >= 0.35
             recent_low_scoring_sum >= 1.00
             abs_hcap <= 0.75
             had_d is not null
```

新增价格下限 `had_d >= 3.10` 的原因:

1. V3.1 普通平命中率提升明显，但低平赔会吃掉收益。
2. 平赔过低时，30% 左右命中率仍然可能不够。
3. `had_d >= 3.10` 是第一轮保守价格过滤，不追求最优曲线拟合。

### HDRAW_V32_CORE: 让平核心保留

让平保留当前稳定主线:

```text
命中 HDRAW_V31_A0 或 HDRAW_V31_A1 或 HDRAW_V31_A2
```

暂不保留:

```text
HDRAW_V31_B
HDRAW_V31_C
```

原因:

1. `HDRAW_V31_B` 样本只有 6 注，虽然 ROI 很高，但只能观察，不能进入 V3.2 核心。
2. `HDRAW_V31_C` ROI 接近 0 且风险偏高。
3. 当前 V3.2 的重点是稳定，不是扩张。

## 5. 单场冲突处理

同一场同时命中普通平和让平时，仍然让平优先。

优先级:

```text
HDRAW_V32_CORE > DRAW_V32_CORE
```

score 分数:

| 规则 | total_score | kelly_pct | bet_type |
| --- | ---: | ---: | --- |
| HDRAW_V32_CORE | 116 | 0.015 | handicap_draw |
| DRAW_V32_CORE | 108 | 0.010 | draw |

说明:

1. 分数只是排序和展示，不是概率。
2. Kelly 只作页面展示和回测一致性，不代表真实资金建议。
3. `notes` 必须记录底层命中的 V3.1 规则、`had_d`、关键过滤条件。

## 6. 输出

脚本生成:

```text
docs/analysis/2026-04-26-v32-filtered-candidate-backtest.md
docs/analysis/v32-filtered-candidates.csv
```

同时写入:

```text
model_config: empirical-v32-filtered-candidate
sporttery_match_scores: 该模型对应历史 score
backtest_sessions: 全样本 + 90 天窗口
```

## 7. 验收标准

代码验收:

1. 单元测试通过。
2. ruff 通过。
3. 候选模型 `is_active=false`。
4. score 只写 `empirical-v32-filtered-candidate`。
5. 历史回测页面能看到该模型和回测记录。

效果验收:

1. 全样本 ROI 为正。
2. 90 天窗口至少 6/7 为正。
3. 下注数在 200 到 800 之间。
4. 普通平与让平拆分可见。
5. 明细 CSV 可用于抽查。

## 8. 风险

1. `had_d >= 3.10` 来自当前样本观察，仍可能过拟合。
2. 7/7 窗口为正是好信号，但窗口之间不是完全独立样本。
3. 让平仍然样本少，不能因 ROI 高就加大权重。
4. 未来要继续验证联赛、赔率变化、赛程压力、伤停。

## 9. 自检

- 文档为中文。
- 明确允许写候选模型历史 score。
- 明确不接今日推荐。
- 保留 V3.1 作为对照。
- V3.2 是过滤器版本，不是最终生产模型。
