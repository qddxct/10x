# 删除中间模型运行逻辑实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除会创建或默认使用中间模型的运行代码，让干净环境只围绕 `default` 与 `empirical-v32-filtered-candidate` 运转。

**Architecture:** 收敛 seed、score/backtest 脚本、ScoringService 策略分支和测试数据；保留 V3.2/V3.4 研究能力，不删除历史研究文档。

**Tech Stack:** FastAPI, SQLAlchemy, Python CLI scripts, pytest, Next.js, Vitest。

---

## Task 1: Seed 与运行策略收敛

**Files:**
- Modify: `backend/app/scripts/seed.py`
- Modify: `backend/app/engine/service.py`
- Modify: `backend/app/engine/scoring.py`
- Modify: `backend/tests/test_seed.py`
- Modify: `backend/tests/test_engine_service.py`
- Modify: `backend/tests/test_engine_scoring.py`

- [x] 删除 `ensure_empirical_v3_config()`。
- [x] 删除 `strategy=empirical_v3` 服务分支。
- [x] 删除 v3 专用测试。
- [x] 保留 default 与 V3.2 相关能力。

## Task 2: CLI 默认模型收敛

**Files:**
- Modify: `backend/app/scripts/score_history.py`
- Modify: `backend/app/scripts/backtest_model_windows.py`
- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`
- Modify: `backend/tests/test_v31_combination_candidate_backtest.py`

- [x] `score_history.py` 文档示例改为 `default`，并注明 V3.2 由候选脚本生成。
- [x] `backtest_model_windows.py` 默认模型只比较 default 和 V3.2。
- [x] V3.2 候选脚本默认 version 改为 v32。
- [x] 禁止脚本创建 `empirical-v31-combination-candidate`。

## Task 3: 前端测试和文档对齐

**Files:**
- Modify: `frontend/tests/backtest-client.test.tsx`
- Modify: `docs/analysis/2026-04-26-clean-environment-reset.md`
- Create: `docs/analysis/CURRENT_MODEL_RUNTIME.md`

- [x] 前端测试示例模型改为 `empirical-v32-filtered-candidate`。
- [x] 当前运行模型文档写明只保留 default 与 V3.2。
- [x] 清理记录补充代码逻辑已收敛。

## Task 4: 验证

- [x] `rg "empirical-v2-d104-h104-clean|empirical-v3-candidate|empirical-v31-combination-candidate" backend/app frontend` 不再返回运行态引用。
- [x] 运行后端相关 pytest。
- [x] 运行前端相关 vitest/lint。
