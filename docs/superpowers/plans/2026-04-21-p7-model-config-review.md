# P7 · 模型配置管理 + 赛果复盘 实施计划

**日期**：2026-04-21
**范围**：`/model` 权重/阈值/Kelly 带可视化编辑 + 多版本克隆切换；`/dashboard` 内嵌「已结束场次复盘」录入实际命中/下注金额/备注；支撑回测迭代闭环。

## 背景

P1-P6 已完成：数据抓取、评分推荐、回测对比。设计文档第六章剩余两个核心模块：

- **④ 模型配置**：当前 `ModelConfig` 仅由 seed 脚本写入，用户无法在线调权重、阈值、Kelly 带，也无法保存多版本。
- **② 复盘回写**：`match_scores.actual_hit / bet_amount / notes` 字段已建库（P2），但无 UI 录入；没有复盘数据就无法做「推荐→实盘→命中复盘→权重迭代」的闭环。

P7 解锁这两块，使系统具备运营层面的自我演化能力。

## 决策记录（2026-04-21 kickoff 已确认）

- **Q1（模型配置权限）→ admin-only**：仅 `admin` 可 `create/update/clone/activate`。member 只读（`GET /api/model-configs`、`GET /api/model-configs/{id}`）。
- **Q2（版本治理）→ 全局唯一 is_active**：引入 `ModelConfig.is_active`，同时最多一条 `TRUE`；Dashboard / Scheduler / 默认评分读 active；`/backtest` 允许指定任意版本。
- **Q3（复盘录入入口）→ Dashboard Tab + 独立 `/review`**：Dashboard 新增「已结束」Tab，`/review` 为深度页，两者复用同一组件。
- **Q4（复盘写入权限）→ admin-only 写**：`actual_hit / bet_amount / notes` 仅 admin 可 `PATCH`；member 只读。member 端后续若需要个人记录，再补 `bets` 新表（P8+）。
- **Q5（迁移 0006）→ 三项一次落**：
  1. `model_configs.is_active BOOLEAN NOT NULL DEFAULT FALSE`
  2. `model_configs.parent_id INT NULL FK model_configs.id`（克隆来源）
  3. `match_scores.updated_at`（乐观锁，已由 `TimestampMixin` 提供，补数据填充 `created_at` 即可）；若已有则跳过
  4. upgrade() 顺便把 `name='default'` 那条置 `is_active=TRUE`

## 目录

```
backend/
├── app/
│   ├── api/
│   │   ├── model_config.py       # 新增：/api/model-configs CRUD + activate + clone
│   │   └── reviews.py            # 新增：/api/reviews/{score_id} 回写复盘字段
│   ├── schemas/
│   │   ├── model_config.py
│   │   └── review.py
│   └── services/
│       └── model_config.py       # 业务逻辑：克隆/激活切换/引用校验
├── alembic/versions/
│   └── 0006_model_config_active_parent.py
└── tests/
    ├── test_api_model_config.py
    ├── test_api_reviews.py
    └── test_migration_0006.py

frontend/
├── app/
│   ├── model/
│   │   ├── page.tsx
│   │   ├── model-config-client.tsx
│   │   ├── model-config-form.tsx
│   │   ├── weights-editor.tsx
│   │   ├── thresholds-editor.tsx
│   │   ├── kelly-bands-editor.tsx
│   │   └── model-config.module.css
│   └── review/
│       ├── page.tsx
│       ├── review-client.tsx
│       ├── review-row.tsx
│       └── review.module.css
├── components/auth/
│   └── site-header.tsx           # 新增「模型」「复盘」导航
├── lib/
│   ├── model-config/
│   │   ├── api.ts
│   │   └── types.ts
│   └── reviews/
│       ├── api.ts
│       └── types.ts
└── tests/
    ├── model-config-client.test.tsx
    └── review-client.test.tsx
```

## 任务拆分（8 步）

每步：① 先写/扩展测试（Pyest / Vitest） ② 实现 ③ 跑 `ruff + black + pnpm test + pnpm lint` ④ 提交 + 邀请 code review。

### T1 · DB 扩展：ModelConfig.is_active / parent_id + 迁移 0006
- 新增字段 `is_active BOOLEAN NOT NULL DEFAULT FALSE`，`parent_id INT NULL FK(model_configs.id)`
- upgrade() 同时把现有行中 `name='default'` 的那条置为 `is_active=TRUE`（Q2 全局唯一）
- 测试：`tests/test_migration_0006.py` 验证 upgrade/downgrade、重复激活校验

### T2 · ModelConfig 后端服务 + API
- `services/model_config.py`：`list / get / create / update / clone / activate`
  - `activate(id)` 事务内把其他行 `is_active=FALSE` 再置目标 `TRUE`
  - `clone(id, name)` 深拷贝 weights/thresholds/kelly_bands，`parent_id=src.id`
  - 更新 active 配置前需拷贝为新版本（防止篡改历史回测对比口径）
- `api/model_config.py`：`GET /`、`GET /{id}`、`POST /`、`PATCH /{id}`、`POST /{id}/clone`、`POST /{id}/activate`
- 权限：只读成员皆可；写操作仅 `admin`
- 测试：`tests/test_api_model_config.py` 覆盖权限、激活切换、克隆链路、update-on-active-拷贝分支

### T3 · 修改 ScoringService / Dashboard 默认读 active
- `dashboard/api.py::latest_scores` 默认过滤 `ModelConfig.is_active=TRUE`
- 前端 dashboard 头部显示当前激活的模型名称，下拉可切换（只改查询参数，不改 active）
- 测试：`tests/test_scores_api.py` 新增用例；`frontend/tests/dashboard-client.test.tsx` 新增切换下拉

### T4 · Review 后端 API
- `schemas/review.py`：`ReviewUpdate { actual_hit, bet_amount, notes }`
- `api/reviews.py`：
  - `GET /api/reviews?date_from&date_to&only_recommended` → 已结束 + 评分存在的场次列表，附带 `actual_result` 冗余字段
  - `PATCH /api/reviews/{score_id}` → 更新 match_scores 的三个字段
- 权限：成员只能改自己 match_scores (user_id 为空视作公共数据，admin 可写所有)
- 测试：`tests/test_api_reviews.py` 覆盖批量查询、权限隔离、actual_hit 自动预填（GET 返回 `suggested_actual_hit`）

### T5 · 前端「模型配置」页
- 路由 `/model`（admin 进入可编辑，member 进入只读）
- 三段编辑器：
  - `WeightsEditor`：6 维滑杆 + 数字输入（0-30），实时显示总分上限
  - `ThresholdsEditor`：`recommend_total_score` / `draw_min_score` / `handicap_draw_min_score`
  - `KellyBandsEditor`：动态增删区间，展示带 [min, max) → pct 预览
- 顶部：`ModelConfigList`，每行显示名字/激活徽标/创建时间/「克隆 / 激活 / 编辑」按钮
- 测试：`model-config-client.test.tsx` 覆盖加载、切换激活、克隆后 list 刷新、提交验证 (Zod)

### T6 · 前端「复盘」页
- 路由 `/review`，也可从 Dashboard `已结束` Tab 跳转 (query 参数过滤日期)
- `ReviewRow` 每行：比赛信息、评分快照 (total_score / bet_type / kelly_pct)、实际结果、`actual_hit` 切换、`bet_amount` 输入、`notes` 文本
- 批量筛选：日期、联赛、仅推荐、命中/未命中
- 底部汇总条：本筛选下 命中率 / 实际投注 / 实际收益 (基于 `bet_amount * (odds - 1)` 或 `-bet_amount`，配合赔率查询)
- 测试：`review-client.test.tsx` 覆盖列表加载、`PATCH` 乐观更新、权限只读（member 看到他人数据禁用控件）

### T7 · 端到端冒烟
- `backend/tests/test_p7_smoke.py`：
  - 流程：admin 创建模型 V2 → 激活 → dashboard 使用 V2 → 用户复盘更新 score → 再跑 backtest V2 命中预期
- `frontend/tests/smoke.test.tsx` 增加 `/model` 和 `/review` 路由渲染

### T8 · 文档 + 部署补丁
- 更新 `README.md` 的 Feature Matrix 勾选 ④⑤ 条目
- `docs/superpowers/guides/model-config-workflow.md`：撰写 admin 调权重 → 回测验证 → 激活 → 复盘 → 再调的使用手册
- `scripts/bootstrap.py`（或 seed 补丁）：保证 `default` 配置被标记为 active

## 非目标（P8+ 再议）

- **历史赔率快照** (`match_odds_history`)：P6 决策 Q1 已延后，需求更成熟后再推
- **盘口异动告警** / **消息推送**：属于设计文档第九章后续可扩展
- **爬虫管理面板**：当前 P4 以脚本/定时为主，完整 UI 需独立 P8
- **短信验证码登录**：依赖三方通道接入

## 风险 & 依赖

- R1：激活版本切换会影响 Dashboard 展示口径，需要同步通知客户端（短期轮询即可）
- R2：复盘批量更新可能并发冲突 → 使用乐观锁（match_scores.updated_at）
- R3：Kelly 带用户输入区间可能互相重叠；前端校验 + 后端 Zod/Pydantic 双重保障
- R4：代码审查 P6 仍有 M1-M8 小项，P7 同步吸收（M1 match_scores.updated_at 字段补齐，恰好服务复盘乐观锁）

## 验收

- [x] 迁移 0006 在已有 MySQL 与新的 SQLite 测试库双向跑通
- [x] admin 能在 UI 完整完成「克隆 → 调权 → 激活」三步
- [x] 复盘页 admin 可写、member 全场只读
- [x] `/backtest` 选择任意历史 config（非激活）仍能跑通（`_resolve_model_config_id` 优先使用传入 id，否则 resolve_default → active → oldest）
- [x] 新增测试：后端 `test_api_model_config` / `test_api_reviews` / `test_p7_smoke` 共 +21 用例；前端 `model-client` / `review-client` / `p7-routes` 共 +13 用例，全量 CI 绿

## 交付清单

- 后端新增：`api/model_config.py`、`api/reviews.py`、`services/model_config.py`、`schemas/{model_config,review}.py`、`alembic/versions/0006_model_config_active_parent.py`
- 后端修改：`api/scores.py`、`api/backtest.py`、`scheduler/main.py`、`scheduler/jobs.py`、`scripts/seed.py`（`ensure_default_config` 补 active 提升）
- 前端新增：`app/model/*`、`app/review/*`、`lib/model-config/*`、`lib/reviews/*`、`components/auth/site-header.tsx` 新导航
- 前端修改：`app/dashboard/dashboard-client.tsx`（模型切换 + 已结束 Tab）
- 文档：`README.md` Feature Matrix、`docs/superpowers/guides/model-config-workflow.md`
