# Sporttery 10x · 产品需求文档（PRD）

**版本**：V1.1 · 2026-04-27
**适用范围**：当前主干 P1-P7 全部交付 + P8 H1 技术债清理已落地
**来源资料**：`平让平竞彩交易模型手册.md`、`docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`、`docs/superpowers/plans/*`

---

## 1. 产品定位

### 1.1 一句话

面向体彩足球「平局 / 让平」玩法的个人量化交易决策系统 —— 把手册里的 6 维评分 + Kelly 资金管理 + 回测 流程，固化为「抓取 → 推荐 → 下注 → 复盘」的 Web 闭环。

### 1.2 产品价值

| 核心痛点 | 解决方案 |
| --- | --- |
| 手工算评分低效易错 | 6 维评分由后端自动算，前端一屏展示 |
| 拍脑袋下注缺纪律 | Kelly 分带 + 达标阈值硬约束 |
| 无法快速验证新权重 | 任意日期段回测 + 双模型并排对比 |
| 赔率数据分散 | 定时抓体彩官网 + titan007 入库 |
| 没有赛后复盘闭环 | `/review` + Dashboard「已结束」Tab 回写命中 / 金额 / 备注（P7 已上线） |
| 模型配置只能改 SQL | `/model` 克隆 / 调权重 / 激活；激活后同步重算当日（P7+P8 H1） |

### 1.3 目标用户

- **主用户（member）**：遵循系统的个人玩家，只做每日查看推荐 + 下注 + 回填结果
- **管理员（admin）**：系统维护者 / 模型调参者，能管理用户、抓取任务、模型配置、审阅全部回测记录

---

## 2. 业务流程

```
┌──────────┐  每日 08:30   ┌───────────┐  09:15    ┌──────────┐
│ Scheduler│ ─ 抓赛程 ───→ │  MySQL    │ ─ 评分 ──→│ Dashboard│
│APScheduler│  08:30+      │           │           │ 今日推荐 │
│          │   每 2h 抓赔率 │           │           └─────┬────┘
│          │   09:00 抓状态│           │                 │ 用户按推荐下注
│          │   23:30 抓赛果│           │                 ▼
└──────────┘               │           │         ┌────────────┐
                           │           │ ←─回填──│  复盘(P7)  │
                           └─────┬─────┘         └────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  /backtest    │ 任选时段复算，对比多模型
                         └───────────────┘
```

---

## 3. 功能需求（Feature Matrix）

| 模块 | 子功能 | 状态 | 阶段 | 负责接口 / 页面 |
| --- | --- | --- | --- | --- |
| **用户鉴权** | 手机号 + 密码登录 | ✅ | P3 | `POST /api/auth/login` / `/login` |
|  | JWT 校验 + `/me` | ✅ | P3 | `GET /api/auth/me` |
|  | admin 管理用户 CRUD | ✅ | P3 | `/api/users/*`（admin-only） |
| **数据抓取** | 体彩赛程 / 赛果 | ✅ | P4 | `app.scrapers.sporttery` |
|  | titan007 赔率 | ✅ | P4 | `app.scrapers.titan007` |
|  | 体彩球队状态 | ✅ | P4 | `app.scrapers.sporttery.team_stats` |
|  | 定时调度（APScheduler） | ✅ | P4 | `app.scheduler.main` |
|  | 管理员面板 + 手动触发 | ✅ | P4 | `/api/scrape/*`、`/admin/scrape` |
| **评分引擎** | 6 维评分 + 总分 | ✅ | P5 | `app.engine.scoring` |
|  | 竞赛类型推断 | ✅ | P5 | `infer_competition_type` |
|  | Kelly 分带 | ✅ | P5 | `app.engine.kelly` |
|  | 推荐 bet_type（平/让平） | ✅ | P5 | `suggest_bet_type` |
|  | 定时批量打分 job | ✅ | P5 | `run_scoring_job` |
| **Dashboard** | 今日推荐 + 已结束 Tab | ✅ | P5 | `/api/scores/today` / `/dashboard` |
|  | 评分明细抽屉 | ✅ | P5 | `/api/scores/{id}/breakdown` |
|  | 手动重算单场 | ✅ | P5 | `PUT /api/scores/{id}` |
| **回测** | 同步执行 + 持久化 | ✅ | P6 | `POST /api/backtest` |
|  | 双口径 P/L（固定 + Kelly） | ✅ | P6 | `app.engine.backtest.simulate_bet` |
|  | 分数段 / 联赛分布 | ✅ | P6 | `BacktestStats.by_score_band` |
|  | 双模型并排对比 | ✅ | P6 | `GET /api/backtest/compare` |
|  | 历史列表 / 详情 | ✅ | P6 | `GET /api/backtest[/{id}]` |
|  | 按 owner 过滤（admin 全量） | ✅ | P6 hotfix I1 | `_visibility_filter` |
| **模型配置 UI** | 可视化调权重/阈值/Kelly | ✅ | P7 | `/model`、`/api/model-configs` |
|  | 多版本克隆 / 激活 | ✅ | P7 | `services/model_config.py` |
|  | `name` 唯一约束 + 激活同步重算今日 | ✅ | P8 H1 | `TD-2` / `TD-6` |
| **复盘** | `actual_hit` / `bet_amount` / `notes` 回填 | ✅ | P7 | `/review`、Dashboard「已结束」Tab、`PATCH /api/reviews/{score_id}` |
|  | PATCH 乐观锁（`expected_updated_at` → 409） | ✅ | P8 H1 | `TD-1` |
| **其他** | 历史赔率快照 | 💤 | P8+ | `match_odds_history` |
|  | 回测扣佣金 / 比赛取消状态 / `/admin/users` | 💤 | P8+ H2 | 登记于 `plans/2026-04-27-p8-tech-debt.md` |
|  | 短信验证码登录 | 💤 | P9+ | - |
|  | 微信/钉钉推送 | 💤 | P9+ | - |

图例：✅ 已上线 / 🕐 规划中 / 💤 延后

---

## 4. 非功能需求

### 4.1 性能

| 指标 | 目标 | 实际 |
| --- | --- | --- |
| API p95 响应 | ≤ 500ms（非回测类） | 依赖 MySQL 索引 |
| 每日评分 job | ≤ 30s 完成（500 场以内） | 单线程串行，已满足 |
| 回测 30 天 | ≤ 10s | 实测 SQLite 约 5s，MySQL 约 3s |
| 数据抓取失败重试 | 同 job 重入幂等 | ScrapeLog 唯一约束 + upsert |

### 4.2 可靠性

- 所有抓取任务写 `scrape_logs`，失败不影响其他 job
- 回测 / 评分引擎不在写入路径产生副作用（P6 hotfix I5 明确把回测打分改为只读 + dry-run）
- 评分命中口径延迟计算：依赖 `MatchResult`（可能次日回填）

### 4.3 安全

- 全站 JWT 鉴权，密码 bcrypt 哈希（成本因子 ≥ 12）
- admin 与 member 角色分离：抓取、模型、用户管理均 `admin`-only
- 回测/下注数据按 `user_id` 隔离，admin 可穿透（I1 实现）
- CORS / Cookie 全部不依赖浏览器同源假设，Bearer token only

### 4.4 数据规模（单用户场景）

| 表 | 年增量估算 | 索引 |
| --- | --- | --- |
| `matches` | ~ 4 000 场 | `(match_date)`、`(sporttery_match_id)` |
| `match_odds` | ~ 20 000 行（5 source×场） | `(match_id, source)` |
| `match_scores` | ~ 4 000 行 × N 模型 | `(match_id, model_config_id)` UNIQUE |
| `backtest_sessions` | < 500 条/用户 | `(user_id, created_at)` |
| `scrape_logs` | ~ 5 000 行 | `(source, status, created_at)` |

---

## 5. 数据字典（简版）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `users` | `phone`, `role`, `password_hash` | 手机号唯一，role = admin/member |
| `leagues` | `name`, `draw_rate_tier` | 平局率等级 H/M/L，影响战意分 |
| `matches` | `sporttery_match_id`, `match_date`, `competition_type`, `round` | 竞赛类型可人工改写 |
| `match_odds` | `win/draw/lose_odds`, `asian_handicap`, `total_goals` | 多源并存，评分默认取体彩 |
| `match_results` | `result`, `handicap_result` | 赛果 + 让球结果 |
| `match_team_stats` | `home/away_recent_form`, 排名, 主客场战绩 | 球队状态源 |
| `model_configs` | `weights_json`, `thresholds_json`, `kelly_bands_json` | P5 校准默认值见 `scripts/seed.py` |
| `match_scores` | `euro/asian/...`, `total_score`, `bet_type`, `kelly_pct`, `is_recommended`, `actual_hit`, `bet_amount`, `notes` | 推荐 + 复盘合一 |
| `backtest_sessions` | `mode`(fixed/kelly/both), `initial_capital`, `equity_curve`, `kelly_*` | 详见 P6 计划 |
| `scrape_logs` | `source`, `status`(running/success/failed/partial), `records` | 管理员面板读 |

完整 DDL 见 `backend/alembic/versions/0001_initial_schema.py` + `0002..0006`。当前 head 为 `0006_model_config_active_parent`（`ModelConfig` 加 `is_active` + `parent_id`）。

---

## 6. 评分规则（V1 落地版）

| 维度 | 满分 | 触发函数 | 输入 |
| --- | --- | --- | --- |
| 欧赔结构 | 25 | `euro_score(win, draw, lose)` | 三项赔率离散度 + 平赔甜区 |
| 亚盘 | 20 | `asian_score(handicap)` | 平手/平半/半球/半球以上 |
| 大小球 | 20 | `goals_score(total)` | ≤2.25 / 2.5 / ≥2.75 |
| 战意/赛制 | 15 | `intent_score(ctype, round)` | 联赛/杯赛/淘汰赛 |
| 平赔压缩度 | 20 | `compression_score(draw)` | ≤3.2 / 3.2-3.5 / ≥3.6 |
| 球队状态 | 20 | `team_stats_score(stats)` | 排名接近度 + 近期 form |
| **合计** | **120** | `total_score(parts, weights)` | 加权求和后四舍五入 |

**推荐规则**（见 `suggest_bet_type`）：

- `total_score ≥ draw_min_score` 且亚盘 ∈ {平手,平半}：推荐「平 (draw)」，取 `draw_odds`
- `total_score ≥ handicap_draw_min_score` 且赔率支持让平：推荐「让平 (handicap_draw)」，取 `draw_handicap_odds`
- 否则不推荐（`is_recommended=false`）

默认阈值：`recommend=84` / `draw_min=84` / `handicap_draw_min=78`（可由 ModelConfig 覆盖）。

**Kelly 分带**（默认 `kelly_bands_json`）：

```json
[
  {"min": 96, "max": 120, "pct": 0.02},
  {"min": 84, "max": 96,  "pct": 0.015},
  {"min": 78, "max": 84,  "pct": 0.01}
]
```

---

## 7. 关键用户故事

### US-1 · Member 查看今日推荐

> 作为 member，打开 Dashboard，我希望一屏看到今日所有被推荐的比赛（平 / 让平），并按总分降序排列，点击单场可看 6 维明细和 Kelly 比例。

- 入口：`/dashboard`
- 验收：至少显示 total_score / bet_type / kelly_pct / 赔率；允许按日期切换

### US-2 · Admin 手动触发抓取

> 作为 admin，当发现定时任务失败，我希望在 `/admin/scrape` 一键重跑某个 job，并看到实时日志。

- 入口：`/admin/scrape` → 点击 job 卡片
- 验收：返回 `ScrapeRunResult`，`scrape_logs` 新增 running→success/failed 行

### US-3 · Admin 评估新权重

> 作为 admin，调整权重后（P7 UI 或手动 seed），我希望选 2026-04-01..04-30 回测一次，再选旧版本回测一次，并排对比命中率和 equity_curve。

- 入口：`/backtest` → 发起新回测 → 切对比模式 → 选择另一条
- 验收：`hit_rate / roi_fixed / roi_kelly / by_score_band` 双侧同屏

### US-4 · Admin 复盘（P7 + P8 H1）

> 作为 admin，赛后我想标记某场是否实际命中、填入下注金额和心得；同时防止两个管理员同时改一条导致互相覆盖。

- 入口：`/review` 或 Dashboard「已结束」Tab
- 验收：`PATCH /api/reviews/{score_id}` 成功后记录 `actual_hit/bet_amount/notes`
- 乐观锁：请求携带 `expected_updated_at`；服务器侧时间戳已推进则返回 409，前端显示提示并自动刷新（TD-1）

### US-5 · Admin 激活新模型

> 作为 admin，在 `/model` 克隆并调整权重，点「激活」后希望 Dashboard 当日立即换算。

- 入口：`/model` → 选中候选版本 → 点「激活」
- 验收：响应体 `scores_recomputed` > 0；前端 toast「已激活 v2，同步重算今日评分 N 条」（TD-6）

---

## 8. 接口概览

| 分类 | 方法 | 路径 | 权限 |
| --- | --- | --- | --- |
| 认证 | POST | `/api/auth/login` | 公开 |
|  | GET | `/api/auth/me` | 登录 |
|  | POST | `/api/auth/logout` | 登录 |
| 用户 | GET/POST/PATCH/DELETE | `/api/users/*` | admin |
|  | POST | `/api/users/{id}/password` | admin |
| 抓取 | GET | `/api/scrape/jobs` | admin |
|  | GET | `/api/scrape/logs` | admin |
|  | POST | `/api/scrape/jobs/{name}/run` | admin |
| 评分 | GET | `/api/scores/today` | 登录 |
|  | GET | `/api/scores/by-date` | 登录 |
|  | POST | `/api/scores/compute` | admin |
|  | GET | `/api/scores/{id}/breakdown` | 登录 |
|  | PUT | `/api/scores/{id}` | admin |
| 回测 | POST | `/api/backtest` | 登录 |
|  | GET | `/api/backtest` | 登录（按 owner 过滤） |
|  | GET | `/api/backtest/compare` | 登录 |
|  | GET | `/api/backtest/{id}` | 登录 |
| 模型 | GET | `/api/model-configs` / `/api/model-configs/active` / `/api/model-configs/{id}` | 登录 |
|  | POST | `/api/model-configs` / `/{id}/clone` / `/{id}/activate` | admin |
|  | PATCH | `/api/model-configs/{id}` | admin |
| 复盘 | GET | `/api/reviews` / `/api/reviews/{score_id}` | 登录 |
|  | PATCH | `/api/reviews/{score_id}`（可选 `expected_updated_at`） | admin |
| 健康 | GET | `/health` | 公开 |

---

## 9. 验收标准（已上线部分）

- [x] `make install && make dev` 能拉起 4 个容器并通过 healthcheck
- [x] 新用户通过 `python -m app.cli.create_admin` 创建 → 登录 → 访问 Dashboard
- [x] 赛程/赛果/赔率/球队状态 四个 job 按 cron 执行并写 `scrape_logs`
- [x] 全量测试：backend 251 / frontend 58 全绿，lint 全绿（含 P8 H1 +4 用例）
- [x] 回测：3 mode 均可选，equity_curve 入库且前端 Recharts 渲染
- [x] 回测可见范围按 owner 隔离，admin 全量可见
- [x] `ScoringService.compute_for_match(dry_run=True)` 保证回测不污染 `match_scores`
- [x] `/model` 可视化克隆 / 调权重 / 阈值 / Kelly 带 / 激活；同名返回 400
- [x] `/review` + Dashboard「已结束」Tab 可回写 `actual_hit/bet_amount/notes`；并发改返回 409
- [x] 激活新版本同步触发当日重算并回显 `scores_recomputed`

---

## 10. 关联文档

- 需求原始手册：`平让平竞彩交易模型手册.md`
- 架构设计：`docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`（V1.0；V1.1 增量已汇总进本 PRD 与 `docs/specs/DESIGN_REVIEW_2026-04-21.md` §10）
- 决策纪要：`docs/superpowers/brainstorm/2026-04-21-decisions.md`
- 分阶段实施计划：`docs/superpowers/plans/2026-04-21-p1..p7-*.md`
- 技术债清理：`docs/superpowers/plans/2026-04-27-p8-tech-debt.md`
- 部署：`docs/deployment/DEPLOYMENT.md`
- 使用：`docs/usage/USAGE.md`
- 模型配置运营手册：`docs/superpowers/guides/model-config-workflow.md`
- 设计 vs 实现差异（2026-04-21 快照）：`docs/specs/DESIGN_REVIEW_2026-04-21.md`
