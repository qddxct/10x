# 当前运行态模型说明

## 结论

当前运行态只保留两个模型配置：

- `default`: 基线模型，用作对照组和回归验证。
- `empirical-v32-filtered-candidate`: 当前候选模型，用于历史 score、90 天窗口回测和二串一组合研究。

以下模型已经退役，不再由 seed、score 或回测脚本自动创建或默认使用：

- `empirical-v2-d104-h104-clean`
- `empirical-v3-candidate`
- `empirical-v31-combination-candidate`

## 运行边界

`default` 仍然保留在系统里，是为了让老板能看到“模型 vs 基线”的差异。

`empirical-v32-filtered-candidate` 是当前唯一候选模型。它继承了 V3.1 阶段沉淀出的因子命名和过滤逻辑，但运行态模型名称统一为 V3.2，避免中间实验版本继续污染环境。

历史研究文档中出现 V2、V3、V3.1 属于归档信息，不代表当前运行态模型。

## 推荐重新生成顺序

1. 生成 default 历史 score：

```bash
python -m app.scripts.score_history --model default --start 2024-09-28 --end 2026-04-22
```

2. 生成 V3.2 候选历史 score：

```bash
python -m app.scripts.v31_combination_candidate_backtest --version v32 --start 2024-09-28 --end 2026-04-22
```

3. 生成 90 天窗口回测报告：

```bash
python -m app.scripts.backtest_model_windows \
  --start 2024-09-28 \
  --end 2026-04-22 \
  --window-days 90 \
  --report docs/analysis/current-model-window-backtest.md
```

4. 生成二串一组合研究报告：

```bash
python -m app.scripts.v34_combo_selector \
  --model empirical-v32-filtered-candidate \
  --start 2024-09-28 \
  --end 2026-04-22
```

## 维护要求

- 新模型进入运行态前，必须先写中文设计文档。
- 新模型必须有基线对照，至少包含 `default` 或随机对照。
- 中间实验模型不要写入 seed 默认配置；只有确认继续使用的模型才能进入运行态。

## 网页自助生成研究报告

入口：`/combo-reports`

用户选择开始日期和结束日期后，系统会：

1. 覆盖生成该区间 `empirical-v32-filtered-candidate` 的历史 score。
2. 生成 V3.4 二串一研究报告。
3. 写入 `model_research_runs` 和 `model_research_artifacts`。
4. 自动跳转到报告详情页。

随机试验次数默认 `1000`，随机种子默认 `20260426`。随机种子只影响随机对照组，不影响模型本身。
