# V3.4 研究报告明细页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 V3.4 研究报告新增可追溯明细页，展示策略规则、随机对照和每张二串一票据。

**Architecture:** 后端继续使用 `model_research_runs` 和 `model_research_artifacts`，新增 `combo_ticket` artifact 类型并提供详情 API。前端从回测页摘要卡片跳转到独立详情页，详情页按摘要、策略、对照、票据四块展示。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pytest、Next.js App Router、React Testing Library、Vitest。

---

### Task 1: 后端 artifact 类型和查询接口

**Files:**
- Modify: `backend/app/models/research.py`
- Modify: `backend/app/research/repository.py`
- Modify: `backend/app/schemas/research.py`
- Modify: `backend/app/api/research.py`
- Test: `backend/tests/test_research_api.py`

- [ ] 写失败测试：创建 research run 和 artifacts，断言 `GET /api/research/{id}` 返回 artifacts 分组，`GET /api/research/{id}/tickets` 返回最佳策略 tickets。
- [ ] 运行测试，确认因为接口不存在或 schema 缺字段失败。
- [ ] 在 Enum 中增加 `combo_ticket`。
- [ ] 增加 repository 函数：`get_research_run`、`research_artifacts_by_run`、`research_tickets`。
- [ ] 增加 Pydantic schema：`ResearchArtifactRead`、`ResearchRunDetailRead`、`ResearchTicketRead`。
- [ ] 实现 API 路由。
- [ ] 跑后端 API 测试确认通过。

### Task 2: V3.4 脚本写入票据明细

**Files:**
- Modify: `backend/app/scripts/v34_combo_selector.py`
- Test: `backend/tests/test_research_combo_selector.py`

- [ ] 写失败测试：构造 `ComboTicket`，断言票据 artifact payload 包含两条腿、选择项中文、让球数、赔率、赛果、盈亏。
- [ ] 运行测试，确认缺少序列化函数失败。
- [ ] 增加 `_ticket_payload(strategy, ticket)` 和 `_leg_payload(candidate)`。
- [ ] 保存 artifacts 时追加 `("combo_ticket", strategy, payload)`。
- [ ] 跑 V3.4 相关测试确认通过。

### Task 3: 前端 API 和摘要入口

**Files:**
- Modify: `frontend/lib/research/types.ts`
- Modify: `frontend/lib/research/api.ts`
- Modify: `frontend/app/backtest/research-summary.tsx`
- Test: `frontend/tests/research-api.test.ts`
- Test: `frontend/tests/research-summary.test.tsx`

- [ ] 写失败测试：断言 API 调用 `/api/research/6` 和 `/api/research/6/tickets`；断言摘要卡片显示“查看明细报告”。
- [ ] 运行测试，确认新方法或链接不存在失败。
- [ ] 增加类型定义和 API 方法。
- [ ] 摘要卡片增加详情链接。
- [ ] 跑前端相关测试确认通过。

### Task 4: 前端详情页

**Files:**
- Create: `frontend/app/backtest/research/[runId]/page.tsx`
- Create: `frontend/app/backtest/research/[runId]/research-detail-client.tsx`
- Create: `frontend/app/backtest/research/[runId]/research-detail.module.css`
- Test: `frontend/tests/research-detail-client.test.tsx`

- [ ] 写失败测试：传入 run detail 和 tickets，断言页面显示摘要、策略规则、随机对照、票据 leg 明细。
- [ ] 运行测试，确认组件不存在失败。
- [ ] 实现服务端页面读取 params 并渲染客户端组件。
- [ ] 实现详情组件和样式。
- [ ] 跑前端详情页测试确认通过。

### Task 5: 回填 V3.4 run 并浏览器验证

**Files:**
- Generated DB data only
- Generated docs/csv report files only

- [ ] 运行 V3.4 脚本 `--replace`，写入 `combo_ticket` artifacts。
- [ ] 用 SQL 或 API 确认 run 最新、ticket 数量为 139。
- [ ] 重建 backend/frontend 容器。
- [ ] 用浏览器打开 `/backtest`，点击/访问详情页，确认摘要和明细显示。

### Task 6: 全量验证

- [ ] 后端测试：`cd backend && .venv/bin/python -m pytest tests/test_research_api.py tests/test_research_combo_selector.py -q`
- [ ] 后端 Ruff：`cd backend && .venv/bin/python -m ruff check app/research app/api/research.py app/scripts/v34_combo_selector.py tests/test_research_api.py tests/test_research_combo_selector.py`
- [ ] 前端测试：`cd frontend && pnpm test -- research-api.test.ts research-summary.test.tsx research-detail-client.test.tsx`
- [ ] 前端 lint：`cd frontend && pnpm lint --file app/backtest/research-summary.tsx --file 'app/backtest/research/[runId]/research-detail-client.tsx' --file lib/research/api.ts --file lib/research/types.ts`
- [ ] 生产构建：`docker compose up -d --build backend frontend`

### Task 7: 金额口径展示

**Files:**
- Modify: `backend/app/scripts/v34_combo_selector.py`
- Modify: `frontend/app/backtest/research/[runId]/research-detail-client.tsx`
- Test: `backend/tests/test_research_combo_selector.py`
- Test: `frontend/tests/research-detail-client.test.tsx`

- [ ] 写失败测试：票据 payload 包含 `stake=100`，详情页摘要显示总投入、总回收、净盈亏，票据行显示单票投入。
- [ ] 运行测试确认失败。
- [ ] V3.4 summary 增加 `best_strategy_stake`、`best_strategy_pnl`、`best_strategy_return`。
- [ ] 详情页增加金额卡片和单票投入文案。
- [ ] 重跑 V3.4 写入金额字段。
- [ ] 浏览器验证详情页金额展示。
