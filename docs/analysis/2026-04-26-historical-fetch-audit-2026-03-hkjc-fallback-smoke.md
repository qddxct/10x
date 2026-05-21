# 历史抓取旁路审计报告

- 审计 run: #6
- 日期范围: 2026-03-01 -> 2026-03-01
- 新抓快照场次: 15
- 有 Titan007 映射: 15
- 有 Titan007 欧赔: 15
- 有 Titan007 analysis 状态: 15
- 字段级差异: 3

## 差异严重程度

| 类型 | 数量 |
|---|---:|
| missing_existing | 3 |
| missing_audit | 0 |
| mismatch | 0 |

## 结论

本次发现字段级差异, 需要按下方 Top 字段抽样核验网页。

## 差异字段 Top 30

| 分类 | 字段 | 类型 | 数量 |
|---|---|---|---:|
| odds | win_odds | missing_existing | 1 |
| odds | draw_odds | missing_existing | 1 |
| odds | lose_odds | missing_existing | 1 |

## 初步解读

- `missing_existing` 多, 说明正式表可能缺数据, 新链路能补齐。
- `missing_audit` 多, 说明新抓链路覆盖不足, 需要优先查 Titan007 映射或 analysis 页面。
- `mismatch` 多, 说明两边都有值但不同, 需要抽样打开网页核验。
