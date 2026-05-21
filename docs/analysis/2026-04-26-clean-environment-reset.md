# 2026-04-26 干净环境清理记录

## 目标

为重新跑模型 score、回测、二串一研究报告和今日推荐准备干净环境。

## 保留数据

以下数据属于基础历史数据或用户数据，不删除：

- `users`: 用户数据。
- `leagues`: 联赛字典。
- `sporttery_matches`: 历史比赛和赛程。
- `sporttery_match_odds`: 历史赔率。
- `sporttery_match_results`: 历史赛果。
- `sporttery_match_team_stats`: 历史球队状态。
- `model_configs`: 仅保留 `default` 和 `empirical-v32-filtered-candidate`。

## 删除数据

以下数据属于模型打磨过程产物，清理后重新生成：

- `sporttery_match_scores`: 历史 score。
- `backtest_sessions`: 历史回测记录。
- `model_research_runs`: 研究报告运行记录。
- `model_research_artifacts`: 研究报告结构化产物。
- `scrape_logs`: 抓取日志。
- `data_audit_runs`: 数据审计运行记录。
- `data_audit_match_snapshots`: 数据审计快照。
- `data_audit_diffs`: 数据审计差异。

## 删除模型配置

删除以下中间模型：

- `empirical-v2-d104-h104-clean`
- `empirical-v3-candidate`
- `empirical-v31-combination-candidate`

保留：

- `default`
- `empirical-v32-filtered-candidate`

## 清理后模型状态

- `empirical-v32-filtered-candidate`: 设为 active。
- `default`: 保留但不激活。

## 后续重新生成顺序

1. 使用 `empirical-v32-filtered-candidate` 跑历史 score。
2. 以 90 天窗口跑历史回测。
3. 跑 V3.4 二串一组单研究报告。
4. 再接今日推荐。

## 代码逻辑同步

数据库清理之后，代码也同步收口：

- `seed.py` 不再创建 `empirical-v3-candidate`，只保证 `default` 与 `empirical-v32-filtered-candidate` 存在。
- `ScoringService` 删除 `strategy=empirical_v3` 分支，中间实验策略不再作为推荐运行策略。
- 90 天窗口回测脚本默认只比较 `default` 与 `empirical-v32-filtered-candidate`。
- V3.2 候选 score 仍由 `v31_combination_candidate_backtest.py --version v32` 生成；文件名保留历史原因，但不再创建 V3.1 运行态模型。
- 前端测试数据已改为当前候选模型，避免页面测试继续引用退役模型。

当前模型运行说明见：`docs/analysis/CURRENT_MODEL_RUNTIME.md`。
