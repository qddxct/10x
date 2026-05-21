# V3.4 研究报告明细页设计

## 背景
当前回测页已经能展示 V3.4 组合选择器的摘要指标，但摘要只能说明“结果看起来不错”，不能解释“具体买了哪些二串一、为什么这些组合入选、每张票是否命中”。如果要给老板或后续模型复盘使用，需要把研究结果变成可追溯证据链。

## 目标
新增研究报告明细能力，让用户可以从回测页进入某次研究 run 的详情页，查看策略方案、随机对照和每一张二串一明细。

## 非目标
- 不把 V3.4 接入今日推荐。
- 不修改 V3.2 单场候选规则。
- 不在本次做新的模型优化或重新调参。
- 不把所有明细塞进历史回测页，避免主页面过重。

## 用户体验
回测页研究报告卡片增加“查看明细报告”入口，跳转到 `/backtest/research/{runId}`。

详情页包含四个区域：
1. 摘要：模型、区间、最佳策略、候选数、二串一数量、ROI、随机对照 ROI、随机分位。
2. 策略方案：展示最佳策略名称和结构化规则说明，例如组合赔率范围、排除联赛、组单频率、混合选择说明。
3. 随机对照：展示全市场随机和候选池约束随机的 ROI 均值、P80/P90/P95、模型分位。
4. 二串一明细：每张票一行，包含日期、组合赔率、命中、盈亏，以及两条腿的比赛、联赛、选择项、让球数、赔率、赛果、命中状态。

## 数据设计
复用 `model_research_runs` 和 `model_research_artifacts`。

新增 artifact 类型：`combo_ticket`。

每条 `combo_ticket` 保存一张二串一票据，JSON 字段包括：
- `strategy`
- `ticket_date`
- `combo_odds`
- `is_hit`
- `pnl`
- `legs`

每个 leg 包含：
- `match_id`
- `match_date`
- `league`
- `home_team`
- `away_team`
- `bet_type`
- `bet_label`
- `handicap_value`
- `odds`
- `is_hit`
- `result_label`
- `total_score`

策略说明放在 run 的 `summary_json.strategy_rules` 中，页面直接读取，避免硬编码在前端。

## API 设计
新增接口：

`GET /api/research/{run_id}`

返回：
- run 基础信息
- summary_json
- artifacts 按类型分组，其中包含 `combo_simulation`、`random_baseline`

`GET /api/research/{run_id}/tickets?strategy=frequency_selector`

返回指定策略的 `combo_ticket` 列表，默认返回最佳策略。

## 前端设计
新增页面：`frontend/app/backtest/research/[runId]/page.tsx`。

新增客户端组件：`ResearchDetailClient`。

新增 API 方法：
- `getResearchRun(runId)`
- `getResearchTickets(runId, strategy?)`

回测页 `ResearchSummary` 增加详情链接。

## 错误处理
- run 不存在：接口返回 404，页面展示“研究报告不存在”。
- ticket 为空：页面展示“暂无二串一明细”。
- artifact 不存在：摘要仍可展示，但明细区显示空状态。

## 测试策略
后端：
- repository 能按 run 读取 artifacts。
- API 能返回详情。
- API 能按最佳策略返回 tickets。
- V3.4 脚本写入 `combo_ticket` artifact。

前端：
- research API 方法路径正确。
- 摘要卡片显示详情入口。
- 详情页组件能展示摘要、策略、随机对照和二串一明细。

## 验收标准
- 回测页可点击进入 V3.4 详情页。
- 详情页能看到 `frequency_selector` 的规则说明。
- 详情页能看到 139 张二串一明细。
- 页面明细包含平/让平、让球数、赔率、赛果和盈亏。
- 后端测试、前端测试、lint、生产构建通过。

## 金额展示补充
每张二串一按固定 100 元投入展示。

详情页摘要增加：
- 总投入金额：`best_strategy_stake`
- 总回收金额：`best_strategy_return`
- 净盈亏：`best_strategy_pnl`

计算口径：
- `总投入金额 = 二串一数量 * 100`
- `净盈亏 = 所有票据 pnl 求和`
- `总回收金额 = 总投入金额 + 净盈亏`

二串一明细每张票增加单票投入 `stake`，默认 100 元。这样报告能直接回答“投了多少钱、回来了多少钱、挣/赔了多少钱”。
