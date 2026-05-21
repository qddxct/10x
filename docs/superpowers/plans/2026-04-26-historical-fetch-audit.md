# 历史抓取旁路审计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用新抓取链路抓取一个月历史数据到旁路审计表，并和正式表对比输出数据质量报告。

**Architecture:** 新增独立脚本 `audit_historical_fetch.py`，脚本用 raw SQL 创建审计表，用现有 parser/fetcher 生成快照，再读取正式 SQLAlchemy 模型做字段级 diff。正式业务表只读不写。

**Tech Stack:** Python 3.11, SQLAlchemy, httpx, MySQL, pytest, ruff, Titan007/Sporttery 抓取模块。

---

## Task 1: 写纯函数测试

**Files:**
- Create: `backend/tests/test_audit_historical_fetch.py`

- [ ] 测试数值归一化比较：`Decimal('2.300')` 与 `'2.3'` 视为相等。
- [ ] 测试缺失正式值时生成 `missing_existing`。
- [ ] 测试字段不同生成 `mismatch`。

## Task 2: 实现审计脚本

**Files:**
- Create: `backend/app/scripts/audit_historical_fetch.py`

- [ ] 创建审计表：`data_audit_runs`、`data_audit_match_snapshots`、`data_audit_diffs`。
- [ ] 抓取日期范围数据并写入 snapshots。
- [ ] 对比正式表并写入 diffs。
- [ ] 生成中文 Markdown 报告。

## Task 3: 验证短范围

**Run:**

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.audit_historical_fetch --start 2026-02-01 --end 2026-02-02 --label smoke --delay 0.2 --analysis-delay 0.2 --report docs/analysis/2026-04-26-historical-fetch-audit-smoke.md
```

Expected: 审计表有 run、snapshots、diffs，报告生成。

## Task 4: 运行一个月审计

**Run:**

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.audit_historical_fetch --start <现有最新可比日期-30天> --end <现有最新可比日期> --label one-month-quality --delay 0.5 --analysis-delay 0.5 --report docs/analysis/2026-04-26-historical-fetch-audit.md
```

Expected: 输出一个月质量报告。

## Task 5: 代码验证

**Run:**

```bash
cd backend && .venv/bin/python -m pytest tests/test_audit_historical_fetch.py -q
cd backend && .venv/bin/python -m ruff check app/scripts/audit_historical_fetch.py tests/test_audit_historical_fetch.py
```

Expected: tests PASS, ruff PASS。
