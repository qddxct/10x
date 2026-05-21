# Titan007 结构化近期比分补数 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 Titan007 历史 analysis 页面补齐近期比分、进失球、一球胜负分布字段，并先用只读分析验证它们是否值得进入 V3.1/V4。

**Architecture:** 先定位 Titan007 JS 数组中的比分字段，再扩展纯解析器产出结构化聚合；数据库只增加 nullable 快照字段，专用回填脚本按比赛业务日重建 `jc_code -> titan007_match_id` 映射后更新球队状态。模型逻辑保持不动，回填后通过独立分析报告判断增益。

**Tech Stack:** Python 3.12, SQLAlchemy, Alembic, httpx, pytest, ruff, MySQL, Titan007 `JcResult.aspx` + `analysis/{id}cn.htm`。

---

## 文件结构

- Modify: `backend/app/scrapers/titan007/analysis.py`
  - 新增比分行解析与聚合函数。
  - 扩展 `TitanTeamStats` dataclass。
  - 保持现有 W/D/L、rank、fetch URL 行为不回归。

- Modify: `backend/tests/test_scrapers_titan007_analysis.py`
  - 先写失败测试覆盖比分解析、近期进失球、一球胜负、缺失比分跳过、旧字段不回归。

- Modify: `backend/app/models/team_stats.py`
  - 给 `sporttery_match_team_stats` 增加 nullable `SmallInteger` 聚合字段。

- Create: `backend/alembic/versions/0011_add_titan007_recent_score_features.py`
  - 增加/回滚新字段。
  - 注意当前已有 `0010_backtest_stake_and_details.py`，所以新 revision 必须是 `0011`，`down_revision='0010'`。

- Modify: `backend/app/scripts/backfill.py`
  - `_upsert_team_stats()` 写入新字段，保证未来常规 backfill 自动带新字段。

- Create: `backend/app/scripts/backfill_titan_recent_scores.py`
  - 专用历史补数脚本。
  - 按日期重拉 Titan007 `JcResult.aspx`，用比赛 `round` 精确映射 `titan007_match_id`，不做球队名模糊匹配。

- Modify: `backend/app/scripts/incremental_signal_validation.py`
  - 加载新字段。
  - 增加一球胜负、近期进失球相关候选规则分析。

- Modify: `backend/tests/test_incremental_signal_validation.py`
  - 测试新派生字段覆盖率和候选规则统计。

- Create: `docs/analysis/2026-04-26-v31-v4-recent-score-signal-validation.md`
  - 回填后生成新版中文分析报告。

---

## Task 1: 确认 Titan007 比分字段位置

**Files:**
- Read: `backend/app/scrapers/titan007/analysis.py`
- Temporary: `/tmp/inspect_titan_analysis_rows.py`
- Output: terminal diagnostic only

- [ ] **Step 1: 抓取一个真实 analysis 页面**

Run:

```bash
curl -L --compressed -A 'Mozilla/5.0' -e 'https://jc.titan007.com/' 'https://zq.titan007.com/analysis/2915933cn.htm' -o /tmp/titan_analysis_2915933.html
```

Expected:

```text
/tmp/titan_analysis_2915933.html 存在，且包含 h_data/a_data/h2_data/a2_data/v_data
```

- [ ] **Step 2: 打印各数组前 3 行和字段序号**

Create `/tmp/inspect_titan_analysis_rows.py`:

```python
from pathlib import Path

from app.scrapers.titan007.analysis import _extract_js_array, _SCRIPT_RE

html = Path('/tmp/titan_analysis_2915933.html').read_text(encoding='utf-8', errors='replace')
scripts = _SCRIPT_RE.findall(html)
big_script = next(s for s in scripts if 'h_data' in s)
for name in ['h_data', 'a_data', 'h2_data', 'a2_data', 'v_data']:
    rows = _extract_js_array(big_script, name) or []
    print(f'\n{name}: rows={len(rows)}')
    for row in rows[:3]:
        print('len=', len(row))
        for idx, value in enumerate(row):
            print(idx, repr(value))
        print('-' * 60)
```

Run:

```bash
PYTHONPATH=backend backend/.venv/bin/python /tmp/inspect_titan_analysis_rows.py
```

Expected:

```text
每个数组输出前 3 行字段序号，能人工确认全场比分字段和 row[12] 结果标记对应关系
```

- [ ] **Step 3: 停止线判断**

如果全场比分字段不能稳定确认，停止实施迁移和回填，只更新设计文档为“数据源缺口”。

如果能确认，记录字段位置并进入 Task 2。

---

## Task 2: TDD 扩展 Titan007 analysis 解析器

**Files:**
- Modify: `backend/tests/test_scrapers_titan007_analysis.py`
- Modify: `backend/app/scrapers/titan007/analysis.py`

- [ ] **Step 1: 写失败测试**

Add tests that construct rows with confirmed score fields. If confirmed structure is `row[9]=team_goals`, `row[10]=opponent_goals`, keep helper local to tests:

```python
def _score_row(flag: int | str, gf: int | str, ga: int | str) -> list:
    row = [0] * 13
    row[9] = gf
    row[10] = ga
    row[12] = flag
    return row
```

Add assertions:

```python
assert stats.home_recent_matches_count == 6
assert stats.home_recent_goals_for == 9
assert stats.home_recent_goals_against == 6
assert stats.home_recent_goal_diff == 3
assert stats.home_recent_win_by_1 == 1
assert stats.home_recent_win_by_2plus == 1
assert stats.home_recent_loss_by_1 == 1
assert stats.home_recent_loss_by_2plus == 1
assert stats.home_recent_draw_score_count == 2
assert stats.home_recent_low_scoring_count == 4
assert stats.home_recent_high_scoring_count == 1
```

Also assert away, home-home, away-away and h2h score fields.

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_scrapers_titan007_analysis.py -q
```

Expected:

```text
FAIL because TitanTeamStats has no recent score fields yet
```

- [ ] **Step 3: 最小实现解析器字段**

In `backend/app/scrapers/titan007/analysis.py`, add:

```python
@dataclass(frozen=True)
class TitanScoreAgg:
    matches_count: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_diff: int = 0
    win_by_1: int = 0
    win_by_2plus: int = 0
    loss_by_1: int = 0
    loss_by_2plus: int = 0
    draw_score_count: int = 0
    low_scoring_count: int = 0
    high_scoring_count: int = 0
```

Implement `_parse_score_from_row(row)` using the confirmed score field positions. It must return `None` when fields are missing or non-integer.

Implement `_score_agg(rows, limit=6)` and `_h2h_score_agg(rows, limit=6)`.

Extend `TitanTeamStats` with all fields listed in the design document and wire them in `parse_analysis()`.

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_scrapers_titan007_analysis.py -q
```

Expected:

```text
PASS
```

---

## Task 3: 数据库字段和常规 backfill 写入

**Files:**
- Modify: `backend/app/models/team_stats.py`
- Create: `backend/alembic/versions/0011_add_titan007_recent_score_features.py`
- Modify: `backend/app/scripts/backfill.py`

- [ ] **Step 1: 写模型字段**

Add nullable `SmallInteger` columns matching the design document. Example:

```python
home_recent_matches_count: Mapped[int | None] = mapped_column(
    SmallInteger, nullable=True, comment='主队近期可解析比分场次',
)
home_recent_goals_for: Mapped[int | None] = mapped_column(
    SmallInteger, nullable=True, comment='主队近期进球',
)
```

Repeat for away, home-home, away-away, h2h fields.

- [ ] **Step 2: 写 Alembic migration**

Create `backend/alembic/versions/0011_add_titan007_recent_score_features.py` with `op.add_column()` for each new field and downgrade in reverse order.

- [ ] **Step 3: 扩展 `_upsert_team_stats()` fields**

In `backend/app/scripts/backfill.py`, add all parsed fields to the `fields` dict. Existing rows should be updated, new rows inserted.

- [ ] **Step 4: 运行相关测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_backfill_titan_team_stats.py tests/test_scrapers_titan007_analysis.py -q
```

Expected:

```text
PASS
```

---

## Task 4: 专用历史补数脚本

**Files:**
- Create: `backend/app/scripts/backfill_titan_recent_scores.py`
- Test: optional targeted unit tests if pure helpers are extracted

- [ ] **Step 1: 实现脚本参数**

CLI:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.backfill_titan_recent_scores --start 2024-09-28 --end 2026-04-22 --delay 0.2
```

Parameters:

```text
--start YYYY-MM-DD
--end YYYY-MM-DD
--delay seconds, default 0.5
--dry-run optional
```

- [ ] **Step 2: 实现按业务日重建 Titan 映射**

For each date:

```python
_, titan_matches, _ = fetch_titan_day(client, target)
jc_to_titan = {item.jc_code: item.match_id for item in titan_matches if item.jc_code}
```

Load matches by `SportteryMatch.id` date prefix or `match_date` range, use `match.round` as jc code.

- [ ] **Step 3: 精确更新球队状态**

For each existing match:

```python
titan_id = jc_to_titan.get(match.round)
if titan_id is None:
    stats['missing_mapping'] += 1
    continue
if _upsert_team_stats(db, match, titan_id, client, delay=args.delay):
    stats['updated'] += 1
```

Commit once per day. Print totals: days, candidates, updated, missing_mapping, fetch_failed, parse_failed.

- [ ] **Step 4: 运行 dry-run**

Run:

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.backfill_titan_recent_scores --start 2024-09-28 --end 2024-09-30 --dry-run
```

Expected:

```text
输出 candidates 和可映射数量，不写库
```

---

## Task 5: 回填、验证和新版分析报告

**Files:**
- Modify: `backend/app/scripts/incremental_signal_validation.py`
- Modify: `backend/tests/test_incremental_signal_validation.py`
- Create: `docs/analysis/2026-04-26-v31-v4-recent-score-signal-validation.md`

- [ ] **Step 1: 应用迁移**

Run:

```bash
docker compose exec backend alembic upgrade head
```

Expected:

```text
数据库 schema 到 head，team_stats 表出现新增字段
```

- [ ] **Step 2: 执行历史补数**

Run:

```bash
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.backfill_titan_recent_scores --start 2024-09-28 --end 2026-04-22 --delay 0.2
```

Expected:

```text
大多数已有 team_stats 行被更新，新字段覆盖率接近旧 team_stats 覆盖率
```

- [ ] **Step 3: 抽样数据质量检查**

Run a SQL sample:

```bash
docker compose exec mysql mysql -uroot -prootpass sporttery_10x -e "select match_id,home_recent_matches_count,home_recent_goals_for,home_recent_goals_against,away_recent_matches_count,away_recent_goals_for,away_recent_goals_against from sporttery_match_team_stats where home_recent_matches_count is not null order by rand() limit 20;"
```

For this iteration, compare a smaller browser/manual sample first if time is limited; full 20-row browser validation is still the final acceptance target before model changes.

- [ ] **Step 4: 扩展只读分析脚本**

Add derived fields:

```text
home_recent_win_by_1_rate
away_recent_loss_by_1_rate
home_recent_gf_per_match
away_recent_ga_per_match
home_home_recent_win_by_1_rate
away_away_recent_loss_by_1_rate
h2h_one_goal_margin_rate
```

Add candidate rule families:

```text
hdraw_one_goal_shape
hdraw_defense_risk_filter
draw_low_scoring_balance
```

Do not change model scoring.

- [ ] **Step 5: 运行测试、ruff、报告**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_scrapers_titan007_analysis.py tests/test_incremental_signal_validation.py -q
cd backend && .venv/bin/python -m ruff check app/scrapers/titan007/analysis.py app/scripts/backfill_titan_recent_scores.py app/scripts/incremental_signal_validation.py tests/test_scrapers_titan007_analysis.py tests/test_incremental_signal_validation.py
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.incremental_signal_validation --start 2024-09-28 --end 2026-04-22 --report docs/analysis/2026-04-26-v31-v4-recent-score-signal-validation.md
```

Expected:

```text
pytest PASS
ruff PASS
新版中文分析报告生成
```

---

## 验收标准

- [ ] Titan007 比分字段位置已通过真实页面确认。
- [ ] 解析器测试先失败后通过。
- [ ] migration 增加 nullable 字段，不破坏旧数据。
- [ ] 专用回填脚本不依赖球队名模糊匹配。
- [ ] 历史新字段覆盖率可量化。
- [ ] 新版分析报告明确回答: 新字段是否值得进入 V3.1/V4。
- [ ] 当前 v2/v3 推荐逻辑未被修改。

## 自检

- 文档为中文。
- 计划不直接引导模型改参。
- 每个阶段都有可停止点。
- 兼容当前已有 `0010` migration，使用 `0011`。
