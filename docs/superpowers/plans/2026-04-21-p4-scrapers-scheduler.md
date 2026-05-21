# P4 实现计划：爬虫与定时任务

- **关联 Spec**：`docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`（第六节·①数据抓取模块）
- **关联 Brainstorm**：`docs/superpowers/brainstorm/2026-04-21-decisions.md`
- **依赖前置**：P1 脚手架、P2 数据模型、P3 认证（admin 权限）
- **最后更新**：2026-04-23（V2.0 —— 反映爬虫 API 化重构、赔率源修正、HHAD 补全）

> **📌 本文档已按实际实现更新至 V2.0。** 原始 V1.0 设计基于 HTML 解析，实际落地后全部改为 JSON API 调用。

---

## 关键决策

| # | 决策 | 最终选择 |
|---|---|---|
| Q1 | 爬虫抓取技术方案 | **JSON API 为主**：竞彩网和 Titan007 均已发现可用的 JSON/TXT API，不再需要 HTML 解析。`httpx` 直接调用，无需 BeautifulSoup |
| Q2 | APScheduler 运行形态 | **B**：独立 worker 进程 `python -m app.scheduler.main`，与 FastAPI 分离 |
| Q3 | 赔率数据源 | **澳门（cid=1）**：`oddsData.aspx` 的 `cid=1` 对应澳门博彩，非 Bet365。欧赔列顺序为 Draw/Home/Away |
| Q4 | 赛程任务链 | **一条龙**：schedule → odds → team_stats 串行执行，确保新增比赛立即有赔率和球队统计 |
| Q5 | 竞彩赔率 vs 模型赔率 | **分离存储**：`sporttery_matches.had_*/hhad_*` 存竞彩官方赔率（算奖金）；`sporttery_match_odds` 存澳门真实赔率（模型评分） |

---

## 数据源（V2.0 实际）

### 竞彩网 API（sporttery.cn）

| API | 用途 | 调用方 |
|-----|------|--------|
| `getMatchCalculatorV1.qry?channel=c&poolCode=hhad,had` | 新赛程 + 竞彩 HAD/HHAD 赔率 | `SportterySchedule` |
| `getUniformMatchResultV1.qry?matchBeginDate=&matchEndDate=` | 历史赛果 + HAD 赔率 + 让球数 | `SportteryResult` / `backfill.py` |
| `getFixedBonusV1.qry?clientCode=3001&matchId={mid}` | HHAD 赔率历史（终盘） | `backfill.py` |
| `getMatchHeadV1.qry?source=web&sportteryMatchId={mid}` | 球队排名 + 赛季战绩 | `team_stats.py` |
| `getResultHistoryV1.qry?sportteryMatchId={mid}&termLimits=10` | 交锋记录 | `team_stats.py` |
| `getMatchResultV1.qry?sportteryMatchId={mid}&termLimits=6` | 近期战绩（生成 form 字符串） | `team_stats.py` |

### Titan007 API（jc.titan007.com）

| API | 用途 | 调用方 |
|-----|------|--------|
| `xml/bf_jc.txt` | 实时比赛列表（titan007_id ↔ 竞彩编号映射） | `Titan007Odds`（实时） |
| `xml/goallottery1.txt` | 实时澳门欧赔 + 亚盘（全部在售比赛） | `Titan007Odds`（实时） |
| `handle/JcResult.aspx?d=YYYY-MM-DD` | 历史比赛列表 + 竞彩编号映射 | `backfill.py` |
| `handle/oddsData.aspx?d=YYYY-MM-DD&cid=1&st=1` | 历史澳门欧赔 + 亚盘（终盘） | `backfill.py` |

### 重要技术细节

**oddsData.aspx 欧赔列顺序**（已验证）：

```
section[2]: id ^ 初和 ^ 初主 ^ 初客 ^ 即和 ^ 即主 ^ 即客
                Draw   Home   Away   Draw   Home   Away
```

**`cid` 映射**：`cid=1` = 澳门（非 Bet365），`cid=105` = 竞彩官方（不可用于模型）。

**12 位逻辑比赛 ID**：`YYYYMMDDWSSS`（日期 8 位 + 星期 1 位[周日=0] + 编号 3 位），用于跨源匹配。

---

## 目录结构（V2.0 实际）

```
backend/app/
├── scrapers/
│   ├── __init__.py
│   ├── base.py                # Scraper ABC + ScrapeError
│   ├── http.py                # httpx client 工厂（timeout/UA/重试）
│   ├── sporttery/
│   │   ├── __init__.py
│   │   ├── schedule.py        # 赛程（getMatchCalculatorV1 JSON API）
│   │   ├── result.py          # 赛果（getUniformMatchResultV1 JSON API）
│   │   └── team_stats.py      # 球队统计（3 个竞彩 JSON API）
│   └── titan007/
│       ├── __init__.py
│       ├── history.py          # JcResult + oddsData 解析器（backfill 用）
│       ├── odds.py             # 实时赔率（bf_jc.txt + goallottery1.txt XML feed）
│       └── analysis.py         # [未接入] titan007 分析页 HTML 解析（预留）
├── scheduler/
│   ├── __init__.py
│   ├── main.py                # BlockingScheduler 入口 + cron 注册
│   └── jobs.py                # 5 个 job 函数 + schedule 链式调用
├── scripts/
│   ├── backfill.py            # 历史数据回补（CLI: --from --to --force）
│   └── seed.py                # 种子数据（admin 用户 + 默认 ModelConfig）
├── services/
│   └── scrape_runner.py       # ScrapeLog 生命周期管理
├── models/
│   ├── match.py               # SportteryMatch（含竞彩 HAD/HHAD 赔率列）
│   ├── match_id.py            # 12 位逻辑 ID 工具函数
│   ├── odds.py                # SportteryMatchOdds
│   ├── result.py              # SportteryMatchResult
│   ├── team_stats.py          # SportteryMatchTeamStats
│   └── ...
└── api/
    └── scrape.py              # /api/scrape/* 路由（admin-only）

frontend/app/admin/scrape/
├── page.tsx
├── scrape-dashboard.tsx
└── scrape-dashboard.module.styl
```

---

## 定时任务编排（V2.0 实际）

### 5 个 Cron Job

| 任务 ID | 时间 | 函数 | 行为 |
|---------|------|------|------|
| `schedule` | 每天 08:30 | `run_schedule_job` | **链式**：SportterySchedule → Titan007Odds → run_team_stats_job(days_ahead=7) |
| `result` | 每天 23:30 | `run_result_job` | SportteryResult（近 3 天赛果） |
| `odds` | 每 2h 分15 | `run_odds_job` | Titan007Odds（实时 XML feed） |
| `team_stats` | 每天 09:00 | `run_team_stats_job` | 未来 3 天比赛的球队统计 |
| `scoring` | 每天 09:15 | `run_scoring_job` | 今日+明日评分计算 |

### schedule 任务链详细

```python
def run_schedule_job(session_factory):
    # Step 1: 赛程
    schedule_out = ScrapeRunner(db).execute(SportterySchedule(db=db))

    # Step 2: 赔率（新增比赛立即获得澳门赔率）
    odds_out = ScrapeRunner(db).execute(Titan007Odds(db=db))

    # Step 3: 球队统计（未来 7 天）
    stats_out = run_team_stats_job(session_factory, days_ahead=7)

    return ScraperOutcome(records=合计, ...)
```

---

## 抓取器实现详解

### SportterySchedule（赛程）

- **数据源**：`getMatchCalculatorV1.qry?channel=c&poolCode=hhad,had`
- **解析**：JSON → `value.matchInfoList[].subMatchList[]`
- **提取**：matchId, homeTeamAbbName, awayTeamAbbName, matchDate, matchTime, leagueAbbName, matchNumStr
- **赔率**：同时提取 `had.{h,d,a}` + `hhad.{h,d,a,goalLine}`（竞彩官方赔率）
- **写入**：`sporttery_matches`（主键为 12 位逻辑 ID），含 HAD/HHAD 赔率列
- **幂等**：按 logical_id 做 upsert

### SportteryResult（赛果）

- **数据源**：`getUniformMatchResultV1.qry`（默认近 3 天）
- **过滤**：`matchResultStatus == '2'`（已结束）
- **提取**：sectionsNo999（全场比分如"2:1"）、h/d/a（HAD 赔率）、goalLine
- **写入**：更新 `sporttery_matches.status='finished'` + HAD 赔率；创建/更新 `sporttery_match_results`

### Titan007Odds（实时赔率）

- **数据源**：两个轻量 TXT feed
  - `bf_jc.txt`：比赛列表，提取 titan007_match_id ↔ jc_code 映射 + kickoff 时间
  - `goallottery1.txt`：澳门欧赔 + 亚盘（通过 `parse_odds_data` 解析）
- **匹配**：用 `logical_id_from_kickoff(kickoff, jc_code)` 生成 12 位 ID，再 `db.get(SportteryMatch, logical_id)`
- **写入**：`sporttery_match_odds`（source='titan007'）

### fetch_stats_for_mid（球队统计）

- **数据源**：3 个竞彩 JSON API
  - `getMatchHeadV1.qry`：排名、赛季总/主客场战绩
  - `getResultHistoryV1.qry`：交锋记录（用 sportteryHomeTeamId 匹配）
  - `getMatchResultV1.qry`：近 6 场战绩（生成 form 字符串如"WDLWWL"）
- **写入**：`sporttery_match_team_stats`

### backfill.py（历史回补脚本）

- **主数据源**：竞彩 `getUniformMatchResultV1.qry`（赛果 + HAD 赔率）
- **赔率补充**：Titan007 `JcResult.aspx`（ID 映射）+ `oddsData.aspx?cid=1`（澳门终盘赔率）
- **HHAD 补充**：竞彩 `getFixedBonusV1.qry`（hhadList 末条 = 终盘赔率）
- **球队统计**：同 `fetch_stats_for_mid`
- **CLI**：`python -m app.scripts.backfill --from 2025-10-01 --to 2026-04-23 --force`

---

## 赔率存储策略

```
sporttery_matches（竞彩官方赔率 — 用于计算奖金）
  ├── had_h / had_d / had_a          ← 胜平负赔率
  ├── hhad_h / hhad_d / hhad_a       ← 让球胜平负赔率
  └── hhad_goal_line                  ← 让球数

sporttery_match_odds（澳门真实赔率 — 模型评分使用）
  ├── win_odds / draw_odds / lose_odds  ← 欧赔（主胜/和/客胜）
  ├── handicap_value                    ← 亚盘盘口
  ├── win_handicap_odds / lose_handicap_odds  ← 亚盘水位
  └── source = 'titan007'
```

> 竞彩赔率返奖率低（~65%），赔率失真；澳门赔率更接近真实概率，作为模型输入。

---

## REST API

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/scrape/jobs` | admin | 列出可调度任务名与说明 |
| GET | `/api/scrape/logs` | admin | 分页查询 ScrapeLog（source/status/job_name/limit/offset） |
| POST | `/api/scrape/jobs/{name}/run` | admin | 立即执行：schedule / result / odds / team_stats / scoring |

---

## 迁移链

```
0001_initial_schema
0002_scrape_status_running
0003_match_scores_unique
0004_backtest_fields
0005_normalize_legacy_weights
0006_model_config_active_parent
0007_rename_tables_add_logical_id    ← sporttery_ 前缀 + 12 位逻辑 ID
0008_add_sporttery_odds_to_matches   ← HAD/HHAD 竞彩赔率列
```

---

## 风险与缓解（更新）

| 风险 | 缓解 |
|---|---|
| 竞彩网 API 接口变更 | JSON API 比 HTML 解析更稳定；ScrapeLog 记录失败详情 |
| Titan007 XML feed 停服 | 有 `oddsData.aspx` 作为历史回补后备；feed 停服时 odds job 失败但不阻塞评分 |
| 澳门赔率覆盖率不足 | `bf_jc.txt` 一次返回全部在售比赛，覆盖率高于分日 API |
| `oddsData.aspx` 列顺序变化 | 已通过 Titan007 比较页交叉验证：Draw/Home/Away 顺序 |
| 调度器与 API 时区不一致 | `Asia/Shanghai` 统一配置；APScheduler 显式传 tz |
| HHAD 赔率缺失 | backfill 中通过 `getFixedBonusV1.qry` 逐场补全；schedule 阶段 `getMatchCalculatorV1` 已内含 HHAD |

---

## 交付验收（更新）

- `docker-compose up` 后 scheduler 存活，5 个 job 按时执行
- `POST /api/scrape/jobs/schedule/run` 一条龙执行赛程+赔率+球队统计
- 历史回补 7 天：45 场比赛，HAD/HHAD/赔率/球队统计全量填充，0 失败
- 赔率与 Titan007 比较页（`1x2.titan007.com/oddslist/`）交叉验证一致
