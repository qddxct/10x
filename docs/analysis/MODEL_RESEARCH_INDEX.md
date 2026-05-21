# 模型研究索引

最后更新: 2026-04-26
维护原则: 所有模型实验、回测报告、页面展示状态必须在这里登记，避免文档腐败。

## 1. 当前结论快照

| 项目 | 当前状态 |
| --- | --- |
| 当前激活生产模型 | `empirical-v2-d104-h104-clean` |
| 当前最佳候选模型 | `empirical-v32-filtered-candidate` |
| 候选模型是否接今日推荐 | 否 |
| 当前研究方向 | V3.4 二串一组单选择器已达标，下一步做稳健性复核 |
| 当前可用历史数据 | 2024-09-28 至 2026-04-22 |
| 数据质量状态 | 随机 20 场网页核验通过，见 `2026-04-26-random20-history-data-quality.md` |

## 2. 模型版本登记

| 版本 | 模型配置名 | 状态 | 作用 | 主要报告 | 页面可见 |
| --- | --- | --- | --- | --- | --- |
| V2 | `empirical-v2-d104-h104-clean` | active | 当前基线/生产激活模型 | `2026-04-24-empirical-v2-clean-analysis.md` | 是 |
| V3 | `empirical-v3-candidate` | inactive | 早期候选，效果不足 | `2026-04-24-empirical-v3-backtest-report.md` | 是 |
| V3.1 | `empirical-v31-combination-candidate` | inactive | 组合候选宽规则，证明方向但普通平拖累 | `2026-04-26-v31-combination-candidate-backtest.md` | 是 |
| V3.2 | `empirical-v32-filtered-candidate` | inactive | 当前最佳候选，过滤后全窗口为正 | `2026-04-26-v32-filtered-candidate-backtest.md` | 是 |
| V3.3 | 暂不新增模型 | 已生成研究 run #3 | 单场因子诊断、二串一模拟、随机对照 | `2026-04-26-v33-single-factor-and-combo-diagnostic.md` | 是，历史研究 |
| V3.4 | 暂不新增模型 | 已生成研究 run #5 | 二串一组单选择器，frequency 达标 | `2026-04-26-v34-combo-selector-backtest.md` | 是，回测页研究摘要 |

## 3. 关键报告索引

| 报告 | 用途 |
| --- | --- |
| `docs/analysis/2026-04-26-random20-history-data-quality.md` | 历史数据质量抽查 |
| `docs/analysis/2026-04-26-v31-v4-recent-score-signal-validation.md` | Titan007 近期比分信号验证 |
| `docs/analysis/2026-04-26-v31-combination-candidate-backtest.md` | V3.1 组合候选回测 |
| `docs/analysis/2026-04-26-v32-filtered-candidate-backtest.md` | V3.2 过滤候选回测 |
| `docs/superpowers/specs/2026-04-26-v33-single-factor-and-combo-diagnostic-design.md` | V3.3 设计文档 |

## 4. V3.2 当前数字

| 指标 | 值 |
| --- | ---: |
| model_config_id | 8 |
| score 数量 | 561 |
| 普通平 score | 514 |
| 让平 score | 47 |
| 全量 ROI | +11.27% |
| 90 天窗口正 ROI | 7/7 |
| 最新回测 session | #98 至 #105 |


## 5. V3.3 当前数字

| 指标 | 值 |
| --- | ---: |
| research_run_id | 3 |
| 输入模型 | `empirical-v32-filtered-candidate` |
| 候选场次 | 561 |
| 同日二串一单数 | 132 |
| 同日二串一 ROI | +17.04% |
| 两日滚动二串一单数 | 144 |
| 两日滚动二串一 ROI | +17.89% |
| 高赔吸引二串一 ROI | -3.24% |
| 全市场随机 ROI 均值 | -20.30% |
| 模型超过全市场随机分位 | 90.3% |
| 约束随机 ROI 均值 | +24.13% |
| 模型超过约束随机分位 | 42.0% |


## 6. V3.4 当前数字

| 指标 | 值 |
| --- | ---: |
| research_run_id | 5 |
| 输入模型 | `empirical-v32-filtered-candidate` |
| 候选场次 | 561 |
| 最佳策略 | `frequency_selector` |
| 二串一单数 | 139 |
| ROI | +49.72% |
| 命中率 | 12.95% |
| 平均组合赔率 | 11.93 |
| 最大连续不中 | 16 |
| 覆盖率 | 24.30% |
| 超过全市场随机分位 | 99.1% |
| 超过候选池约束随机分位 | 81.9% |

## 7. 文档更新规则

1. 新增模型、报告、表结构、页面能力时，必须更新本索引。
2. 历史报告不回写覆盖结论，只在本索引标注当前推荐状态。
3. 如果实现偏离设计，先更新对应设计文档，再继续实现。
4. 所有新增项目文档使用中文。
5. 报告数据必须来自脚本输出或数据库查询，不能手动猜测。

## 8. 下一步

1. 对 V3.4 `frequency_selector` 做 90 天窗口和月度稳健性复核。
2. 检查是否存在过拟合：特别是规避 `德甲/澳超` 与组合赔率 `10-14` 的规则。
3. 稳健性通过后，再设计“今日推荐接入前置检查”，仍不直接接生产。
