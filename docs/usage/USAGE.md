# Sporttery 10x · 使用手册

**版本**：2026-04-27（P7 + P8 H1 已上线）
**面向读者**：member（普通玩家）、admin（管理员）
**当前已上线**：登录、Dashboard（含「已结束」Tab）、回测、抓取面板、**模型配置 UI（`/model`）、复盘 UI（`/review`）**。

> **配套阅读**：本手册讲"按钮怎么点"；运营节奏、下注纪律、调参节律请读 [`MVP_OPERATIONS.md`](./MVP_OPERATIONS.md)。

---

## 目录

- [1. 快速上手（3 分钟）](#1-快速上手3-分钟)
- [2. 登录与账号](#2-登录与账号)
- [3. Dashboard：今日推荐](#3-dashboard今日推荐)
- [4. 回测：历史复算与对比](#4-回测历史复算与对比)
- [5. 抓取管理（admin）](#5-抓取管理admin)
- [6. 模型配置（`/model` UI）](#6-模型配置model-ui)
- [7. 复盘（`/review` + Dashboard 已结束 Tab）](#7-复盘review--dashboard-已结束-tab)
- [8. 推荐规则速查](#8-推荐规则速查)
- [9. FAQ](#9-faq)
- [10. API 速查表](#10-api-速查表)

---

## 1. 快速上手（3 分钟）

前置：运维已按 `docs/deployment/DEPLOYMENT.md` 跑起系统，且给你一个手机号 / 密码。

1. 浏览器打开 <http://localhost:3000>
2. 输入手机号（`^1[3-9]\d{9}$`） + 密码，点击「登录」
3. 自动跳转到 `/dashboard`：看见按总分排序的今日比赛
4. 点击单行 → 右侧抽屉显示 6 维评分 + 明细
5. 想复算历史：顶部导航点「回测」→ 选日期段 → 看图表

---

## 2. 登录与账号

### 2.1 登录

- 入口：`/login`
- 字段：手机号、密码
- 成功后保存 JWT 到 `localStorage.access_token`，后续请求自动带 `Authorization: Bearer ...`
- token 默认 30 天（`JWT_EXPIRE_MINUTES=43200`）

### 2.2 密码 / 资料修改

P3 已实现后端，但前端未暴露「我的」页面。admin 可代为修改：

```bash
curl -X POST http://localhost:8000/api/users/{id}/password \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"NewPass@2026"}'
```

### 2.3 创建新 member（admin 操作）

```bash
curl -X POST http://localhost:8000/api/users/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone":"13900000001","name":"张三","role":"member","password":"Abcd1234"}'
```

或用 CLI（只创建 admin）：

```bash
docker compose exec -it backend python -m app.cli.create_admin --phone 13800000002 --name ops
```

---

## 3. Dashboard：今日推荐

### 3.1 页面布局（`/dashboard`）

```
┌──────────────────────────────────────────────────────────────┐
│ 日期：[2026-04-22 ▼]     仅推荐 ☑   [重新计算]               │
├──────────────────────────────────────────────────────────────┤
│  ★ 总分 │ 联赛 │ 对阵         │ 比分   │ Bet  │ Kelly │ ...  │
│   102  │ 西甲│ 皇马 vs 巴萨  │ -      │ draw │ 2.0%  │ 👁   │
│   95   │ 英超│ …             │ -      │ h-drw│ 1.5%  │ 👁   │
│   …    │ …   │ …             │        │      │       │      │
└──────────────────────────────────────────────────────────────┘
```

- **默认列表**：`GET /api/scores/today`，即当日所有比赛
- **筛选**：顶部日期选择调用 `GET /api/scores/by-date?d=YYYY-MM-DD`；勾选「仅推荐」前端过滤 `is_recommended=true`
- **排序**：总分降序

### 3.2 点击某一行 → 明细抽屉

- 数据源 `GET /api/scores/{id}/breakdown`
- 展示 6 维分数 + 每项解释 + 输入的赔率 / 亚盘 / 大小球
- 解释文本在 `backend/app/api/scores.py:_DIMENSION_EXPLANATIONS`

### 3.3 手动重新计算（admin）

- 按钮「重新计算」触发 `POST /api/scores/compute?date=YYYY-MM-DD&model_config_id=1`
- 通常用于：临时抓完赔率、没等 09:15 定时 job

### 3.4 修改单场评分（admin）

member 只能看；admin 可通过 `PUT /api/scores/{id}` 覆写 `bet_type / kelly_pct / is_recommended / notes`，用于人工干预明显错判的场次。

---

## 4. 回测：历史复算与对比

### 4.1 入口：`/backtest`

```
┌─── 新建回测 ─────────────────────────────────────────┐
│ 起止日期：[2026-04-01]─[2026-04-30]  最长 90 天     │
│ 初始本金：[10000]                                    │
│ 模式：( ) fixed  ( ) kelly  ( * ) both              │
│ 模型配置：[#1 default ▼]                             │
│                                       [开始回测]    │
└──────────────────────────────────────────────────────┘

┌─── 历史回测列表 ────────────────────────────────────┐
│ #7 · 2026-04-01→04-30 · both · 命中 14/30          │
│ #6 · 2026-04-01→04-15 · fixed · …                  │
└──────────────────────────────────────────────────────┘

┌─── 回测概览（点击历史行）───────────────────────────┐
│ 命中率 46.7%   ROI 固定 +24%   ROI Kelly +7.1%     │
│ [折线图：累计盈亏 fixed/kelly]                       │
│ [饼图：分数段分布]                                    │
└──────────────────────────────────────────────────────┘
```

### 4.2 工作流程

1. 选起止日期（系统限制 ≤ 90 天），填初始本金，选模式
2. 默认模型 = 列表第一个（ID 升序，通常是 `default`）；P7 上线后会显示多版本下拉
3. 点「开始回测」→ 同步执行（单用户 30 天 ≈ 3-8 秒）
4. 成功后新 session 会 push 到顶部「历史」列表，自动选中并渲染图表

### 4.3 模式含义（重要）

| 模式 | `profit_loss` | `kelly_profit_loss` | 说明 |
| --- | --- | --- | --- |
| `fixed` | 有效 | 0 | 每场 1 单位，命中+odds-1、未命中 -1 |
| `kelly` | 0 | 有效 | 按 `kelly_pct * 当前本金` 滚动下注 |
| `both` | 有效 | 有效 | 同时算两份，适合同屏对比 |

> **Kelly 破产保护**：`simulate_bet` 在 `current_capital ≤ 0` 时 Kelly 端自动停注（P6 热修 I4）。

### 4.4 双模型并排对比

1. 先点击一条历史行，选中它
2. 点击「对比模式：关」→ 变为「开」
3. 再点击另一条历史行 → 触发 `GET /api/backtest/compare?a=X&b=Y`
4. 页面变为左右两列，同时渲染两份摘要 / 折线图 / 饼图

**注意**：只读 admin 能看他人的回测；member 只能对比自己的（P6 热修 I1）。

### 4.5 可见性

- 普通 member：`GET /api/backtest` 只返回本人创建的；访问他人 ID 返回 403
- admin：穿透所有

### 4.6 结果字段解读

```jsonc
{
  "id": 7,
  "total_bets": 30,
  "hit_count": 14,
  "hit_rate": 0.4667,
  "roi": 0.24,                  // 固定单位 ROI
  "profit_loss": 7.2,
  "kelly_profit_loss": 712.5,
  "kelly_roi": 0.0713,
  "mode": "both",
  "initial_capital": 10000,
  "results_by_score": {          // 每个分数段汇总
    "84-100":  { "bets": 20, "hits": 9, "hit_rate": 0.45, "roi_fixed": 0.28, ... },
    "100-120": { "bets": 10, "hits": 5, "hit_rate": 0.5,  ... }
  },
  "results_by_league":  { "西甲": {...}, "英超": {...} },
  "equity_curve": [
    { "date": "2026-04-01", "cumulative_pnl_fixed": 2.2, "cumulative_pnl_kelly": 440.0 },
    ...
  ]
}
```

---

## 5. 抓取管理（admin）

### 5.1 面板 `/admin/scrape`

- 上半屏：5 张 Job 卡片（schedule / result / odds / team_stats / scoring）
  - 每张展示：名称 / 下一次 cron 时间 / 最近一次状态
  - 按钮「立即运行」→ `POST /api/scrape/jobs/{name}/run`
- 下半屏：抓取日志表（默认倒序 50 条）
  - 可过滤 `source` / `status`

### 5.2 手动补数（CLI）

抓某天赛程：

```bash
docker compose exec backend python -c "
from app.core.database import SessionLocal
from app.scheduler.jobs import run_schedule_job
with SessionLocal() as db:
    r = run_schedule_job(lambda: db)
    print(r)
"
```

也可以直接 `POST /api/scrape/jobs/schedule/run`（走管理员 token），效果等价。

### 5.3 典型日常

- **开盘前（~08:35）**：打开面板看 `schedule` 是否 success；失败则手动重跑
- **09:00**：`team_stats` 执行，默认通过 Titan007 analysis 页面补赛前球队状态
- **09:15**：`scoring` 执行，完成后 Dashboard 会显示今日推荐
- **赛后（23:40）**：看 `result` 状态；次日再看有无缺漏赛果（延迟回填是常态）

### 5.4 失败处理

- 抓取类 job 失败记 `scrape_logs.status='failed'`，message 里有 URL 和 HTTP 码
- 常见：titan007 反爬导致 403。等一会儿重试；长期失败需调整爬虫 headers
- 抓失败不会阻塞评分 job，但评分会因数据残缺跳过相应比赛

---

## 6. 模型配置（`/model` UI）

> 前置：admin 角色。详细操作手册见 `docs/superpowers/guides/model-config-workflow.md`。

### 6.1 页面一览

- 顶部导航「模型」→ 左侧版本列表（显示 name / `is_active` badge / `parent_id`）
- 右侧详情：6 维权重、阈值、Kelly 分带；表单实时校验（权重总分、阈值单调性、Kelly 带无重叠）
- 底部按钮：**保存** / **克隆** / **激活**

### 6.2 典型闭环：调参 → 回测 → 激活

1. 选中当前激活版本 → 点「克隆」→ 输入新 name（例：`v2026-04-27-euro-up`；**重名返回 400**，P8 H1 TD-2）
2. 在克隆版本上调权重 / 阈值 / Kelly 带，点「保存」→ `PATCH /api/model-configs/{id}`
3. 切到 `/backtest`，选择新版与旧版做 **双模型并排对比**，观察 ROI / 命中率 / Sharpe
4. 指标满意后，回 `/model` 在新版本点「激活」
   - 后端事务：全表先 `is_active=false` → 指定行 `is_active=true`
   - **同步重算当日评分**（P8 H1 TD-6），响应体 `scores_recomputed: N`
   - 前端 toast「已激活 <name>，同步重算今日评分 N 条」
5. Dashboard 立即读新版本（`/api/scores/today` 默认取 active）；不满意可在旧版本再点「激活」回滚

### 6.3 阈值与 Kelly 分带说明

`thresholds_json` 默认：

```json
{"recommend_total_score": 84, "draw_min_score": 84, "handicap_draw_min_score": 78}
```

`kelly_bands_json` 默认（引擎用 `min ≤ score < max` 命中）：

```json
[
  {"min": 96,  "max": 120, "pct": 0.02},
  {"min": 84,  "max": 96,  "pct": 0.015},
  {"min": 78,  "max": 84,  "pct": 0.01}
]
```

> 权重归一化约定：UI 里填的数字以「每维满分盖」为基准（`euro=25 / asian=20 / ...`）；填 25 表示欧赔权重满档，填 12.5 表示半档。

---

## 7. 复盘（`/review` + Dashboard 已结束 Tab）

### 7.1 入口

- **轻量**：`/dashboard` → 切换「已结束」Tab（近 14 天，快速录入）
- **批量**：顶部导航「复盘」→ `/review`（支持多维过滤 + 汇总条）

### 7.2 字段规则

| 字段 | 可选值 | 说明 |
| --- | --- | --- |
| `actual_hit` | 命中 / 未中 / 待定 | 下拉 select，离开即 PATCH |
| `bet_amount` | ≥ 0 的 Decimal(10,2) | 负数直接 422 |
| `notes` | 纯文本 | 数据库 TEXT |
| `suggested_actual_hit` | 只读 | 基于 `bet_type` + `match_results.result/handicap_result` 系统建议 |

### 7.3 权限与乐观锁

- 读：所有登录用户
- 写：**仅 admin**；member 下拉/输入 disabled
- **乐观锁**（P8 H1 TD-1）：前端每次 PATCH 带上当前行的 `updated_at` 作为 `expected_updated_at`；若服务端已推进，返回 409，页面显示「该行已被其他管理员更新」并自动刷新

### 7.4 `/review` 汇总条

底部实时显示当前过滤范围内：

- 已复盘数 / 命中数 / 命中率
- Σ 投注金额 / Σ 净盈亏（= Σ(hit ? bet_amount : -bet_amount)）

### 7.5 SQL 旁路（仅作应急对账）

```sql
SELECT m.match_date, m.home_team, m.away_team,
       ms.total_score, ms.bet_type, ms.kelly_pct,
       mr.result, mr.handicap_result,
       ms.actual_hit, ms.bet_amount, ms.notes
FROM match_scores ms
JOIN matches m       ON m.id = ms.match_id
LEFT JOIN match_results mr ON mr.match_id = m.id
WHERE ms.is_recommended = 1
  AND m.match_date BETWEEN '2026-04-01' AND '2026-04-30'
ORDER BY m.match_date;
```

---

## 8. 推荐规则速查

### 8.1 6 维评分（满分 120）

| 维度 | 满分 | 高分触发 |
| --- | --- | --- |
| 欧赔结构 | 25 | 胜/负 2.30-2.80，平 3.00-3.40，三项均衡 |
| 亚盘 | 20 | 平手 20 / 平半 15 / 半球 5 / 半球以上 0 |
| 大小球 | 20 | 总进球 ≤ 2.25（防守对决偏好平） |
| 战意/赛制 | 15 | 淘汰赛首/次回合、关键场次 |
| 平赔压缩度 | 20 | 平赔 ≤ 3.2 |
| 球队状态 | 20 | 排名接近、近 5 场均衡、历史交锋平局多 |

### 8.2 阈值

- **平 (draw)**：总分 ≥ 84 且亚盘 ∈ {平手, 平半}
- **让平 (handicap_draw)**：总分 ≥ 78 且让平赔率合理
- 两条都不满足 → 不推荐

### 8.3 Kelly 分带（半 Kelly）

| 总分 | 下注比例 |
| --- | --- |
| ≥ 96 | 2.0% 本金 |
| 84 - 96 | 1.5% 本金 |
| 78 - 84 | 1.0% 本金 |
| < 78 | 0（不下注） |

### 8.4 示例

| 比赛 | 总分 | Bet | Odds | 建议单数（1 万本金） |
| --- | --- | --- | --- | --- |
| 皇马 vs 巴萨 | 102 | draw | 3.2 | 200 元（2%） |
| 切尔西 vs 阿森纳 | 88 | handicap_draw | 3.6 | 150 元（1.5%） |
| 狼队 vs 利物浦 | 80 | handicap_draw | 3.8 | 100 元（1%） |

---

## 9. FAQ

**Q1 · Dashboard 空白，今天没推荐？**
先看 `/admin/scrape`：`schedule`、`odds`、`team_stats` 是否成功。`team_stats` 当前使用 Titan007 analysis；若缺失，评分会少球队状态维度。

**Q2 · 为什么我回测命中率 0？**
很可能还在用老的 `weights_json={1.0}`。跑一次 `alembic upgrade head`（0005 迁移会自动修） 或直接改 default 权重到 §8 默认值。

**Q3 · 回测为什么修改了 Dashboard 的推荐？**
不会。P6 热修 I5 之后，回测走的是 `dry_run=True`，永不写入 `match_scores`。

**Q4 · Kelly 出现负本金？**
P6 热修 I4 加了保护：`current_capital ≤ 0` 时 Kelly 停注。此时 `kelly_profit_loss` 会冻结；固定单位口径不受影响。

**Q5 · 改了 ModelConfig 后，今日推荐没变？**
手动触发重算：`POST /api/scores/compute?date=今天&model_config_id=...`，或等次日 09:15。

**Q6 · 让球盘看不到 handicap_draw 推荐？**
让平推荐需要 `asian_handicap ∈ {"平手半", "半球"}` 且 `draw_handicap_odds` 存在。查 `match_odds` 表对应字段是否为空。

**Q7 · member 能修改评分吗？**
不能。`PUT /api/scores/{id}` 与 `PATCH /api/reviews/{score_id}` 均为 admin-only；member 只读。复盘数据由 admin 统一维护，member 可在 `/review` / Dashboard 已结束 Tab 查看。

**Q8 · 最大回测区间是多少？**
90 天。超过会 400。大范围可拆成多段再拼。

**Q9 · 如何退出登录？**
前端清 `localStorage.access_token` 或调 `POST /api/auth/logout`（后端目前是 204，token 失效靠过期）。

**Q10 · 评分明细里 `intent_score=0` 什么意思？**
手册把非关键联赛记 0 分。提升方法：修改 `ModelConfig.weights.intent` 或在 `matches.competition_type` 字段手改为「淘汰赛次回合」等。

---

## 10. API 速查表

| 操作 | 方法 + 路径 | 权限 |
| --- | --- | --- |
| 登录 | `POST /api/auth/login` | 公开 |
| 当前用户 | `GET /api/auth/me` | 登录 |
| 退出 | `POST /api/auth/logout` | 登录 |
| 用户 CRUD | `/api/users/*` | admin |
| 今日评分 | `GET /api/scores/today` | 登录 |
| 按日评分 | `GET /api/scores/by-date?d=` | 登录 |
| 手动评分 | `POST /api/scores/compute?date=&model_config_id=` | admin |
| 评分明细 | `GET /api/scores/{id}/breakdown` | 登录 |
| 覆写评分 | `PUT /api/scores/{id}` | admin |
| 抓取 Job 列表 | `GET /api/scrape/jobs` | admin |
| 抓取日志 | `GET /api/scrape/logs?source=&status=` | admin |
| 手动运行 | `POST /api/scrape/jobs/{name}/run` | admin |
| 创建回测 | `POST /api/backtest` | 登录 |
| 回测列表 | `GET /api/backtest?limit=&offset=` | 登录（按 owner） |
| 回测详情 | `GET /api/backtest/{id}` | 登录（本人 + admin） |
| 回测对比 | `GET /api/backtest/compare?a=&b=` | 登录（双方可见性校验） |
| 模型列表 | `GET /api/model-configs` | 登录 |
| 当前激活 | `GET /api/model-configs/active` | 登录 |
| 模型详情 | `GET /api/model-configs/{id}` | 登录 |
| 编辑模型 | `PATCH /api/model-configs/{id}` | admin |
| 克隆模型 | `POST /api/model-configs/{id}/clone` | admin |
| 激活模型（同步重算当日） | `POST /api/model-configs/{id}/activate` | admin |
| 复盘列表 | `GET /api/reviews?date_from=&date_to=&league=&hit_status=` | 登录 |
| 复盘详情 | `GET /api/reviews/{score_id}` | 登录 |
| 复盘回写（带乐观锁） | `PATCH /api/reviews/{score_id}` | admin |
| 健康 | `GET /health` | 公开 |

> 在线自动生成的 OpenAPI 文档：<http://localhost:8000/docs>（Swagger UI）、<http://localhost:8000/redoc>。

---

## 附录 · 示例脚本：每天早上 9:20 本地拉推荐到 CSV

```bash
#!/usr/bin/env bash
set -euo pipefail
TOKEN=$(curl -sX POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800000000","password":"Admin@1234"}' | jq -r .token)

curl -sH "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/scores/today" \
  | jq -r '.items[] | select(.is_recommended) |
    [.match_date, .home_team, .away_team, .total_score, .bet_type, .kelly_pct] | @csv' \
  > ~/sporttery_$(date +%Y%m%d).csv
```
