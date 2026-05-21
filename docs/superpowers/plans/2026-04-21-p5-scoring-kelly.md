# P5 · 评分引擎与 Kelly 策略 实施计划

**日期**：2026-04-21  
**范围**：6 维评分、Kelly 档位、ScoringService、API、Scheduler 打分任务、前端 Dashboard（列表 + 详情 + 覆盖）

## 决策记录

- **Q1 (战意/赛制数据来源)**：B — 规则推断 `competition_type`：
  - `league.name` 含"欧冠/欧联/亚冠/世界杯/杯赛/淘汰赛"→ `knockout_first_leg`（简化先统一"杯赛"）
  - `round` 包含"首回合"→ `knockout_first_leg`，"次回合"→ `knockout_second_leg`
  - 其他 → `league`
  - MVP 不爬 `round`，默认全部按 `competition_type=league`；未来 P5.x 再补爬。T1 增一个 `infer_competition_type()` 工具函数便于以后替换。
- **Q2 (计算与存储)**：C — Scheduler 预算 + 手动触发兼备
  - Scheduler 新增 `scoring` job（每日 09:15）批量算当日全部比赛
  - API 支持 `POST /api/scores/compute` 手动触发 + 覆盖
- **Q3 (前端范围)**：C — 列表 + 单场详情 + 手动覆盖
- **Q4 (match_scores 语义)**：A — 系统评分 `user_id=NULL`，`(match_id, model_config_id)` 唯一；用户下注字段（`bet_amount`、`actual_hit`、`notes`）允许覆盖但暂不引入多用户拆分

## 目录

```
backend/
├── app/
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── scoring.py            # 6 维纯函数 + total + infer_competition_type
│   │   ├── kelly.py              # 半 Kelly 档位映射
│   │   └── service.py            # ScoringService：读 DB、算分、upsert
│   ├── schemas/
│   │   └── scores.py
│   ├── api/
│   │   └── scores.py
│   └── scheduler/
│       └── jobs.py               # 新增 run_scoring_job
├── alembic/versions/
│   └── 0003_match_scores_unique.py  # (match_id, model_config_id) unique
└── tests/
    ├── test_engine_scoring.py
    ├── test_engine_kelly.py
    ├── test_engine_service.py
    ├── test_scores_api.py
    └── test_scheduler_scoring.py

frontend/
├── app/dashboard/
│   ├── page.tsx
│   ├── dashboard-client.tsx
│   ├── dashboard-client.module.css
│   ├── score-detail.tsx
│   └── score-edit.tsx
├── lib/scores/
│   ├── api.ts
│   └── types.ts
└── tests/
    ├── scores-api.test.ts
    ├── dashboard-client.test.tsx
    └── score-detail.test.tsx
```

## 任务

### T1 · match_scores 唯一索引 + migration
- Alembic `0003`：为 `match_scores` 添加 `uq_match_scores_match_config` 唯一索引 `(match_id, model_config_id)`；`user_id` 保持 nullable
- 测试：ORM round-trip 验证唯一约束冲突

### T2 · scoring.py 6 维纯函数
- `euro_score(win, draw, lose) -> int` (0-25)
  - 计算离散度：三项 `|odd - mean| / mean` 的最大值 → 高分段接近
  - 参考手册 4.1：胜/负 2.30-2.80、平 3.00-3.40 → 25 分
- `asian_score(asian_handicap) -> int`：平手 20 / 平半 15 / 半球 5 / 其他 0
- `goals_score(total_goals) -> int`：≤2.25 → 20, =2.5 → 10, ≥2.75 → 0
- `compression_score(draw_odds) -> int`：≤3.2 → 20, 3.2-3.5 → 10, ≥3.6 → 0
- `intent_score(competition_type, round) -> int`：杯赛/淘汰赛 15，其他 5
- `team_stats_score(stats) -> int`：近期状态 + 排名接近度 + 主客场平局率
- `total_score(weights, parts) -> int`：按 model_config.weights_json 比例加权（手册默认权重需可覆盖）
- `infer_competition_type(league_name, round) -> str`：B 决策的规则实现
- 全部测试驱动，每个函数 3-5 个用例

### T3 · kelly.py Kelly 档位
- `kelly_pct(score: int, bands: dict) -> float`：读 `ModelConfig.kelly_bands_json`（已 seed 为手册"半Kelly"档位）
- `suggest_bet_type(match, odds, score) -> "draw"|"handicap_draw"|None`：
  - 若 `asian_handicap` 为平手/平半 → 优先 draw
  - 含让球且让平赔率 ≥3.5 → handicap_draw
  - 未达阈值 → None
- 测试：覆盖 4 档 + 3 种 bet_type

### T4 · engine/service.py ScoringService
- `ScoringService(db).compute_for_match(match_id, model_config_id) -> MatchScore`
  - 读 Match / MatchOdds（按 source 优先 sporttery 否则 titan007）/ MatchTeamStats / ModelConfig
  - 算 6 维 → total → kelly → bet_type → is_recommended（按 thresholds_json）
  - upsert `match_scores`（`(match_id, model_config_id)` 唯一，`user_id=NULL`）
- `compute_for_date(date, model_config_id) -> list[MatchScore]`：批量
- 缺数据（无赔率 / 无 team_stats）时返回 partial 并记录日志
- 测试：全量成功、部分缺失、重复调用幂等

### T5 · schemas/scores.py + api/scores.py
- Pydantic：`ScoreOut`（含各维度分、total、kelly、bet_type、is_recommended、notes、bet_amount、actual_hit）、`ScoreBreakdown`（详情：每维分 + 计算解释）、`ScoreUpdate`（notes/bet_amount/actual_hit）、`ScoreListResponse`
- 路由（全部 member+admin 可读，覆盖 admin 专属）：
  - `GET  /api/scores/today?model_config_id=`
  - `GET  /api/scores/by-date?date=&model_config_id=`
  - `POST /api/scores/compute?date=&model_config_id=`（admin）
  - `GET  /api/scores/{score_id}/breakdown`（含每维解释）
  - `PUT  /api/scores/{score_id}`（notes/bet_amount/actual_hit；member 可更新自己的？MVP 允许 admin + member 都能编辑同一条，P6 再做 RBAC 拆分）
- 测试：6-8 个用例

### T6 · Scheduler scoring job
- `run_scoring_job(session_factory, *, model_config_id=None)`：默认使用最小 id 的 ModelConfig
- 注册到 JOB_REGISTRY，默认 cron `hour=9, minute=15`
- 测试：mock ScoringService，确认调用 + session 生命周期
- 顺带更新 `DEFAULT_CRONS`、`/api/scrape/jobs` 描述

### T7 · 前端 `/dashboard` — 列表 + 详情 + 编辑
- `lib/scores/types.ts`、`lib/scores/api.ts`（getToday / getBreakdown / updateScore / compute）
- `DashboardClient`：表格列 `比赛 / 欧赔 / 盘口 / 评分 / Kelly / 推荐`，点击行打开 `ScoreDetail` 抽屉/弹窗
- `ScoreDetail`：展示 6 维分 + 解释文本 + `ScoreEdit` 表单（notes / bet_amount / actual_hit）
- 未登录由 middleware 重定向（已有）
- 前端测试：api、dashboard（列表 + 触发 compute）、detail（显示分项 + 编辑）

### T8 · CI + 合并
- `backend`：alembic 0003 迁移 roundtrip + 新增 pytest
- `frontend`：新增 vitest + `pnpm build`
- `git merge --no-ff feat/p5-scoring`

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| 评分函数与手册精准度偏差 | 每函数先在 `engine/scoring.py` 顶部用 docstring 钉死规则；回测 P6 再调 |
| 缺赔率/状态导致评分残缺 | ScoringService 返回 `partial`，前端展示"数据不全"占位 |
| 前端 dashboard 体量较大 | 分 3 子组件，每个独立测试；MVP 不做分页/排序 |
