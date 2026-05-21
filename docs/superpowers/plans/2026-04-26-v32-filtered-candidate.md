# V3.2 过滤器候选模型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 V3.1 结果实现 `empirical-v32-filtered-candidate`，写入独立 inactive 模型历史 score，并生成回测报告/CSV/页面可见回测记录。

**Architecture:** 复用 V3.1 候选脚本的加载、派生特征、报告、score 写入框架，新增 V3.2 规则层。V3.2 只保留普通平正收益方向并增加价格过滤，同时保留 HDRAW_A 核心让平规则；不接今日推荐，不改变 active 模型。

**Tech Stack:** Python 3.11, SQLAlchemy, pytest, ruff, MySQL, Markdown/CSV。

---

## 文件结构

- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`
  - 新增 V3.2 常量、规则函数、CLI `--version v31|v32` 或独立入口参数。
  - 支持 `empirical-v32-filtered-candidate` 模型配置与 score 写入。

- Modify: `backend/tests/test_v31_combination_candidate_backtest.py`
  - 新增 V3.2 规则命中、score 分数、模型名测试。

- Create: `docs/analysis/2026-04-26-v32-filtered-candidate-backtest.md`
  - 脚本生成。

- Create: `docs/analysis/v32-filtered-candidates.csv`
  - 脚本生成。

## Task 1: 扩展版本配置

- [ ] 新增 `CandidateVersion` 配置，包含模型名、报告标题、规则列表、score 映射。
- [ ] 保留 V3.1 默认行为不变。
- [ ] 新增 `--version` 参数，默认 `v31`，可传 `v32`。

## Task 2: 新增 V3.2 规则测试

测试要求:

```python
def test_v32_draw_rule_requires_positive_v31_draw_rule_and_price_floor():
    # DRAW_V31_B + had_d >= 3.10 命中
    # DRAW_V31_B + had_d < 3.10 不命中
    # DRAW_V31_C 即使命中也不进入 V3.2


def test_v32_hdraw_rule_keeps_only_a0_a1_a2():
    # HDRAW_V31_A0 命中 V3.2
    # HDRAW_V31_B 不进入 V3.2


def test_v32_model_config_name_and_score_values():
    # model name = empirical-v32-filtered-candidate
    # draw total_score = 108
    # hdraw total_score = 116
```

## Task 3: 实现 V3.2 规则

规则:

```text
DRAW_V32_CORE:
  (DRAW_V31_D or DRAW_V31_B) and had_d >= 3.10

HDRAW_V32_CORE:
  HDRAW_V31_A0 or HDRAW_V31_A1 or HDRAW_V31_A2
```

全局优先级:

```text
HDRAW_V32_CORE > DRAW_V32_CORE
```

score:

```text
HDRAW_V32_CORE: total_score=116, kelly_pct=0.0150, bet_type=handicap_draw
DRAW_V32_CORE: total_score=108, kelly_pct=0.0100, bet_type=draw
```

## Task 4: 运行测试和生成 V3.2 score

Commands:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
cd backend && .venv/bin/python -m ruff check app/scripts/v31_combination_candidate_backtest.py tests/test_v31_combination_candidate_backtest.py
MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308 MYSQL_DATABASE=sporttery_10x MYSQL_USER=sporttery MYSQL_PASSWORD=sporttery_pass PYTHONPATH=backend backend/.venv/bin/python -m app.scripts.v31_combination_candidate_backtest --version v32 --start 2024-09-28 --end 2026-04-22 --replace --report docs/analysis/2026-04-26-v32-filtered-candidate-backtest.md --csv docs/analysis/v32-filtered-candidates.csv
```

Expected:

```text
pytest PASS
ruff PASS
v32 scored rows between 200 and 800
```

## Task 5: 创建回测页面记录

运行 V3.2 全样本和 90 天窗口回测，生成 `backtest_sessions`。

验收:

```text
历史回测页面能看到 empirical-v32-filtered-candidate
列表中出现全样本和 90 天窗口记录
```

## Task 6: 汇总结论

报告需要明确:

1. V3.2 与 V3.1 的 ROI、下注数、窗口稳定性对比。
2. 普通平过滤后是否转正。
3. 让平是否仍贡献正收益。
4. 下一步是否继续 V3.3 或补新数据。

## 自检

- 文档中文。
- 不接今日推荐。
- 不覆盖 V3.1。
- 通过页面查看结果。
