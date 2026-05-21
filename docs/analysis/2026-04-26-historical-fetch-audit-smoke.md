# 历史抓取旁路审计报告

- 审计 run: #2
- 日期范围: 2024-09-28 -> 2024-09-29
- 新抓快照场次: 30
- 有 Titan007 映射: 30
- 有 Titan007 欧赔: 30
- 有 Titan007 analysis 状态: 30
- 字段级差异: 0

## 差异严重程度

| 类型 | 数量 |
|---|---:|
| missing_existing | 0 |
| missing_audit | 0 |
| mismatch | 0 |

## 差异字段 Top 30

| 分类 | 字段 | 类型 | 数量 |
|---|---|---|---:|

## 初步解读

- `missing_existing` 多, 说明正式表可能缺数据, 新链路能补齐。
- `missing_audit` 多, 说明新抓链路覆盖不足, 需要优先查 Titan007 映射或 analysis 页面。
- `mismatch` 多, 说明两边都有值但不同, 需要抽样打开网页核验。
