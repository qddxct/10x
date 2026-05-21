# Titan007 香港马场欧赔兜底实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 历史赔率抓取优先澳门，澳门缺失时用香港马场单场欧赔补齐。

**Architecture:** 保留 `oddsData.aspx?cid=1` 作为澳门主源；只对澳门缺失的比赛请求 `1x2d.titan007.com/{match_id}.js`，从公司 ID `432` 的香港马场行解析当前主/平/客欧赔；合并时澳门永远优先。

**Tech Stack:** Python 3.11, httpx, pytest, ruff, Titan007 `oddsData.aspx`, Titan007 `1x2d` 单场欧赔 JS。

---

## Task 1: 写香港马场兜底解析测试

**Files:**
- Modify: `backend/tests/test_scrapers_titan007_history_fallback.py`

- [ ] 新增测试：从 `var game=Array(...)` 中按 `company_id=432` 提取香港马场当前欧赔。
- [ ] 新增测试：当 JS 中没有 `432` 时返回 `None`。
- [ ] 新增测试：合并时澳门已有比赛不被香港马场覆盖。
- [ ] 运行测试，确认新增解析测试先失败。

## Task 2: 实现香港马场单场欧赔解析

**Files:**
- Modify: `backend/app/scrapers/titan007/history.py`

- [ ] 删除旧备选公司常量和文案。
- [ ] 新增 `TITAN_HKJC_COMPANY_ID = "432"`。
- [ ] 新增 `parse_oddslist_js_company(match_id, text, company_id)`。
- [ ] 保持 `merge_titan_odds_by_priority()` 只做优先级合并，不耦合具体公司。
- [ ] 运行单元测试，确认解析测试通过。

## Task 3: 接入回填链路

**Files:**
- Modify: `backend/app/scripts/backfill.py`

- [ ] 修改 `fetch_titan_day()`：先拿比赛列表，再把 `matches` 传给赔率兜底函数。
- [ ] 修改 `fetch_titan_odds_with_fallback(client, target_date, matches)`：只请求澳门日期接口和缺失 match id 的香港马场单场 JS。
- [ ] 删除多公司日期接口循环和旧兜底日志。
- [ ] 运行相关测试，确认审计脚本仍可复用 `fetch_titan_day()`。

## Task 4: 验证 2026 年 3 月

**Run:**

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.audit_historical_fetch --start 2026-03-01 --end 2026-03-31 --label march-2026-hkjc-fallback-audit --delay 0.1 --analysis-delay 0.1 --report docs/analysis/2026-04-26-historical-fetch-audit-2026-03-hkjc-fallback.md
```

Expected: Titan007 欧赔覆盖高于 `162/170`；理想结果为 `170/170`。

## Task 5: 最终验证

**Run:**

```bash
cd backend && .venv/bin/python -m pytest tests/test_scrapers_titan007_history_fallback.py tests/test_audit_historical_fetch.py tests/test_backfill_titan_team_stats.py -q
cd backend && .venv/bin/python -m ruff check app/scrapers/titan007/history.py app/scripts/backfill.py app/scripts/audit_historical_fetch.py tests/test_scrapers_titan007_history_fallback.py
```
