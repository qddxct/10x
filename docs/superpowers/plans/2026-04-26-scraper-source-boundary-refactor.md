# 抓取数据源边界重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构赛程、欧赔、球队状态、历史回填的数据源边界，保证未来推荐数据完整，历史回测不发生球队状态泄漏。

**Architecture:** 保留 Sporttery 作为赛程和官方奖金赔率来源；新增面向调度的 Titan007 analysis 状态抓取器；历史回填继续用 Titan007 JcResult/oddsData/analysis 精确映射。调度层只调用 Titan007 状态抓取器，不再调用 Sporttery 状态抓取器。

**Tech Stack:** Python 3.11, SQLAlchemy, httpx, pytest, ruff, MySQL, Titan007 `bf_jc.txt` / `goallottery1.txt` / `analysis/{id}cn.htm`。

---

## Task 1: 写失败测试锁定未来状态来源

**Files:**
- Create: `backend/tests/test_scrapers_titan007_analysis_stats.py`
- Modify: `backend/tests/test_scheduler_jobs.py`

- [ ] **Step 1: 新增 Titan007 analysis 状态抓取器测试**

创建测试，构造一场未来比赛，提供 `jc_code -> titan007_match_id` 映射和假 analysis 解析结果，断言状态写入 `sporttery_match_team_stats`。

- [ ] **Step 2: 更新调度测试**

把 `run_team_stats_job` 的 mock 从 `SportteryTeamStats` 改成 `Titan007AnalysisStats`，断言无候选时不调用，有候选时调用。

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_scrapers_titan007_analysis_stats.py tests/test_scheduler_jobs.py -q
```

Expected: 新测试因模块或类不存在失败。

## Task 2: 实现 Titan007AnalysisStats

**Files:**
- Create: `backend/app/scrapers/titan007/analysis_stats.py`
- Modify: `backend/app/scrapers/titan007/analysis.py`

- [ ] **Step 1: 新增抓取器类**

实现 `Titan007AnalysisStats`，输入 DB、候选比赛逻辑 ID、Titan007 映射 fetcher、analysis fetcher/parser，可测试注入。

- [ ] **Step 2: 写入球队状态**

复用 `parse_analysis()` 产出的 `TitanTeamStats` 字段，upsert 到 `sporttery_match_team_stats`。

- [ ] **Step 3: 运行新测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_scrapers_titan007_analysis_stats.py -q
```

Expected: PASS。

## Task 3: 调度切换到 Titan007 状态抓取

**Files:**
- Modify: `backend/app/scheduler/jobs.py`
- Modify: `backend/tests/test_scheduler_jobs.py`

- [ ] **Step 1: 查询候选比赛逻辑 ID**

把 `find_match_ids_needing_stats` 改成返回未来待补状态的比赛逻辑 ID，或新增 `find_matches_needing_titan_stats` 保持旧函数兼容。

- [ ] **Step 2: `run_team_stats_job` 调用 `Titan007AnalysisStats`**

调度任务不再调用 `SportteryTeamStats`。

- [ ] **Step 3: 跑调度测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_scheduler_jobs.py -q
```

Expected: PASS。

## Task 4: 历史回填边界加固

**Files:**
- Modify: `backend/app/scripts/backfill.py`
- Modify: `backend/tests/test_backfill_titan_team_stats.py`

- [ ] **Step 1: 更新注释和命名**

把历史回填说明从 `Sporttery-primary` 改为“组合源历史回填”，明确球队状态只来自 Titan007 analysis。

- [ ] **Step 2: 增加不调用 Sporttery 状态接口的测试**

测试 `upsert_day` 只通过 `_upsert_team_stats` 使用 Titan007 match id，不依赖 Sporttery 状态 fetcher。

- [ ] **Step 3: 跑历史回填测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_backfill_titan_team_stats.py tests/test_scrapers_titan007_analysis.py -q
```

Expected: PASS。

## Task 5: 文档同步和最终验证

**Files:**
- Modify: `docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`
- Modify: `docs/usage/USAGE.md`

- [ ] **Step 1: 更新长期架构文档**

追加“当前数据源边界”：未来推荐和历史回填分别使用哪些源。

- [ ] **Step 2: 运行后端相关测试和 ruff**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_scrapers_titan007_analysis.py tests/test_scrapers_titan007_analysis_stats.py tests/test_backfill_titan_team_stats.py tests/test_scheduler_jobs.py -q
cd backend && .venv/bin/python -m ruff check app/scrapers/titan007/analysis.py app/scrapers/titan007/analysis_stats.py app/scheduler/jobs.py app/scripts/backfill.py tests/test_scrapers_titan007_analysis_stats.py tests/test_backfill_titan_team_stats.py tests/test_scheduler_jobs.py
```

Expected: tests PASS, ruff reports no errors。
