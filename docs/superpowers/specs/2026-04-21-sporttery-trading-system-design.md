# 平/让平竞彩交易决策系统 设计文档

**日期**：2026-04-21（V1.0 原稿）· 2026-04-27（V1.1）· 2026-04-23（V1.2 爬虫重构）
**版本**：V1.0 + V1.1 + V1.2 补丁
**用途**：系统架构与功能设计规范

> **📌 阅读指引**：V1.0 原文自「一、项目目标」开始保留不动，供"当时我怎么想"的历史参考；真实已交付实现请读 **§十 · V1.1 增量补丁** + **§十一 · V1.2 爬虫重构补丁**（文末）。

---

## 一、项目目标

构建一套基于概率模型的竞彩交易决策Web系统，分三层：

1. **模型构建** — 将手册中的评分、筛选逻辑结构化为可配置模型
2. **历史数据回测与修正** — 用真实历史数据验证并迭代模型
3. **实盘筛选与决策** — 对当日比赛自动评分、计算概率、排名推荐

---

## 二、整体架构

```text
┌─────────────────────────────────────────────┐
│              Next.js Frontend                │
│  Dashboard | 回测 | 模型配置 | 用户管理      │
└──────────────────┬──────────────────────────┘
                   │ REST API (JSON)
┌──────────────────▼──────────────────────────┐
│           Python FastAPI Backend             │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │  爬虫模块 │ │ 模型引擎  │ │  用户认证   │  │
│  │ sporttery│ │ 评分/概率 │ │  JWT Auth   │  │
│  │ titan007 │ │ Kelly/回测│ │             │  │
│  └──────────┘ └──────────┘ └─────────────┘  │
│         APScheduler（定时自动抓取）           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│                 MySQL                        │
│  比赛 | 赔率 | 赛果 | 评分记录 | 用户        │
└─────────────────────────────────────────────┘
```

**三条核心数据流：**

- **抓取流**：APScheduler定时 → 爬虫抓sporttery + titan007 → 入库
- **决策流**：用户打开Dashboard → 后端读取今日比赛 → 自动评分排名 → 前端展示推荐
- **回测流**：用户选时间段 → 后端用历史赔率跑模型 → 对比实际赛果 → 输出命中率/盈亏

---

## 三、数据源

| 数据源 | 用途 | 抓取方式 |
| --- | --- | --- |
| <https://www.sporttery.cn/jc/zqszsc/> | 赛程（比赛列表、期号） | httpx + BeautifulSoup |
| <https://www.sporttery.cn/jc/zqsgkj/> | 赛果（实际比分） | httpx + BeautifulSoup |
| <https://jc.titan007.com/schedule.aspx> | 欧赔/亚盘/大小球/让平赔率/球队状态 | httpx + BeautifulSoup |

抓取策略：自动为主（APScheduler定时），手动补录为辅（指定日期触发）。

---

## 四、数据库结构

### leagues — 联赛信息

```text
id, name, country, draw_rate_tier
```

- `draw_rate_tier`：平局率等级（高/中/低），影响联赛类型评分维度

### matches — 比赛基础信息

```text
id, sporttery_match_id, date, league_id,
home_team, away_team, round,
competition_type (联赛/杯赛/淘汰赛首回合/淘汰赛次回合),
status (待开/进行中/已结束)
```

- `sporttery_match_id`：体彩期号，用于关联sporttery数据
- `round`：轮次，用于识别首回合/次回合，影响战意评分

### match_odds — 赔率数据

```text
id, match_id, source,
win_odds, draw_odds, lose_odds,                              -- 欧赔
handicap_value,                                              -- 让球数值（0/0.25/0.5/1球）
win_handicap_odds, draw_handicap_odds, lose_handicap_odds,   -- 让球三项赔率
asian_handicap,                                              -- 亚盘类型（平手/平半/半球/半球以上）
total_goals,                                                 -- 大小球（2/2.25/2.5/2.75+）
scraped_at
```

### match_results — 赛果

```text
id, match_id, home_score, away_score,
result (胜/平/负), handicap_result (让胜/让平/让负)
```

### match_team_stats — 球队状态快照（比赛时刻）

```text
id, match_id,
-- 主队
home_rank, home_season_wins, home_season_draws, home_season_losses,
home_home_wins, home_home_draws, home_home_losses,
home_recent_form,                    -- 近5场，如 "W,D,L,W,W"
-- 客队
away_rank, away_season_wins, away_season_draws, away_season_losses,
away_away_wins, away_away_draws, away_away_losses,
away_recent_form,
-- 历史交锋
h2h_home_wins, h2h_draws, h2h_away_wins,
scraped_at
```

### model_configs — 模型配置版本

```text
id, name, created_by,
weights_json,     -- 6维评分权重（欧赔/亚盘/大小球/战意/平赔压缩/球队状态）
thresholds_json,  -- 下注阈值（平局≥70/让平≥65等）
created_at
```

### match_scores — 比赛评分记录

```text
id, match_id, model_config_id, user_id,
euro_score,         -- 欧赔结构分
asian_score,        -- 亚盘分
goals_score,        -- 大小球分
intent_score,       -- 战意/赛制分
compression_score,  -- 平赔压缩度分
team_stats_score,   -- 球队状态分
total_score,
bet_type,           -- 平/让平
kelly_pct,          -- Kelly建议下注比例
is_recommended,     -- 是否达标推荐
actual_hit,         -- 实际是否命中（复盘填写）
bet_amount,         -- 实际下注金额
notes,
created_at
```

### backtest_sessions — 回测任务

```text
id, user_id, model_config_id,
date_from, date_to,
total_bets, hit_count, hit_rate, roi,
profit_loss,
results_by_score,   -- JSON：各分数段命中率
results_by_league,  -- JSON：各联赛命中率
created_at
```

### users — 用户

```text
id, phone, name, role (admin/member), password_hash, created_at
```

---

## 五、评分系统（6维）

基于手册V1.0扩展，新增球队状态维度：

| 维度 | 满分 | 评分逻辑 |
| --- | --- | --- |
| 欧赔结构 | 25 | 三项接近→高分；一方明显强势→低分 |
| 亚盘 | 20 | 平手20/平半15/半球5/半球以上0 |
| 大小球 | 20 | ≤2.25→20/2.5→10/≥2.75→0 |
| 战意/赛制 | 15 | 淘汰赛/关键战→高分；普通联赛→中低分 |
| 平赔压缩度 | 20 | ≤3.2→20/3.2-3.5→10/≥3.6→0 |
| 球队状态 | 20 | 综合排名接近度/主客场成绩/近期状态 |
| **合计** | **120** | |

**下注阈值**（权重调整后需回测重新校准）：

- 平局下注：总分 ≥ 70%（84分）
- 让平下注：总分 ≥ 65%（78分）

Kelly下注比例（半Kelly）：

| 评分 | 建议下注 |
| --- | --- |
| ≥ 80% | 2%资金 |
| 70–80% | 1.5%资金 |
| 65–70% | 1%资金 |
| < 65% | 不下注 |

---

## 六、功能模块

### ① 数据抓取模块

- 定时自动抓取：每天抓取sporttery赛程 + titan007赔率/球队状态/赛果
- 手动补抓：指定日期触发历史数据补录
- 抓取状态面板：最近抓取时间、成功/失败状态

### ② 今日推荐（核心页面）

- 展示当日所有比赛，自动完成6维评分
- 按总分排名，标注达标场次
- 显示Kelly建议下注比例
- 支持手动修正单场评分或添加备注

### ③ 模型回测

- 选择时间段 + 模型配置版本
- 系统用历史数据跑模型，对比实际赛果
- 输出：命中率、ROI、盈亏、各分数段/各联赛命中率
- 支持两个模型配置版本对比

### ④ 模型配置

- 可视化调整6维权重和下注阈值
- 保存多个配置版本（如"保守版"/"激进版"）
- 回测结果与配置版本绑定展示

### ⑤ 用户管理（Admin）

- 手机号注册/登录（JWT认证）
- 角色：admin（管理用户/模型配置）/ member（查看推荐）
- Admin可查看所有用户下注记录

---

## 七、技术栈

| 层级 | 技术 | 用途 |
| --- | --- | --- |
| 前端 | Next.js 14 + TypeScript | 页面框架 |
| UI组件 | shadcn/ui + Tailwind CSS | 界面组件 |
| 图表 | ECharts / Recharts | 回测可视化 |
| 后端 | Python FastAPI | REST API |
| 爬虫 | httpx + BeautifulSoup | 数据抓取 |
| 模型计算 | NumPy + Pandas | 评分/Kelly/回测 |
| 定时任务 | APScheduler | 自动抓取 |
| 数据库 | MySQL | 主数据存储 |
| ORM | SQLAlchemy + Alembic | 数据库操作+迁移 |
| 认证 | JWT (python-jose) | 手机号登录鉴权 |
| 部署 | Docker Compose | 一键启动 |

---

## 八、项目结构

```text
sporttery_10x/
├── frontend/
│   ├── app/
│   │   ├── dashboard/     — 今日推荐
│   │   ├── backtest/      — 回测
│   │   ├── model/         — 模型配置
│   │   └── admin/         — 用户管理
│   └── components/
├── backend/
│   ├── api/               — 路由层
│   ├── models/            — 数据库模型
│   ├── scrapers/          — 爬虫模块
│   ├── engine/            — 评分/回测引擎
│   └── scheduler/         — 定时任务
└── docker-compose.yml
```

---

## 九、后续可扩展

- 短信验证码登录（替代密码）
- 微信/钉钉推送每日推荐
- 赔率变动监控（盘口异动提醒）
- 更多数据源接入（如爱彩网）

---

## 十、V1.1 增量补丁（2026-04-27）

本节汇总 V1.0 与 P1-P7 + P8 H1 落地之间的差异。读者**以本节为准**，以上章节保留供历史参考。

### 10.1 数据源修订

| 维度 | V1.0 | V1.1 |
| --- | --- | --- |
| 球队状态 | titan007 | **sporttery**（按 `sporttery_match_id` 抓球队状态，见 `app/scrapers/sporttery/team_stats.py`） |
| 赛果 / 赛程 | sporttery | sporttery（不变） |
| 欧赔/亚盘/大小球 | titan007 | titan007（不变） |

### 10.2 数据库结构补丁

- `matches.date` → `match_date` (`DateTime`, 含开球时刻)
- 所有业务表混入 `TimestampMixin` → 统一 `created_at / updated_at`
- `matches.status` 固定为 `enum('scheduled','in_progress','finished')`
- `match_odds` 字段类型：`*_odds DECIMAL(6,3)` / `total_goals DECIMAL(4,2)` / `asian_handicap VARCHAR(32)`
- `backtest_sessions` 新增：`mode`（`fixed|kelly|both`）、`initial_capital`、`kelly_profit_loss`、`kelly_roi`、`equity_curve`（JSON）
- `model_configs` 新增：`scrape_schedule_json`（可覆盖 cron）、**`is_active BOOLEAN`**（P7，全局唯一 true）、**`parent_id FK`**（P7，克隆血缘）、**`name` UNIQUE**（P8 H1 TD-2）
- `match_scores` 新增复盘子分组：`actual_hit` / `bet_amount` / `notes`；`(match_id, model_config_id)` UNIQUE；`updated_at` 兼任复盘乐观锁字段
- 新增表 `scrape_logs`（`id, source, status(running|success|failed|partial), records, message, duration_ms, created_at`）

迁移链：`0001_initial_schema → 0002_scrape_status_running → 0003_match_scores_unique → 0004_backtest_fields → 0005_normalize_legacy_weights → 0006_model_config_active_parent (HEAD)`。

### 10.3 评分系统口径澄清

- 阈值以**绝对分数**存储（`draw_min_score=84`、`handicap_draw_min_score=78`），文档描述可用百分比辅助理解（84/120≈70%、78/120=65%）。
- 权重归一化约定：`normalized[k] = weights[k] / DEFAULT_WEIGHTS[k]`，其中 `DEFAULT_WEIGHTS = {euro:25, asian:20, goals:20, intent:15, compression:20, team_stats:20}`（即每维满分盖）。UI 里填的数字直接落在 `[0, dim_cap]` 区间。
- 历史遗留权重 `{1.0}` 在 0005 迁移里自动归一到默认值。

### 10.4 功能模块交付状态（覆盖 V1.0 §六）

| 模块 | V1.0 标记 | V1.1 真实状态 |
| --- | --- | --- |
| ① 数据抓取 | 设计 | ✅ P4 |
| ② 今日推荐 | 设计 | ✅ P5 |
| ③ 回测 | 设计 | ✅ P6（超出设计：equity_curve / Kelly 双口径 / owner 隔离 / 90 天上限） |
| ④ 模型配置 UI | 设计 | ✅ P7（`/model` + 克隆/激活 + P8 H1 激活即时重算） |
| ⑤ 用户管理 admin | 设计 | 🟡 后端 API 全、**前端 `/admin/users` 未开发**（TD-5，P8+） |
| ⑥ 复盘 | 未独立成模块 | ✅ P7（`/review` + Dashboard「已结束」Tab + P8 H1 乐观锁 TD-1） |

### 10.5 技术栈修订

- 图表：**Recharts**（V1.0 的 ECharts 未引入）
- 模型计算：**Python `Decimal` + dataclass**（未引入 NumPy / Pandas；无矩阵需求，Decimal 避免 P/L 浮点漂移）
- 定时任务：APScheduler `BlockingScheduler`（独立容器，无 SQLAlchemyJobStore）

### 10.6 项目结构补全

```
backend/app/
  ├── api/       路由层
  ├── cli/       管理 CLI (create_admin)
  ├── core/      配置 / DB session / security
  ├── engine/    scoring / kelly / backtest
  ├── models/    SQLAlchemy
  ├── scrapers/  httpx+bs4
  ├── scheduler/ BlockingScheduler + jobs
  ├── schemas/   Pydantic DTO
  ├── scripts/   seed.py
  └── services/  ModelConfig / Backtest 服务层
frontend/
  ├── app/       dashboard / backtest / model / review / admin/scrape / login
  ├── components/
  └── lib/       api 客户端 + zustand + i18n(预留)
```

### 10.7 遗留风险登记册（与 PRD V1.1 同步）

完整列表见 `docs/superpowers/plans/2026-04-27-p8-tech-debt.md`。V1.1 时点未了项（H2）：
- TD-3 回测扣佣金；TD-4 比赛 cancelled/postponed 状态；TD-5 `/admin/users` UI；TD-7 权重 per-dim 上限校验；TD-8 赔率多源优先级；TD-10 赔率历史快照（盘口异动告警前置）；TD-11 爬虫面板细化；TD-15 refresh token 黑名单。

---

## 十一、V1.2 爬虫重构补丁（2026-04-23）

本节记录对数据抓取层的全面重构。V1.0/V1.1 的 HTML 解析方案已全部替换为 JSON API 调用。

### 11.1 数据源修订（覆盖 V1.0 §三）

| 功能 | V1.0/V1.1 | V1.2 实际 |
|------|-----------|-----------|
| 新赛程 | sporttery HTML 解析 | `getMatchCalculatorV1.qry` JSON API |
| 历史赛果 | sporttery HTML 解析 | `getUniformMatchResultV1.qry` JSON API |
| 球队统计 | sporttery 详情页 HTML | 3 个 JSON API（getMatchHeadV1 / getResultHistoryV1 / getMatchResultV1） |
| 实时赔率 | titan007 schedule.aspx HTML | `bf_jc.txt` + `goallottery1.txt` XML feed |
| 历史赔率 | titan007 oddsData.aspx cid=105 | `oddsData.aspx cid=1`（澳门，列顺序 D/H/A） |
| HHAD 赔率 | 无 | `getFixedBonusV1.qry`（新增） |
| 抓取方式 | httpx + BeautifulSoup | **httpx + JSON/TXT 直接解析**（无 BS4 依赖） |

### 11.2 数据库结构修订（覆盖 V1.1 §10.2）

**表名重命名**（0007 迁移）：

| V1.0/V1.1 | V1.2 |
|------------|------|
| `matches` | `sporttery_matches` |
| `match_odds` | `sporttery_match_odds` |
| `match_results` | `sporttery_match_results` |
| `match_scores` | `sporttery_match_scores` |
| `match_team_stats` | `sporttery_match_team_stats` |

**主键变更**：`sporttery_matches.id` 从自增 INT 改为 **12 位 BIGINT 逻辑 ID**（`YYYYMMDDWSSS`，如 `202604190005`），用于跨竞彩/Titan007 精确匹配。

**新增竞彩赔率列**（0008 迁移，`sporttery_matches` 表）：

```
had_h    DECIMAL(6,3)  -- 竞彩胜赔率（计算奖金用）
had_d    DECIMAL(6,3)  -- 竞彩平赔率
had_a    DECIMAL(6,3)  -- 竞彩负赔率
hhad_h   DECIMAL(6,3)  -- 竞彩让球胜赔率
hhad_d   DECIMAL(6,3)  -- 竞彩让球平赔率
hhad_a   DECIMAL(6,3)  -- 竞彩让球负赔率
hhad_goal_line DECIMAL(4,1) -- 让球数
```

**赔率双轨存储**：

| 表 | 存什么 | 用途 |
|----|--------|------|
| `sporttery_matches.had_*/hhad_*` | 竞彩官网赔率 | 计算竞彩奖金（返奖率~65%，赔率失真） |
| `sporttery_match_odds`（source=titan007） | 澳门欧赔 + 亚盘 | **模型评分输入**（更接近真实概率） |

**迁移链更新**：`0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007_rename_tables_add_logical_id → 0008_add_sporttery_odds_to_matches (HEAD)`

### 11.3 定时任务修订（覆盖 V1.1 schedule 描述）

| 任务 | V1.1 | V1.2 |
|------|------|------|
| `schedule` | 仅抓赛程 | **一条龙**：赛程 → 赔率 → 球队统计（串行执行，确保新增比赛立即有完整数据） |
| `odds` | 调 sporttery | **Titan007Odds**（`bf_jc.txt` + `goallottery1.txt` 实时 feed） |
| `result` | 不变 | 不变（getUniformMatchResultV1） |
| `team_stats` | 调 titan007 HTML | 3 个竞彩 JSON API |
| `scoring` | 不变 | 不变 |

### 11.4 新增模块

| 模块 | 说明 |
|------|------|
| `scrapers/titan007/history.py` | JcResult.aspx + oddsData.aspx 解析器（TitanMatch / TitanOdds 数据结构） |
| `scripts/backfill.py` | 历史数据回补 CLI（`--from --to --force --delay --no-stats`） |
| `models/match_id.py` | 12 位逻辑 ID 构建/解析工具（`logical_id_from_kickoff` / `logical_id_from_jc` / `parse_jc_code`） |

### 11.5 关键技术细节

**oddsData.aspx 欧赔列顺序**（已通过 `1x2.titan007.com/oddslist/` 交叉验证）：

```
section[2]: id ^ initDraw ^ initHome ^ initAway ^ currDraw ^ currHome ^ currAway
```

与 V1.0 假设的 Home/Draw/Away 顺序不同，实际为 **Draw/Home/Away**。

**cid 映射**：

| cid | 公司 | 说明 |
|-----|------|------|
| 1 | 澳门 | 当前使用，亚洲主流参考 |
| 105 | 竞彩官方 | 不可用于模型（返奖率低，赔率失真） |
| 3 | 待确认 | 可能是其他欧洲博彩公司 |

**Titan007 实时 feed 解析**：

- `bf_jc.txt`：按 `$` 分大段、`!` 分行、`^` 分字段；fields[0]=match_id, fields[1]=kickoff(JS 月份+1), fields[4]=jc_code
- `goallottery1.txt`：复用 `parse_odds_data()`，与 `oddsData.aspx` 同格式

**HHAD 赔率获取**：

- 新赛程：`getMatchCalculatorV1.qry` 响应中 `hhad.{h,d,a,goalLine}` 直接包含
- 历史回补：`getFixedBonusV1.qry` → `value.oddsHistory.hhadList[-1]`（取终盘赔率）

### 11.6 项目结构补全（覆盖 V1.1 §10.6）

```
backend/app/
  ├── api/          路由层
  ├── cli/          管理 CLI (create_admin)
  ├── core/         配置 / DB session / security
  ├── engine/       scoring / kelly / backtest
  ├── models/       SQLAlchemy（sporttery_matches / match_id / odds / result / team_stats / ...）
  ├── scrapers/
  │   ├── base.py / http.py
  │   ├── sporttery/  schedule.py / result.py / team_stats.py
  │   └── titan007/   odds.py / history.py / analysis.py(预留)
  ├── scheduler/    BlockingScheduler + jobs（含 schedule 链式调用）
  ├── schemas/      Pydantic DTO
  ├── scripts/      seed.py / backfill.py
  └── services/     ModelConfig / Backtest / ScrapeRunner

frontend/app/
  ├── dashboard / backtest / model / review / admin/scrape / login
  ├── components/
  └── lib/          api 客户端 + zustand
```

### 11.7 遗留风险更新

| 风险 | 状态 |
|------|------|
| ~~HTML 解析脆弱~~ | ✅ 已消除：全部改为 JSON API |
| ~~BeautifulSoup 无法解析 JS 渲染页面~~ | ✅ 已消除：不再依赖 HTML |
| ~~cid=105 拉到竞彩官方赔率而非真实欧赔~~ | ✅ 已修复：改用 cid=1（澳门） |
| ~~欧赔列顺序错误（win/draw 互换）~~ | ✅ 已修复：D/H/A 顺序已验证 |
| ~~历史回补缺 HHAD 赔率~~ | ✅ 已修复：getFixedBonusV1.qry 补全 |
| Bet365 真实 cid 待确认 | 🟡 当前用澳门（cid=1），如需 Bet365 需调研对应 cid |
| Titan007 XML feed 长期稳定性 | 🟡 有 `oddsData.aspx` 作为历史后备 |

## 12. 当前抓取数据源边界（2026-04-26 更新）

### 12.1 未来/今日推荐链路

未来推荐需要完整赛前信息，不是只抓赛程。当前链路为：

1. `SportterySchedule` 抓取竞彩赛程、竞彩编号、官方 HAD/HHAD 赔率，写入 `sporttery_matches`。
2. `Titan007Odds` 通过 `bf_jc.txt` 和 `goallottery1.txt` 抓取 Titan007 实时映射、澳门欧赔、亚盘，写入 `sporttery_match_odds`。
3. `Titan007AnalysisStats` 通过 Titan007 `analysis/{match_id}cn.htm` 抓取赛前球队状态、近期比分、主客场近况、交锋信息，写入 `sporttery_match_team_stats`。
4. `ScoringService` 在上述数据尽量齐全后计算推荐分数。

因此 `schedule` 定时任务仍然是一条龙，但现在语义是：赛程 → Titan007 欧赔/亚盘 → Titan007 赛前分析，而不是调用竞彩网球队状态。

### 12.2 历史回填链路

历史回填必须避免球队状态泄漏。当前约束为：

1. Sporttery 历史接口可用于官方赛果、竞彩奖金赔率、HHAD 终盘赔率补充。
2. Titan007 `JcResult.aspx` 是 `竞彩编号 -> titan007_match_id` 的历史精确映射来源。
3. Titan007 `oddsData.aspx?cid=1` 是历史澳门欧赔/亚盘来源。
4. Titan007 `analysis/{match_id}cn.htm` 是历史球队状态唯一默认来源。
5. 历史回填不得调用 `SportteryTeamStats` 或 `fetch_stats_for_mid`，因为竞彩网球队状态历史回看可能显示最新状态。

### 12.3 遗留模块说明

`backend/app/scrapers/sporttery/team_stats.py` 保留为遗留解析器和兼容代码，但不再进入默认调度链路，也不作为模型研究和历史回测的数据来源。后续如果要删除，需要先确认没有运维脚本或旧测试依赖。
