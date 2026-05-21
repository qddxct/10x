# 历史抓取旁路审计报告

- 审计 run: #5
- 日期范围: 2026-03-01 -> 2026-03-31
- 新抓快照场次: 0
- 有 Titan007 映射: 0
- 有 Titan007 欧赔: 0
- 有 Titan007 analysis 状态: 0
- 字段级差异: 0

## 差异严重程度

| 类型 | 数量 |
|---|---:|
| missing_existing | 0 |
| missing_audit | 0 |
| mismatch | 0 |

## 结论

本次日期范围没有抓到可审计比赛, 需要更换日期范围。

## 差异字段 Top 30

| 分类 | 字段 | 类型 | 数量 |
|---|---|---|---:|

## 抓取失败日期

- 2026-03-01: retry exhausted status=500
- 2026-03-02: retry exhausted status=500
- 2026-03-03: retry exhausted status=500
- 2026-03-04: retry exhausted status=500
- 2026-03-05: retry exhausted status=500
- 2026-03-06: retry exhausted status=500
- 2026-03-07: retry exhausted status=500
- 2026-03-08: retry exhausted status=500
- 2026-03-09: retry exhausted status=500
- 2026-03-10: retry exhausted status=500
- 2026-03-11: retry exhausted status=500
- 2026-03-12: retry exhausted status=500
- 2026-03-13: retry exhausted status=500
- 2026-03-14: retry exhausted status=500
- 2026-03-15: retry exhausted status=500
- 2026-03-16: retry exhausted status=500
- 2026-03-17: retry exhausted status=500
- 2026-03-18: retry exhausted status=500
- 2026-03-19: retry exhausted status=500
- 2026-03-20: retry exhausted status=500
- 2026-03-21: retry exhausted status=500
- 2026-03-22: retry exhausted status=500
- 2026-03-24: retry exhausted status=500
- 2026-03-26: retry exhausted status=500
- 2026-03-27: retry exhausted status=500
- 2026-03-28: retry exhausted status=500
- 2026-03-29: retry exhausted status=500
- 2026-03-30: retry exhausted status=500
- 2026-03-31: retry exhausted status=500

## 初步解读

- `missing_existing` 多, 说明正式表可能缺数据, 新链路能补齐。
- `missing_audit` 多, 说明新抓链路覆盖不足, 需要优先查 Titan007 映射或 analysis 页面。
- `mismatch` 多, 说明两边都有值但不同, 需要抽样打开网页核验。
