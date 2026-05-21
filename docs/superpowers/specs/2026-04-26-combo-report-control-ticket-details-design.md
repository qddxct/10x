# 二串一报告对照组明细设计

## 背景

二串一报告明细页当前包含三类信息：

1. 模型最佳策略摘要。
2. 两个随机对照组的 ROI / P90 / 模型分位。
3. 模型最佳策略的二串一逐票明细。

页面上“随机对照”和“二串一明细”相邻展示，但二串一明细没有明确说明属于模型方案；同时两个随机对照组只有统计指标，没有逐票明细。这样会造成误解：用户可能以为下方明细属于某个随机对照组，或者以为随机对照不可审计。

## 目标

1. 二串一报告明细页展示三组逐票明细：
   - 模型最佳策略。
   - 全市场随机。
   - 候选池约束随机。
2. 每组明细都有清晰标题、说明、投入、回收、盈亏、ROI、票数。
3. 随机对照组明细使用与汇总指标同一随机过程生成，保证可追溯。
4. 前端不再把“随机对照汇总”和“模型方案明细”混在一起；明细区按组分块展示。
5. 旧模型报告如果没有随机逐票明细，需要显示缺失提示；重新生成后的报告应完整展示三组明细。

## 非目标

1. 本次不改变模型选号算法。
2. 本次不改变随机对照汇总统计口径。
3. 本次不支持在页面上切换任意随机 trial；只保存并展示一个代表性 trial 的逐票明细。
4. 本次不新增业务表，继续使用 `model_research_artifacts` 保存产物；需要扩展 `artifact_type` 枚举以支持 `random_ticket`。

## 数据设计

继续使用 `model_research_artifacts`：

| artifact_type | label | payload_json |
|---|---|---|
| `combo_ticket` | `frequency_selector` | 模型策略逐票明细 |
| `random_ticket` | `frequency_selector:全市场随机` | 全市场随机代表性逐票明细 |
| `random_ticket` | `frequency_selector:候选池约束随机` | 候选池约束随机代表性逐票明细 |

`random_ticket` 的 payload 与 `combo_ticket` 保持同结构，额外包含：

- `group_type`: `random_control`
- `control_label`: `全市场随机` 或 `候选池约束随机`
- `strategy`: 对应模型策略，例如 `frequency_selector`

## 随机明细生成口径

`run_random_combo_baseline()` 仍负责生成随机 ROI 分布。新增一个函数生成代表性随机票：

- 使用同一个候选池。
- 使用同一 `ticket_count`。
- 使用固定 seed。
- 生成一组随机票，作为“随机对照明细样本”。

注意：随机汇总指标来自多次 trial 的分布；随机明细是其中一个固定 seed 的可审计样本，不代表均值本身。因此页面文案应写清楚：

> 随机明细为固定 seed 的代表性样本，用于说明随机组选票构成；随机 ROI 以汇总分布为准。

## API 设计

新增接口：

`GET /api/research/{run_id}/ticket-groups`

返回：

```json
[
  {
    "group_key": "model:frequency_selector",
    "title": "模型最佳策略：frequency_selector",
    "description": "模型选择出的实际二串一方案。",
    "summary": { "ticket_count": 139, "stake": 13900, "returns": 20811.08, "pnl": 6911.08, "roi": 0.4972 },
    "tickets": []
  },
  {
    "group_key": "random:frequency_selector:全市场随机",
    "title": "对照组：全市场随机",
    "description": "固定 seed 的随机样本；随机 ROI 以汇总分布为准。",
    "summary": { "ticket_count": 139, "stake": 13900, "returns": 10904.5, "pnl": -2995.5, "roi": -0.2155 },
    "tickets": []
  }
]
```

## 前端设计

`/combo-reports/[runId]`：

1. 保留上方摘要、策略方案、随机对照汇总。
2. 明细区改为 `二串一逐票明细`。
3. 明细区下按组展示：
   - `模型最佳策略：frequency_selector`
   - `对照组：全市场随机`
   - `对照组：候选池约束随机`
4. 每组先展示金额汇总，再展示票列表。
5. 如果某个分组没有逐票明细，显示：`该组暂无逐票明细。`

## 验收标准

1. 页面能同时看到模型组、全市场随机组、候选池约束随机组三组明细。
2. 每组明细标题明确，不会误解明细归属。
3. 两个随机对照组仍显示随机汇总指标。
4. 重新生成 V3.4 报告后，当前最新报告包含 `random_ticket` 产物。
5. 后端 API、研究脚本、前端页面相关测试通过。
