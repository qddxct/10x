# 回测与二串一报告页面拆分设计

## 背景

当前 `/backtest` 页面同时承载两类任务：

1. 历史回测：发起模型回测、查看历史回测、对比两次回测、查看下注明细。
2. 二串一测试报告：展示组合策略研究摘要，并跳转到组合报告明细。

这两类任务目标不同：历史回测回答“单场/模型历史表现怎么样”，二串一报告回答“按组合策略下单，频率、投入、收益和随机对照表现怎么样”。继续放在同一页会让页面语义混乱，也会让后续功能迭代互相干扰。

## 目标

1. `/backtest` 只保留历史回测相关能力。
2. 新增 `/combo-reports` 作为二串一测试报告入口页。
3. 将二串一报告明细从 `/backtest/research/[runId]` 迁移到 `/combo-reports/[runId]`。
4. 旧路径 `/backtest/research/[runId]` 临时保留跳转，避免已有链接失效。
5. 保持现有后端 `research` API 不变，本次只调整前端信息架构和路由。
6. 所有新增页面文案使用中文。

## 非目标

1. 本次不新增二串一报告生成能力。
2. 本次不修改研究报告表结构。
3. 本次不改变历史回测 API 和回测算法。
4. 本次不重做整体导航系统，只在相关页面中提供清晰入口。

## 页面结构

### 历史回测页 `/backtest`

保留：

- 回测条件表单。
- 历史回测列表。
- 回测删除。
- 回测对比篮和双回测对比。
- 单次回测概览。
- 下注明细。

移除：

- 二串一研究报告摘要卡片。
- `getLatestResearchRun()` 请求。
- 指向 `/backtest/research/[runId]` 的报告入口。

新增：

- 页头或辅助入口中放一个轻量链接：“查看二串一测试报告”，跳转 `/combo-reports`。

### 二串一报告页 `/combo-reports`

新增独立页面，职责是“报告入口与摘要”。首版只展示最新报告，后续可扩展为报告列表。

内容：

- 页面标题：`二串一测试报告`。
- 说明：展示组合策略、随机对照、投入收益和明细入口。
- 最新报告摘要卡片，复用现有 `ResearchSummary` 展示指标。
- 无报告时显示空状态。

链接：

- “返回历史回测”链接到 `/backtest`。
- “查看明细报告”链接到 `/combo-reports/[runId]`。

### 二串一报告明细页 `/combo-reports/[runId]`

迁移现有 `/backtest/research/[runId]` 功能：

- 报告摘要。
- 策略规则。
- 随机对照。
- 二串一明细。
- 每张票展示投入、组合赔率、命中状态、盈亏。
- 每个选项展示比赛、选择、让球数、赔率、赛果、分数。

页面返回链接改为 `/combo-reports`。

### 旧路径兼容 `/backtest/research/[runId]`

旧路径页面不再维护报告 UI，只做跳转到 `/combo-reports/[runId]`。

## 组件边界

| 组件/文件 | 职责 |
|---|---|
| `BacktestClient` | 只管理历史回测状态和交互 |
| `ResearchSummary` | 报告摘要展示组件，移动到报告路由目录或保持可复用路径 |
| `ComboReportsClient` | 新增，加载最新报告并展示摘要 |
| `ResearchDetailClient` | 迁移到 `/combo-reports/[runId]`，继续展示明细 |
| `research` API client | 不变，继续访问 `/api/research` |

## 数据流

1. `/backtest` 调用 `listBacktests/createBacktest/getBacktest/compareBacktests/deleteBacktest/listModelConfigs`。
2. `/combo-reports` 调用 `getLatestResearchRun()`。
3. `/combo-reports/[runId]` 调用 `getResearchRun(runId)` 和 `getResearchTickets(runId, best_strategy)`。
4. `/backtest/research/[runId]` 直接重定向到 `/combo-reports/[runId]`。

## 测试策略

1. 更新 `BacktestClient` 测试，证明历史回测页不再请求最新研究报告，也不渲染研究报告卡片。
2. 新增 `ComboReportsClient` 测试，证明有报告时展示摘要并链接到 `/combo-reports/[id]`。
3. 更新 `ResearchSummary` 测试，链接断言改为 `/combo-reports/[id]`。
4. 更新报告明细测试，导入新路径组件，并确认返回链接指向 `/combo-reports`。
5. 运行前端相关测试和 lint/类型检查（若项目脚本可用）。

## 验收标准

1. `/backtest` 页面没有二串一研究报告摘要。
2. `/combo-reports` 可以看到最新二串一报告摘要。
3. `/combo-reports/[runId]` 可以看到原有二串一明细报告。
4. `/backtest/research/[runId]` 不显示旧页面，自动跳到 `/combo-reports/[runId]`。
5. 相关前端测试通过。
