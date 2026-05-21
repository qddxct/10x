# 设计文档 Review：V1.0 → 实际实现（2026-04-21）

**基线文档**：`docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md` V1.0
**对标代码**：`fix/p6-followup` 分支 HEAD（P1-P6 + P6 follow-up 已合并）
**方法**：按设计文档九个章节逐节核对，记录 ✅ 已实现 / 🟡 部分偏差 / ❌ 未实现 / 🆕 实现但文档未记录。

> **📌 2026-04-27 补注**：本 review 是 2026-04-21 的**历史快照**，其中标 ❌ 的 `/model`、`/review` UI 已在 **P7** 全部落地；标记 🕐 延后的复盘乐观锁（R-4）、激活即时重算（R-3）、`ModelConfig.name` 唯一（隐式）已在 **P8 H1** 补齐。后续进展见 `docs/superpowers/plans/2026-04-21-p7-model-config-review.md`、`2026-04-27-p8-tech-debt.md` 与 PRD V1.1。本文档保留原貌，仅供"当时做了什么选择"的考古用途。

---

## 总览

| 章节 | 符合度 | 主要问题数 |
| --- | --- | --- |
| 一 · 项目目标 | ✅ | 0 |
| 二 · 整体架构 | ✅ | 0 |
| 三 · 数据源 | 🟡 | 1 |
| 四 · 数据库结构 | 🟡 | 7 |
| 五 · 评分系统 | 🟡 | 2 |
| 六 · 功能模块 | 🟡 | 2 尚未上线 |
| 七 · 技术栈 | 🟡 | 1 |
| 八 · 项目结构 | 🟡 | 1 |
| 九 · 后续可扩展 | ✅ | 0 |

**结论**：实现覆盖了绝大部分设计要求；主要偏差在于（1）**数据库字段命名与数据类型**出现若干漂移；（2）**`/model`、`/admin` 用户管理、复盘 UI** 未开发（P7 规划中）；（3）设计文档未记录的新表 / 新字段（`scrape_logs`、`backtest_sessions.mode/kelly_*/equity_curve` 等）需要回写设计文档。

---

## 一 · 项目目标 ✅

三层目标（模型构建、回测、实盘）全部落地，与文档一致。

---

## 二 · 整体架构 ✅

| 设计 | 实现 |
| --- | --- |
| Next.js 前端 | ✅ Next.js 14 App Router |
| FastAPI 后端 | ✅ |
| 爬虫模块 | ✅ `app/scrapers/sporttery`、`app/scrapers/titan007` |
| 模型引擎 | ✅ `app/engine/scoring.py` / `backtest.py` / `kelly.py` |
| 用户认证 | ✅ `app/api/auth.py` JWT |
| APScheduler | ✅ `app/scheduler/main.py` + jobs |
| MySQL | ✅ |
| 三条数据流（抓取 / 决策 / 回测） | ✅ |

---

## 三 · 数据源 🟡（1）

### 偏差 S-1 · titan007 的球队状态子模块未启用

设计文档表格将「球队状态」归为 titan007；**实际代码**把 `team_stats` 从 **体彩官网**抓取（`app/scrapers/sporttery/team_stats.py`），参数是 `sporttery_match_id`。titan007 只抓欧赔/亚盘/大小球。

- **影响**：team_stats 依赖体彩赛程先入库，两个数据源强耦合；titan007 的球队状态维度暂未使用。
- **建议**：更新设计文档数据源表，把「球队状态」标注为 sporttery，或补做 titan007 同源采集。

---

## 四 · 数据库结构 🟡（7 处偏差）

### D-1 · `matches.date` → 实际 `match_date`（DateTime）

| 设计文档 | 实现 |
| --- | --- |
| `date` | `match_date` |
| （未指定类型） | `DateTime NOT NULL`（不仅日期，含开球时刻） |

**影响**：所有 API/前端按 `match_date` 命名；文档的 ER 示意不更新会误导新成员。

### D-2 · `matches` 多出 `created_at/updated_at`、`status` 为 enum

- 所有业务表都混入了 `TimestampMixin`（`created_at`/`updated_at`）。
- `status` 是 `Enum('scheduled','in_progress','finished')`，与文档中文值「待开/进行中/已结束」语义一致但命名不同。

### D-3 · `match_odds` 细节差异

- 设计文档未标字段类型；实现统一为 `DECIMAL(6,3)` / `DECIMAL(4,2)`
- 新增 `asian_handicap String(32)` 语义取值（"平手" / "平半" / "半球" / ...）；设计文档表格里只是作为说明列出
- `total_goals` 实际是 `DECIMAL(4,2)` 数值，不是枚举 "2/2.25/2.5/..."

### D-4 · `backtest_sessions` 新增 5 个字段（P6）

| 字段 | 类型 | 来源 |
| --- | --- | --- |
| `mode` | ENUM(`fixed`,`kelly`,`both`) | P6 Q2 |
| `initial_capital` | DECIMAL(14,2) | P6 Q3 |
| `kelly_profit_loss` | DECIMAL(14,2) | P6 Q3 |
| `kelly_roi` | DECIMAL(8,4) | P6 Q3 |
| `equity_curve` | JSON | P6 Q4 |

设计文档仅列 6 个字段（`total_bets/hit_count/hit_rate/roi/profit_loss/results_by_score/results_by_league`）。
**建议**：把 P6 Q1-Q4 决策写回设计文档四.backtest_sessions。

### D-5 · `match_scores` 字段增强

设计文档列出了 `actual_hit / bet_amount / notes` 但没强调它们是"复盘"字段；实现全部就位但 **UI 还没开放录入** → P7 任务。

### D-6 · `model_configs` 实际多出 `scrape_schedule_json` 字段

用于覆盖默认 cron（见 `scheduler/main.py:load_schedule_config`）。设计文档未记录。
**建议**：更新设计文档第四节 `model_configs` 定义补充该字段，并在第六节说明"模型配置也承载抓取调度覆盖"。

### D-7 · 全新表 `scrape_logs`（设计文档完全未记录）

字段：`id, source, status(running|success|failed|partial), records, message, duration_ms, created_at`。用于抓取面板与可观测。
**建议**：把它加到设计文档第四节。

---

## 五 · 评分系统 🟡（2 处偏差）

### 设计文档规则 vs 实现

| 维度 | 设计满分 | 实现满分 | 触发函数 | 是否一致 |
| --- | --- | --- | --- | --- |
| 欧赔结构 | 25 | 25 | `euro_score` | ✅ |
| 亚盘 | 20 | 20 | `asian_score` | ✅ |
| 大小球 | 20 | 20 | `goals_score` | ✅ |
| 战意/赛制 | 15 | 15 | `intent_score` | ✅ |
| 平赔压缩度 | 20 | 20 | `compression_score` | ✅ |
| 球队状态 | 20 | 20 | `team_stats_score` | ✅ |

### 偏差 SCR-1 · 阈值单位口径

设计文档第五节写「平 ≥ 70%（84分）、让平 ≥ 65%（78分）」，`DEFAULT_THRESHOLDS`（`scripts/seed.py`）存储的是**绝对分数**：

```json
{"recommend_total_score": 84, "draw_min_score": 84, "handicap_draw_min_score": 78}
```

一致，但文档用百分比、代码用绝对值，换算关系需要同步文字。

### 偏差 SCR-2 · 权重规范化的口径

`ScoringService` 的做法：

```python
normalized = { k: weights[k] / DEFAULT_WEIGHTS[k] for k in DEFAULT_WEIGHTS }
```

其中 `DEFAULT_WEIGHTS = {euro=25, asian=20, ...}`（即最大分盖）。
**隐含语义**：用户在 `ModelConfig.weights_json` 里填的数字需要以「最大盖」为 1 单位。C1 热修后 seed 默认值也改成了这个语义（否则历史 `{1.0}` 会被归一化到 1/25 = 4%）。
**问题**：设计文档没有明确该归一化约定，新手很容易填错。P7 UI 必须同步校验/提示。

---

## 六 · 功能模块 🟡（2 项未上线）

### ① 数据抓取 ✅
- 定时自动抓取 ✅ 5 个 job
- 手动补抓 ✅ `/api/scrape/jobs/{name}/run`
- 抓取状态面板 ✅ `/admin/scrape`

### ② 今日推荐 ✅
- 当日列表 / 排序 / 标注达标 / Kelly 比例 ✅
- 手动修正 + 备注 ✅（`PUT /api/scores/{id}`）

### ③ 回测 ✅（超出设计预期）
- 时间段 + 模型配置 ✅
- 命中率 / ROI / 盈亏 / 分数段 / 各联赛命中率 ✅
- 两模型并排对比 ✅
- **额外**：equity curve / Kelly 双口径 / 90 天限额 / owner 隔离 + admin 穿透

### ④ 模型配置 ❌
- **当前**：只有 `default` 种子，管理员需要改库或改 seed
- **P7 计划**：`/model` 页面支持可视化调权重、阈值、Kelly 带；多版本克隆；激活切换

### ⑤ 用户管理（admin UI）❌
- 后端 `/api/users/*` 完整 ✅
- 前端 `/admin` 目录仅有 `/admin/scrape`，**用户管理页面未开发**；admin 需用 curl 或 SQL
- **建议**：P7 或 P8 补上 `/admin/users`

---

## 七 · 技术栈 🟡（1 处偏差）

| 设计 | 实现 | 备注 |
| --- | --- | --- |
| Next.js 14 | ✅ | App Router |
| shadcn/ui + Tailwind | ✅ | |
| ECharts / Recharts | 🟡 **Recharts** | 统一用 Recharts，未引入 ECharts |
| FastAPI | ✅ | |
| httpx + BeautifulSoup | ✅ | |
| NumPy + Pandas | 🟡 **Decimal**-based | 评分 / 回测 / Kelly 全部用 Python `Decimal` + dataclass；并未引入 pandas |
| APScheduler | ✅ BlockingScheduler | |
| MySQL | ✅ 8.0 utf8mb4 | |
| SQLAlchemy + Alembic | ✅ 2.0 Mapped API | |
| JWT (python-jose) | ✅ | |
| Docker Compose | ✅ | |

### 偏差 TS-1 · 未引入 pandas / numpy

实际计算没有矩阵或时序分析需求，Decimal + 纯函数更安全（避免浮点精度引发的 P/L 误差）。
**建议**：更新技术栈表格，把 NumPy/Pandas 改为「Python Decimal + dataclass」。

---

## 八 · 项目结构 🟡（1 处偏差）

```
设计                                  实际
sporttery_10x/                        sporttery_10x/
├── frontend/                         ├── frontend/
│   ├── app/                          │   ├── app/
│   │   ├── dashboard/ ✅             │   │   ├── dashboard/ ✅
│   │   ├── backtest/ ✅              │   │   ├── backtest/ ✅
│   │   ├── model/    ❌              │   │   ├── (缺) model/ ❌ P7
│   │   └── admin/    🟡              │   │   ├── admin/scrape/ ✅
│   └── components/                   │   │   └── (缺) admin/users/ ❌
├── backend/                          │   └── components/
│   ├── api/                          │   └── lib/        🆕 api client + 类型
│   ├── models/                       ├── backend/
│   ├── scrapers/                     │   ├── app/
│   ├── engine/                       │   │   ├── api/  ✅
│   └── scheduler/                    │   │   ├── models/ ✅
└── docker-compose.yml                │   │   ├── scrapers/ ✅
                                      │   │   ├── engine/  ✅（多一个 backtest_service.py）
                                      │   │   ├── scheduler/ ✅
                                      │   │   ├── services/ 🆕 服务层
                                      │   │   ├── schemas/  🆕 Pydantic
                                      │   │   ├── core/     🆕 config/database/security
                                      │   │   ├── cli/      🆕 create_admin
                                      │   │   └── scripts/  🆕 seed
                                      │   └── alembic/      🆕 migrations
                                      ├── docker-compose.yml ✅
                                      ├── Makefile          🆕
                                      └── docs/             🆕
```

**建议**：设计文档第八节目录树同步更新（特别是补齐 `backend/app/{services,schemas,core,cli,scripts}` 和 `frontend/lib`）。

---

## 九 · 后续可扩展 ✅

- 短信验证码登录 / 微信钉钉推送 / 赔率变动监控 / 爱彩网接入 → 均未实现但属于预期外延，符合"后续"定位。

---

## 建议合并到设计文档 V1.1 的修订清单

以下条目建议以 **V1.1 增量补丁**的形式回写 `docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`。

1. **第三节 数据源表**：把「球队状态」数据源从 titan007 改回 sporttery（S-1）。
2. **第四节 数据库结构**：
   - `matches.date` → `match_date (DateTime)`（D-1）
   - 所有业务表增加 `created_at/updated_at`（D-2）
   - 增补 `match_odds` 字段类型（D-3）
   - `backtest_sessions` 添加 `mode/initial_capital/kelly_profit_loss/kelly_roi/equity_curve` 五个字段（D-4）
   - `model_configs` 增补 `scrape_schedule_json`（D-6）
   - 新增 `scrape_logs` 表（D-7）
   - 明确 `match_scores` 的复盘三字段 `actual_hit/bet_amount/notes` 归为「复盘」子分组（D-5）
3. **第五节 评分系统**：
   - 明确阈值口径写为「绝对分数 + 对应百分比」双标注（SCR-1）
   - 补充权重归一化约定：`normalized = weight[k] / dim_cap[k]`，并给出建议用户直接填写 `[0, dim_cap]` 数值（SCR-2）
4. **第六节 功能模块**：将 ④⑤ 状态标注为「规划中 · P7」。
5. **第七节 技术栈**：
   - 图表库改为「Recharts」
   - 模型计算改为「Python `Decimal` + dataclass」（TS-1）
6. **第八节 项目结构**：补齐 `backend/app/{services,schemas,core,cli,scripts}`、`frontend/lib/*`、顶层 `Makefile` 和 `docs/`（目录图已在上文给出）。
7. **第九节 后续可扩展**：追加两项已规划条目：
   - 历史赔率快照（`match_odds_history`）
   - 评分版本化（model_config `is_active` / `parent_id`，见 P7 计划）

> 一次合入 V1.1 后，设计文档与实现即可完全对齐。

---

## 风险 / 遗留项（不在设计文档范围但值得提）

| 编号 | 问题 | 来源 | 处理建议 |
| --- | --- | --- | --- |
| R-1 | `match_odds` 多源并存，当前默认取 `sporttery`；titan007 数据仅用于补全 | P4 | P7+ 引入"odds_preference"字段显式决定 |
| R-2 | 回测口径不含佣金/税；真实盈亏偏乐观 | 手册未提 | 需要时加 `commission_rate` 到 `ModelConfig` |
| R-3 | 用户修改后短时间窗口内需要重算（目前依赖 09:15 cron） | 设计文档 | P7 `/model` 激活切换时触发重算 job |
| R-4 | `match_scores.updated_at` 用于复盘乐观锁尚未引入 | review M1 | P7 一起补 |
| R-5 | 本地时区硬编码 `Asia/Shanghai`，跨时区使用需改 | 设计固定 | 暂无需修改 |
| R-6 | 未覆盖「赛程推迟 / 比赛取消」的赛果状态 | 设计未列 | 增加 `matches.status='cancelled'` 与 `match_results.status` |

---

## 附录 · 核对清单（供后续评审快速勾选）

- [x] 架构图 4 层全部落地
- [x] 6 维评分 + 总分 120
- [x] Kelly 分带 2%/1.5%/1%
- [x] APScheduler 5 个 job
- [x] 回测同步 + 对比
- [x] JWT 认证
- [x] Docker Compose 四容器
- [ ] `/model` 页面
- [ ] `/admin/users` 页面
- [ ] 复盘录入 UI
- [x] 回测 owner 隔离（P6 hotfix）
- [x] 回测不污染 match_scores（P6 hotfix）
- [x] Alembic 迁移链到 0005 → 2026-04-27 已延至 `0006_model_config_active_parent`
- [x] `/model` 页面（P7 已完成）
- [ ] `/admin/users` 页面（P8+ 登记为 TD-5）
- [x] 复盘录入 UI（P7 `/review` + Dashboard「已结束」Tab 已完成）
- [x] 复盘乐观锁 R-4（P8 H1 TD-1 已完成）
- [x] 激活切换触发重算 R-3（P8 H1 TD-6 已完成）
- [ ] 设计文档 V1.1 合入本次 review 结论（PRD V1.1 已折中承载；原始 spec 保留 V1.0 版本快照）
