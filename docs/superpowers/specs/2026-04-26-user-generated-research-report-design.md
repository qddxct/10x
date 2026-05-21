# 用户自助生成区间研究报告设计

## 目标

让用户可以在网页上选择一个历史时间区间，一键生成该区间的二串一研究报告，并在生成完成后直接跳转到报告详情页查看组合策略、随机对照、投入收益和明细方案。

## 背景

当前二串一研究报告主要通过命令行脚本 `app.scripts.v34_combo_selector` 生成。用户想自己选择时间范围并在网页上生成报告，减少对开发者手动执行脚本的依赖。

当前运行态模型已经收敛为：

- `default`: 基线对照模型。
- `empirical-v32-filtered-candidate`: 当前候选模型，也是二串一研究报告默认模型。

本功能第一版只服务“二串一研究报告”生成，不把 90 天历史回测和今日推荐混入同一个操作。

## 设计结论

采用“同步生成”的第一版方案：

1. 用户在二串一测试报告页面填写开始日期、结束日期、随机试验次数、随机种子。
2. 用户点击“生成研究报告”。
3. 后端检查并补齐该区间内 `empirical-v32-filtered-candidate` 的历史 score。
4. 后端基于该区间生成 V3.4 二串一研究报告。
5. 报告写入 `model_research_runs` 和 `model_research_artifacts`。
6. 前端拿到新 `run_id` 后跳转到 `/combo-reports/{run_id}`。

第一版暂不引入异步任务队列。生成期间按钮展示 loading，页面等待接口返回。

## 非目标

第一版不做以下内容：

- 不自动生成 `default` 历史 score。
- 不自动跑 90 天窗口历史回测。
- 不接今日推荐。
- 不做后台任务队列、进度条、取消任务、任务恢复。
- 不删除旧报告，除非后续明确增加“替换旧报告”选项。

## 页面入口

页面：`/combo-reports`

新增区域：`生成研究报告`

字段：

- 开始日期：必填。
- 结束日期：必填。
- 模型：第一版固定为 `empirical-v32-filtered-candidate`，页面可展示但不允许编辑。
- 随机试验次数：默认 `1000`，允许用户编辑。
- 随机种子：默认 `20260426`，允许用户编辑。

按钮：

- `生成报告`

交互：

- 生成中禁用按钮，显示“正在生成研究报告...”或同类文案。
- 成功后跳转到 `/combo-reports/{run_id}`。
- 失败时在页面顶部显示后端错误信息。

## 后端接口

新增接口：`POST /api/research/generate-combo-report`

请求体：

```json
{
  "date_from": "2025-01-01",
  "date_to": "2025-03-31",
  "model_name": "empirical-v32-filtered-candidate",
  "random_trials": 1000,
  "random_seed": 20260426
}
```

第一版前端固定传 `model_name=empirical-v32-filtered-candidate`。后端仍保留字段，方便后续扩展。

响应体：

```json
{
  "run_id": 10,
  "report_path": "docs/analysis/generated/v34-combo-selector-2025-01-01-2025-03-31-run-10.md",
  "score_summary": {
    "matches": 520,
    "existing_scores": 80,
    "written_scores": 42,
    "candidate_scores": 122
  },
  "research_summary": {
    "best_strategy": "frequency_selector",
    "best_strategy_combo_count": 22,
    "best_strategy_roi": 0.18
  }
}
```

## 后端服务边界

新增服务模块建议：`backend/app/research/generator.py`

职责：

- 校验日期和模型。
- 调用 V3.2 候选 score 生成逻辑。
- 调用 V3.4 二串一研究报告生成逻辑。
- 返回结构化生成结果。

为避免 API 直接调用 CLI，现有脚本需要轻量拆分：

- `v31_combination_candidate_backtest.py` 保留 CLI，同时暴露可复用函数生成指定区间的 V3.2 score。
- `v34_combo_selector.py` 保留 CLI，同时暴露可复用函数生成指定区间的二串一报告。

这样页面、API、脚本都使用同一套核心逻辑，避免后续维护两份实现。

## Score 补齐策略

第一版采用“覆盖式生成当前区间 V3.2 score”的简单策略：

- 先删除该模型在目标区间内已有 score。
- 再按当前 V3.2 规则重新生成该区间 score。

原因：

- 当前处于模型打磨阶段，规则会变化。
- 覆盖式生成比“只补缺失”更可复现。
- 避免旧规则 score 与新规则 score 混在一个区间里。

后端响应里展示 `replaced_old_scores` 和 `recommended_scores`，让用户知道本次改写了多少数据。

## 报告文件命名

页面生成的报告统一放在：

`docs/analysis/generated/`

文件名格式：

- Markdown：`v34-combo-selector-{date_from}-{date_to}-run-{run_id}.md`
- 二串一明细 CSV：`v34-combo-selector-{date_from}-{date_to}-tickets-run-{run_id}.csv`
- 随机对照 CSV：`v34-combo-selector-{date_from}-{date_to}-random-run-{run_id}.csv`

由于 `run_id` 在保存数据库后才知道，服务可以先生成临时路径，保存 run 后再更新 `report_path` 和文件名；或者使用时间戳文件名。第一版推荐使用时间戳，避免二次更新复杂度。

实际第一版格式：

- `docs/analysis/generated/v34-combo-selector-{date_from}-{date_to}-{YYYYMMDDHHMMSS}.md`
- `docs/analysis/generated/v34-combo-selector-{date_from}-{date_to}-{YYYYMMDDHHMMSS}-tickets.csv`
- `docs/analysis/generated/v34-combo-selector-{date_from}-{date_to}-{YYYYMMDDHHMMSS}-random.csv`

## 校验规则

- `date_from <= date_to`。
- `random_trials` 范围：`100` 到 `5000`。
- `random_seed` 范围：`1` 到 `999999999`。
- 模型必须存在。
- 区间内必须有已完赛比赛。
- 生成 V3.2 score 后必须至少有 2 个候选，否则二串一无法成组，返回清晰错误。

## 错误处理

后端错误示例：

- 日期非法：`date_from must be <= date_to`
- 模型不存在：`ModelConfig not found`
- 区间无比赛：`No finished matches in selected range`
- 候选不足：`Not enough candidates to build combo report`
- 生成失败：返回异常摘要，前端展示“报告生成失败：...”

第一版失败时不创建 `failed` run，避免页面堆积无效报告。后续如果做异步任务，再引入 failed 状态。

## 权限

沿用当前研究报告 API 的登录要求。第一版所有登录用户都可以生成报告。

如果后续开放给普通用户，需要再考虑：

- 是否只允许 admin 生成。
- 是否限制时间范围。
- 是否限制随机试验次数。
- 是否记录创建者。

## 测试策略

后端测试：

- 日期非法返回 400。
- 模型不存在返回 404 或 400。
- 正常区间会写入 V3.2 score 和 research run。
- 候选不足时返回清晰错误。
- 核心生成函数可以被 CLI 和 API 共同调用。

前端测试：

- 页面展示生成表单。
- 点击生成按钮调用 API。
- 成功后跳转到详情页。
- 失败时显示错误。

浏览器验证：

- 登录后打开 `/combo-reports`。
- 输入一个小区间生成报告。
- 验证跳转到 `/combo-reports/{run_id}`。
- 验证详情页展示金额、随机对照、二串一明细。

## 后续扩展

后续可以升级为异步任务：

- `model_research_runs.status=running` 先入库。
- 后台任务逐步写 artifacts。
- 前端轮询 run 状态。
- 展示“生成 score / 组合计算 / 随机对照 / 完成”的进度。
