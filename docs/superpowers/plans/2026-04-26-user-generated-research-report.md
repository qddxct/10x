# 用户自助生成区间研究报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在 `/combo-reports` 页面支持用户选择时间区间，一键覆盖生成该区间 V3.2 历史 score，并生成 V3.4 二串一研究报告后跳转详情页。

**Architecture:** 后端新增 `app.research.generator` 服务，负责复用 V3.2 score 生成和 V3.4 组合报告生成逻辑；`app.api.research` 新增同步生成接口。前端新增研究报告生成表单组件，调用 API 后跳转到新报告详情页。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Next.js App Router, React, Vitest, Testing Library, Playwright。

---

## File Structure

- Create: `backend/app/research/generator.py`
  - 封装用户自助生成报告的核心服务。
  - 不直接依赖 HTTP；可被 API 和未来任务队列复用。

- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`
  - 抽出 `generate_v32_scores()`，供 CLI 和 API 复用。
  - 保持现有 CLI 行为不变。

- Modify: `backend/app/scripts/v34_combo_selector.py`
  - 抽出 `generate_combo_selector_report()`，供 CLI 和 API 复用。
  - 保持现有 CLI 行为不变。

- Modify: `backend/app/schemas/research.py`
  - 新增 `ResearchGenerateRequest` 和 `ResearchGenerateResponse`。

- Modify: `backend/app/api/research.py`
  - 新增 `POST /api/research/generate-combo-report`。

- Modify: `backend/tests/test_research_api.py`
  - 增加 API 正常生成、非法日期、候选不足等测试。

- Modify: `frontend/lib/research/types.ts`
  - 新增生成请求和响应类型。

- Modify: `frontend/lib/research/api.ts`
  - 新增 `generateComboResearchReport()`。

- Create: `frontend/app/combo-reports/generate-report-form.tsx`
  - 新增页面表单。
  - 默认隐藏随机种子为高级参数或简洁说明。

- Modify: `frontend/app/combo-reports/combo-reports-client.tsx`
  - 接入表单，成功后跳转详情页。

- Modify: `frontend/app/combo-reports/combo-reports.module.css`
  - 增加表单样式。

- Modify: `frontend/tests/research-api.test.ts`
  - 增加 API 封装测试。

- Modify: `frontend/tests/combo-reports-client.test.tsx`
  - 增加页面表单生成成功和失败测试。

- Modify: `docs/analysis/CURRENT_MODEL_RUNTIME.md`
  - 补充网页自助生成报告的使用方式。

---

## Task 1: 后端生成服务测试先行

**Files:**
- Create: `backend/app/research/generator.py`
- Modify: `backend/tests/test_research_api.py`

- [x] **Step 1: 写生成服务的 API 级失败测试**

在 `backend/tests/test_research_api.py` 追加测试：

```python
def test_generate_combo_report_rejects_invalid_date_range(ctx):
    client, _session = ctx
    headers = _auth(client, "13800030004")
    payload = {
        "date_from": "2026-04-22",
        "date_to": "2026-03-22",
        "model_name": "empirical-v32-filtered-candidate",
        "random_trials": 1000,
        "random_seed": 20260426,
    }

    r = client.post("/api/research/generate-combo-report", json=payload, headers=headers)

    assert r.status_code == 400
    assert "date_from" in r.json()["detail"]
```

- [x] **Step 2: 写生成服务的成功路径 API 测试**

在 `backend/tests/test_research_api.py` 新增一个最小数据夹具函数，插入两场完赛且均可作为 V3.2 候选的比赛。测试调用接口后应返回 `run_id`，并能读取详情。

```python
def test_generate_combo_report_creates_run(ctx):
    client, session = ctx
    _seed_v32_candidate_dataset(session)
    headers = _auth(client, "13800030005")
    payload = {
        "date_from": "2026-01-01",
        "date_to": "2026-01-03",
        "model_name": "empirical-v32-filtered-candidate",
        "random_trials": 100,
        "random_seed": 20260426,
    }

    r = client.post("/api/research/generate-combo-report", json=payload, headers=headers)

    assert r.status_code == 201
    body = r.json()
    assert body["run_id"] > 0
    assert body["score_summary"]["recommended_scores"] >= 2
    assert body["research_summary"]["best_strategy"]

    detail = client.get(f"/api/research/{body['run_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["summary_json"]["model_name"] == "empirical-v32-filtered-candidate"
```

- [x] **Step 3: 运行测试确认失败**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_api.py::test_generate_combo_report_rejects_invalid_date_range tests/test_research_api.py::test_generate_combo_report_creates_run -q
```

Expected: FAIL，因为接口和服务尚未实现。

---

## Task 2: 抽出 V3.2 score 生成函数

**Files:**
- Modify: `backend/app/scripts/v31_combination_candidate_backtest.py`
- Test: `backend/tests/test_v31_combination_candidate_backtest.py`

- [x] **Step 1: 新增可复用返回类型**

在 `backend/app/scripts/v31_combination_candidate_backtest.py` 中新增 dataclass：

```python
@dataclass(frozen=True)
class V32ScoreGenerationResult:
    model_config_id: int
    rows: int
    candidates: int
    portfolio: int
    scored_matches: int
    recommended_scores: int
    draw_scores: int
    handicap_draw_scores: int
    replaced_old_scores: int
    report_path: str | None
    csv_path: str | None
```

- [x] **Step 2: 抽出函数 `generate_v32_scores`**

在 CLI `main()` 上方新增函数：

```python
def generate_v32_scores(
    db: Session,
    *,
    start: date,
    end: date,
    report_path: Path | None = None,
    csv_path: Path | None = None,
) -> V32ScoreGenerationResult:
    version = candidate_version("v32")
    rows = load_rows(db, start=start, end=end)
    candidates = evaluate_rules(rows, version.rules)
    portfolio = select_portfolio(candidates)
    cfg = ensure_candidate_model_config(db, model_name=version.model_name)
    write_summary = write_scores(db, cfg=cfg, portfolio=portfolio, start=start, end=end)
    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("\n".join(csv_lines(candidates)), encoding="utf-8-sig")
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = render_report(
            rows=rows,
            candidates=candidates,
            portfolio=portfolio,
            start=start,
            end=end,
            detail_path=str(csv_path or ""),
            write_summary=write_summary,
            title=version.title,
            model_name=version.model_name,
        )
        report_path.write_text(report, encoding="utf-8")
    return V32ScoreGenerationResult(
        model_config_id=cfg.id,
        rows=len(rows),
        candidates=len(candidates),
        portfolio=len(portfolio),
        scored_matches=int(write_summary["scored_matches"]),
        recommended_scores=int(write_summary["recommended_scores"]),
        draw_scores=int(write_summary["draw_scores"]),
        handicap_draw_scores=int(write_summary["handicap_draw_scores"]),
        replaced_old_scores=int(write_summary["replaced_old_scores"]),
        report_path=str(report_path) if report_path else None,
        csv_path=str(csv_path) if csv_path else None,
    )
```

- [x] **Step 3: 改造 CLI main 复用函数**

将 `main()` 内部重复逻辑替换为 `generate_v32_scores(...)`，保留原有 print 输出字段：

```python
result = generate_v32_scores(
    db,
    start=start,
    end=end,
    report_path=Path(args.report),
    csv_path=Path(args.csv),
)
print(
    f"rows={result.rows} candidates={result.candidates} "
    f"portfolio={result.portfolio} scored={result.scored_matches} "
    f"model_config_id={result.model_config_id} report={result.report_path} csv={result.csv_path}"
)
```

- [x] **Step 4: 运行现有候选脚本测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_v31_combination_candidate_backtest.py -q
```

Expected: PASS。

---

## Task 3: 抽出 V3.4 二串一报告生成函数

**Files:**
- Modify: `backend/app/scripts/v34_combo_selector.py`
- Test: `backend/tests/test_research_api.py`

- [x] **Step 1: 新增返回类型**

在 `backend/app/scripts/v34_combo_selector.py` 新增 dataclass：

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ComboSelectorReportResult:
    run_id: int
    candidates: int
    combo_summaries: int
    random_baselines: int
    report_path: str
    tickets_csv: str
    random_csv: str
    summary: dict[str, Any]
```

- [x] **Step 2: 抽出 `generate_combo_selector_report`**

新增函数：

```python
def generate_combo_selector_report(
    db,
    *,
    model: str,
    start: date,
    end: date,
    random_trials: int = 1000,
    random_seed: int = 20260426,
    report_path: Path,
    replace: bool = False,
) -> ComboSelectorReportResult:
    tickets_csv = report_path.with_name(report_path.stem + "-tickets.csv")
    random_csv = report_path.with_name(report_path.stem + "-random.csv")
    model_config_id = get_model_config_id(db, model)
    if replace:
        replace_existing_run(db, name=RUN_NAME)
    candidates = load_model_candidates(db, model_config_id=model_config_id, start=start, end=end)
    if len(candidates) < 2:
        raise ValueError("Not enough candidates to build combo report")
    market_candidates = load_market_candidates(db, start=start, end=end)
    # Move existing main loop here unchanged.
    return ComboSelectorReportResult(...)
```

实现时把当前 `main()` 里从 `candidates = ...` 到 `save_research_run(...)` 的逻辑搬进函数，`main()` 只负责解析参数和 print。

- [x] **Step 3: CLI main 复用函数**

`main()` 改为：

```python
with SessionLocal() as db:
    result = generate_combo_selector_report(
        db,
        model=args.model,
        start=start,
        end=end,
        random_trials=args.random_trials,
        random_seed=args.random_seed,
        report_path=report_path,
        replace=args.replace,
    )
print(
    f"run_id={result.run_id} candidates={result.candidates} "
    f"combo_summaries={result.combo_summaries} random_baselines={result.random_baselines}"
)
```

- [x] **Step 4: 运行研究相关测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_combo.py tests/test_research_combo_selector.py tests/test_research_random_baseline.py -q
```

Expected: PASS。

---

## Task 4: 新增后端 generator 服务和 API

**Files:**
- Create: `backend/app/research/generator.py`
- Modify: `backend/app/schemas/research.py`
- Modify: `backend/app/api/research.py`
- Test: `backend/tests/test_research_api.py`

- [x] **Step 1: 新增 Pydantic schema**

在 `backend/app/schemas/research.py` 增加：

```python
from pydantic import Field

class ResearchGenerateRequest(BaseModel):
    date_from: date
    date_to: date
    model_name: str = "empirical-v32-filtered-candidate"
    random_trials: int = Field(default=1000, ge=100, le=5000)
    random_seed: int = Field(default=20260426, ge=1, le=999999999)

class ResearchScoreSummaryRead(BaseModel):
    rows: int
    candidates: int
    portfolio: int
    scored_matches: int
    recommended_scores: int
    draw_scores: int
    handicap_draw_scores: int
    replaced_old_scores: int

class ResearchGenerateResponse(BaseModel):
    run_id: int
    report_path: str
    score_summary: ResearchScoreSummaryRead
    research_summary: dict[str, Any]
```

- [x] **Step 2: 新增 generator 服务**

创建 `backend/app/research/generator.py`：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import ModelConfig
from app.scripts.v31_combination_candidate_backtest import generate_v32_scores
from app.scripts.v34_combo_selector import generate_combo_selector_report

DEFAULT_RESEARCH_MODEL = "empirical-v32-filtered-candidate"
GENERATED_REPORT_DIR = Path("docs/analysis/generated")

@dataclass(frozen=True)
class GeneratedResearchReport:
    run_id: int
    report_path: str
    score_summary: dict[str, int]
    research_summary: dict[str, Any]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def generate_user_combo_report(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    model_name: str = DEFAULT_RESEARCH_MODEL,
    random_trials: int = 1000,
    random_seed: int = 20260426,
) -> GeneratedResearchReport:
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if db.query(ModelConfig).filter(ModelConfig.name == model_name).one_or_none() is None:
        raise LookupError("ModelConfig not found")
    stamp = _timestamp()
    prefix = f"v34-combo-selector-{date_from.isoformat()}-{date_to.isoformat()}-{stamp}"
    score_result = generate_v32_scores(
        db,
        start=date_from,
        end=date_to,
        report_path=GENERATED_REPORT_DIR / f"v32-score-{date_from.isoformat()}-{date_to.isoformat()}-{stamp}.md",
        csv_path=GENERATED_REPORT_DIR / f"v32-score-{date_from.isoformat()}-{date_to.isoformat()}-{stamp}.csv",
    )
    if score_result.rows == 0:
        raise ValueError("No finished matches in selected range")
    if score_result.recommended_scores < 2:
        raise ValueError("Not enough candidates to build combo report")
    report_result = generate_combo_selector_report(
        db,
        model=model_name,
        start=date_from,
        end=date_to,
        random_trials=random_trials,
        random_seed=random_seed,
        report_path=GENERATED_REPORT_DIR / f"{prefix}.md",
        replace=False,
    )
    return GeneratedResearchReport(
        run_id=report_result.run_id,
        report_path=report_result.report_path,
        score_summary={
            "rows": score_result.rows,
            "candidates": score_result.candidates,
            "portfolio": score_result.portfolio,
            "scored_matches": score_result.scored_matches,
            "recommended_scores": score_result.recommended_scores,
            "draw_scores": score_result.draw_scores,
            "handicap_draw_scores": score_result.handicap_draw_scores,
            "replaced_old_scores": score_result.replaced_old_scores,
        },
        research_summary=report_result.summary,
    )
```

- [x] **Step 3: 新增 API endpoint**

在 `backend/app/api/research.py` imports 加入：

```python
from fastapi import status
from app.research.generator import generate_user_combo_report
from app.schemas.research import ResearchGenerateRequest, ResearchGenerateResponse
```

新增路由，必须放在 `/{run_id}` 路由之前：

```python
@router.post(
    "/generate-combo-report",
    response_model=ResearchGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_combo_report(
    payload: ResearchGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ResearchGenerateResponse:
    try:
        result = generate_user_combo_report(
            db,
            date_from=payload.date_from,
            date_to=payload.date_to,
            model_name=payload.model_name,
            random_trials=payload.random_trials,
            random_seed=payload.random_seed,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResearchGenerateResponse(
        run_id=result.run_id,
        report_path=result.report_path,
        score_summary=result.score_summary,
        research_summary=result.research_summary,
    )
```

- [x] **Step 4: 运行 API 测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_api.py -q
```

Expected: PASS。

---

## Task 5: 前端 API 封装和表单测试

**Files:**
- Modify: `frontend/lib/research/types.ts`
- Modify: `frontend/lib/research/api.ts`
- Modify: `frontend/tests/research-api.test.ts`

- [x] **Step 1: 新增前端类型**

在 `frontend/lib/research/types.ts` 增加：

```ts
export interface GenerateComboResearchPayload {
  date_from: string
  date_to: string
  model_name?: string
  random_trials?: number
  random_seed?: number
}

export interface GenerateComboResearchResponse {
  run_id: number
  report_path: string
  score_summary: {
    rows: number
    candidates: number
    portfolio: number
    scored_matches: number
    recommended_scores: number
    draw_scores: number
    handicap_draw_scores: number
    replaced_old_scores: number
  }
  research_summary: ResearchSummaryJson
}
```

- [x] **Step 2: 新增 API 函数**

在 `frontend/lib/research/api.ts` 增加：

```ts
import type {
  GenerateComboResearchPayload,
  GenerateComboResearchResponse,
  ResearchRun,
  ResearchRunDetail,
  ResearchTicket,
  ResearchTicketGroup
} from './types'

export async function generateComboResearchReport(
  payload: GenerateComboResearchPayload
): Promise<GenerateComboResearchResponse> {
  return apiFetch<GenerateComboResearchResponse>('/api/research/generate-combo-report', {
    method: 'POST',
    body: payload
  })
}
```

- [x] **Step 3: 新增 API 测试**

在 `frontend/tests/research-api.test.ts` 增加：

```ts
it('generates combo research report', async () => {
  const fetchMock = mockFetchJson(201, { run_id: 10, report_path: 'docs/analysis/x.md' })
  const res = await generateComboResearchReport({
    date_from: '2026-01-01',
    date_to: '2026-01-31',
    random_trials: 1000,
    random_seed: 20260426
  })
  expect(res.run_id).toBe(10)
  expect(String(fetchMock.mock.calls[0][0])).toContain('/api/research/generate-combo-report')
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST' })
})
```

- [x] **Step 4: 运行前端 API 测试**

Run:

```bash
cd frontend && npm test -- research-api
```

Expected: PASS。

---

## Task 6: 前端生成表单和页面接入

**Files:**
- Create: `frontend/app/combo-reports/generate-report-form.tsx`
- Modify: `frontend/app/combo-reports/combo-reports-client.tsx`
- Modify: `frontend/app/combo-reports/combo-reports.module.css`
- Modify: `frontend/tests/combo-reports-client.test.tsx`

- [x] **Step 1: 写页面成功测试**

修改 `frontend/tests/combo-reports-client.test.tsx` mock：

```ts
vi.mock('@/lib/research/api', () => ({
  getLatestResearchRun: vi.fn(),
  generateComboResearchReport: vi.fn()
}))
```

新增测试：

```ts
it('generates a report and redirects to detail page', async () => {
  mockLatestResearch.mockResolvedValue(null)
  mockGenerate.mockResolvedValue({
    run_id: 10,
    report_path: 'docs/analysis/generated/x.md',
    score_summary: {
      rows: 10,
      candidates: 4,
      portfolio: 4,
      scored_matches: 4,
      recommended_scores: 4,
      draw_scores: 3,
      handicap_draw_scores: 1,
      replaced_old_scores: 0
    },
    research_summary: { best_strategy: 'frequency_selector' }
  })

  render(<ComboReportsClient />)
  await waitFor(() => expect(mockLatestResearch).toHaveBeenCalled())
  fireEvent.change(screen.getByLabelText('开始日期'), { target: { value: '2026-01-01' } })
  fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2026-01-31' } })
  fireEvent.click(screen.getByRole('button', { name: '生成报告' }))

  await waitFor(() => expect(mockGenerate).toHaveBeenCalled())
  expect(mockPush).toHaveBeenCalledWith('/combo-reports/10')
})
```

- [x] **Step 2: 新建表单组件**

创建 `frontend/app/combo-reports/generate-report-form.tsx`：

```tsx
'use client'

import { FormEvent, useState } from 'react'

import type { GenerateComboResearchResponse } from '@/lib/research/types'

import styles from './combo-reports.module.css'

interface Props {
  onGenerate: (payload: {
    date_from: string
    date_to: string
    model_name: string
    random_trials: number
    random_seed: number
  }) => Promise<GenerateComboResearchResponse>
}

export function GenerateReportForm({ onGenerate }: Props) {
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [randomTrials, setRandomTrials] = useState(1000)
  const [randomSeed, setRandomSeed] = useState(20260426)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!dateFrom || !dateTo) {
      setError('请选择开始日期和结束日期')
      return
    }
    try {
      setLoading(true)
      await onGenerate({
        date_from: dateFrom,
        date_to: dateTo,
        model_name: 'empirical-v32-filtered-candidate',
        random_trials: randomTrials,
        random_seed: randomSeed
      })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className={styles.generatorCard}>
      <div>
        <div className={styles.sectionTitle}>生成研究报告</div>
        <p className={styles.hint}>选择历史区间后，系统会重算 V3.2 候选 score 并生成二串一研究报告。</p>
      </div>
      {error ? <div className={styles.errorBanner}>报告生成失败：{error}</div> : null}
      <form className={styles.generatorForm} onSubmit={handleSubmit}>
        <label>
          开始日期
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          结束日期
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <label>
          模型
          <input value="empirical-v32-filtered-candidate" disabled />
        </label>
        <button type="button" className={styles.secondaryButton} onClick={() => setShowAdvanced(!showAdvanced)}>
          {showAdvanced ? '收起高级参数' : '展开高级参数'}
        </button>
        {showAdvanced ? (
          <>
            <label>
              随机试验次数
              <input type="number" min={100} max={5000} value={randomTrials} onChange={(e) => setRandomTrials(Number(e.target.value))} />
            </label>
            <label>
              随机种子
              <input type="number" min={1} max={999999999} value={randomSeed} onChange={(e) => setRandomSeed(Number(e.target.value))} />
            </label>
          </>
        ) : null}
        <button className={styles.primaryButton} disabled={loading} type="submit">
          {loading ? '正在生成研究报告...' : '生成报告'}
        </button>
      </form>
    </section>
  )
}
```

- [x] **Step 3: 接入页面跳转**

在 `frontend/app/combo-reports/combo-reports-client.tsx`：

```tsx
import { useRouter } from 'next/navigation'
import { generateComboResearchReport, getLatestResearchRun } from '@/lib/research/api'
import { GenerateReportForm } from './generate-report-form'

const router = useRouter()

<GenerateReportForm
  onGenerate={async (payload) => {
    const result = await generateComboResearchReport(payload)
    router.push(`/combo-reports/${result.run_id}`)
    return result
  }}
/>
```

表单放在 header 下方、错误提示和最新报告摘要上方。

- [x] **Step 4: 补充样式**

在 `frontend/app/combo-reports/combo-reports.module.css` 增加：

```css
.generatorCard {
  border: 1px solid rgb(51 65 85 / 0.9);
  border-radius: 0.9rem;
  padding: 1rem;
  background: linear-gradient(135deg, rgb(15 23 42 / 0.95), rgb(8 47 73 / 0.45));
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.generatorForm {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.8rem;
  align-items: end;
}

.generatorForm label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: rgb(203 213 225);
  font-size: 0.82rem;
}

.generatorForm input {
  border: 1px solid rgb(51 65 85);
  border-radius: 0.55rem;
  background: rgb(2 6 23 / 0.72);
  color: rgb(226 232 240);
  padding: 0.65rem 0.7rem;
}

.primaryButton,
.secondaryButton {
  border: 1px solid rgb(20 184 166 / 0.65);
  border-radius: 0.6rem;
  padding: 0.68rem 0.9rem;
  color: rgb(240 253 250);
  background: rgb(13 148 136 / 0.28);
  cursor: pointer;
}

.secondaryButton {
  border-color: rgb(71 85 105);
  background: rgb(15 23 42 / 0.7);
}

.primaryButton:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
```

- [x] **Step 5: 运行前端测试**

Run:

```bash
cd frontend && npm test -- combo-reports-client research-api
```

Expected: PASS。

---

## Task 7: 文档、集成验证和浏览器验证

**Files:**
- Modify: `docs/analysis/CURRENT_MODEL_RUNTIME.md`

- [x] **Step 1: 更新运行态文档**

在 `docs/analysis/CURRENT_MODEL_RUNTIME.md` 增加章节：

```markdown
## 网页自助生成研究报告

入口：`/combo-reports`

用户选择开始日期和结束日期后，系统会：

1. 覆盖生成该区间 `empirical-v32-filtered-candidate` 的历史 score。
2. 生成 V3.4 二串一研究报告。
3. 写入 `model_research_runs` 和 `model_research_artifacts`。
4. 自动跳转到报告详情页。

随机试验次数默认 `1000`，随机种子默认 `20260426`。随机种子只影响随机对照组，不影响模型本身。
```

- [x] **Step 2: 后端完整验证**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_research_api.py tests/test_v31_combination_candidate_backtest.py tests/test_research_combo.py tests/test_research_combo_selector.py tests/test_research_random_baseline.py -q
cd backend && .venv/bin/python -m ruff check app/api/research.py app/research/generator.py app/scripts/v31_combination_candidate_backtest.py app/scripts/v34_combo_selector.py app/schemas/research.py tests/test_research_api.py
```

Expected: pytest PASS, ruff PASS。

- [x] **Step 3: 前端完整验证**

Run:

```bash
cd frontend && npm test -- combo-reports-client research-api research-detail-client
cd frontend && npm run lint
```

Expected: tests PASS, lint PASS。

- [x] **Step 4: 本地 API smoke test**

Run:

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800000000","password":"Admin@1234"}' \
  | backend/.venv/bin/python -c 'import sys,json; print(json.load(sys.stdin)["token"])')

curl -sS -X POST http://localhost:8000/api/research/generate-combo-report \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"date_from":"2026-03-22","date_to":"2026-04-22","random_trials":100,"random_seed":20260426}' \
  | backend/.venv/bin/python -m json.tool
```

Expected: 返回 `run_id`、`score_summary`、`research_summary`。

- [x] **Step 5: 浏览器验证**

使用 Playwright 或 in-app browser：

1. 打开 `http://localhost:3000/combo-reports`。
2. 登录。
3. 输入 `2026-03-22` 到 `2026-04-22`。
4. 点击 `生成报告`。
5. 验证跳转到 `/combo-reports/{run_id}`。
6. 验证详情页包含 `随机对照`、金额、二串一明细和让平让球数。

- [x] **Step 6: 提交实现**

Run:

```bash
git add backend/app/research/generator.py backend/app/scripts/v31_combination_candidate_backtest.py backend/app/scripts/v34_combo_selector.py backend/app/schemas/research.py backend/app/api/research.py backend/tests/test_research_api.py frontend/lib/research/types.ts frontend/lib/research/api.ts frontend/app/combo-reports/generate-report-form.tsx frontend/app/combo-reports/combo-reports-client.tsx frontend/app/combo-reports/combo-reports.module.css frontend/tests/research-api.test.ts frontend/tests/combo-reports-client.test.tsx docs/analysis/CURRENT_MODEL_RUNTIME.md docs/superpowers/plans/2026-04-26-user-generated-research-report.md
git commit -m "feat: generate combo research reports from page"
```

Expected: commit succeeds。
