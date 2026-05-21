# Sporttery 10x · MVP 期运营手册

**版本**：V1.0 · 2026-04-21
**适用阶段**：P1-P7 + P8 H1 已上线，进入「真实运行 + 数据积累」阶段
**面向读者**：owner（既是 admin 又是真实下注人）
**配套阅读**：

- 操作细节：`docs/usage/USAGE.md`
- 评分原理：`平让平竞彩交易模型手册.md`
- 系统架构：`docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`
- 模型调参流程：`docs/superpowers/guides/model-config-workflow.md`

---

## 目录

- [1. 本手册的定位](#1-本手册的定位)
- [2. MVP 阶段的"是"与"不是"](#2-mvp-阶段的是与不是)
- [3. Phase 0：准入检查（做一次）](#3-phase-0准入检查做一次)
- [4. Phase 1：锚定基线（做一次）](#4-phase-1锚定基线做一次)
- [5. Phase 2：日常纪律（每日 / 每赛事日）](#5-phase-2日常纪律每日--每赛事日)
- [6. Phase 3：周度与月度复盘](#6-phase-3周度与月度复盘)
- [7. 禁忌清单（MVP 期必须抵制）](#7-禁忌清单mvp-期必须抵制)
- [8. 升级到 V2 的触发条件](#8-升级到-v2-的触发条件)
- [9. 附录：记录模板](#9-附录记录模板)

---

## 1. 本手册的定位

`USAGE.md` 回答的是 "按钮怎么点 / 字段怎么填"。
本手册回答的是：**"系统已经跑起来了，接下来的 1–3 个月怎么用才能真正创造价值？"**

核心主张只有一句：

> **MVP 的核心任务不是"把模型做得更好"，而是"用规则式模型产生足够多的真实样本，让未来的 V2 有数据可用"。**

也就是说，现在的重点是 **跑数据 + 守纪律**，不是 **加功能 / 改代码 / 调模型**。

---

## 2. MVP 阶段的"是"与"不是"

| 维度 | ✅ 这个阶段应该做 | ❌ 这个阶段不做 |
| --- | --- | --- |
| 数据 | 把爬虫跑稳、补齐历史 | 接更多数据源（爱彩网等） |
| 模型 | 沿用手册 6 维评分默认权重 | 上 ML / 自动寻优 / 加新维度 |
| 下注 | 严格按系统输出的 bet_type + Kelly | 情绪加注、倍投、追单 |
| 复盘 | 每场赛后 `/review` 回填真实结果 | 只看不填、或批量乱填 |
| 调参 | 每月最多一次 `/model` 微调 | 每天都想动权重 |
| 开发 | 只修 bug，不加功能 | 新 Feature 大改造 |

一句话：**抑制产品欲、抑制交易欲，先让数据跑满一个季度。**

---

## 3. Phase 0：准入检查（做一次）

在把系统当作"真实决策工具"之前，先**一次性**确认下面 5 件事都就绪。任何一项没过关，都不要进 Phase 2 下注。

### 3.1 容器与定时任务

```bash
docker compose ps          # 4 个容器 UP
curl http://localhost:8000/health
```

- [ ] `backend` / `frontend` / `mysql` / `scheduler` 全部 healthy
- [ ] `/admin/scrape` 面板 5 个 job 都有「下次运行时间」
- [ ] 观察 2 天，每个 job 都至少成功跑过 1 次（`scrape_logs.status='success'`）

### 3.2 历史数据覆盖度

至少补齐 **最近 6 个月** 的历史：

```bash
# 爬虫回溯（admin 后台或 CLI）
docker compose exec backend python -c "
from app.scheduler.jobs import run_schedule_job, run_result_job, run_odds_job
# 具体日期段接口见 P4 计划
"
```

覆盖度要求（用下列 SQL 自查）：

```sql
SELECT
  COUNT(*)                                                          AS total,
  SUM(CASE WHEN mo.id IS NOT NULL THEN 1 ELSE 0 END)                AS with_odds,
  SUM(CASE WHEN mts.id IS NOT NULL THEN 1 ELSE 0 END)               AS with_team_stats,
  SUM(CASE WHEN mr.id IS NOT NULL THEN 1 ELSE 0 END)                AS with_result
FROM matches m
LEFT JOIN match_odds mo        ON mo.match_id = m.id
LEFT JOIN match_team_stats mts ON mts.match_id = m.id
LEFT JOIN match_results mr     ON mr.match_id = m.id
WHERE m.match_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH);
```

- [ ] `with_odds / total ≥ 90%`
- [ ] `with_team_stats / total ≥ 85%`
- [ ] `with_result / total ≥ 95%`（赛果延迟可接受，但不能缺太多）

> 三项中任一低于阈值 → 回测结果**不可信**，先补数据。

### 3.3 默认模型配置完整性

```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/model-configs/active | jq
```

- [ ] `weights_json` 6 维齐全，每项在 `[0, dim_cap]` 内
- [ ] `thresholds_json = {"recommend_total_score":84, "draw_min_score":84, "handicap_draw_min_score":78}`
- [ ] `kelly_bands_json` 有 3 个不重叠档位

### 3.4 本金设置

- [ ] `users.bankroll_cny` 已按你真实能承受的风险资金填写
- [ ] 牢记规则：**bankroll 是你愿意全部归零的钱**，不是家庭储蓄

### 3.5 第一次端到端演练（干跑，不真投注）

- [ ] 选最近一天有比赛的日期 → 看 Dashboard 有推荐
- [ ] 点一场 → 能看到 6 维明细
- [ ] 赛后 → 能在 `/review` 把 `actual_hit` 回填并保存成功
- [ ] 跑一次最近 7 天 `both` 模式回测 → 能看到 equity_curve 折线

以上全过，才进入 Phase 1。

---

## 4. Phase 1：锚定基线（做一次）

**目的**：在动任何权重之前，先记下"原始版本"的表现，作为未来所有调参的参照系。

### 4.1 基线回测

入口：`/backtest` → 新建

| 参数 | 取值 |
| --- | --- |
| 日期范围 | 近 3 个月（系统最长 90 天，分两段也行） |
| 初始本金 | 10000（统一口径，别用真本金） |
| 模式 | `both`（同时看固定和 Kelly） |
| 模型 | 默认激活版本（通常是 seed 生成的 v1） |

### 4.2 必须记录的 7 个指标

把这 7 个数字写进 `docs/usage/baseline.md`（手工维护，或填到 §9 附录的模板里）：

1. 样本数 `total_bets`
2. 总命中率 `hit_rate`
3. `draw` 子集命中率（从 `results_by_score` / `bet_type` 拆算）
4. `handicap_draw` 子集命中率
5. 固定单位 ROI `roi_fixed`
6. Kelly ROI `roi_kelly`
7. 最大连续未中（从 `equity_curve` 人眼数或 SQL 算）

### 4.3 分段观察

重点看 `results_by_score`：

- **84+ 分段命中率** 应明显高于 **78–84 分段**（否则说明阈值设得太松）
- **78 分段以下** 都不该有下注（若有，说明规则有 bug）

重点看 `results_by_league`：

- 记下 ROI 最好和最差的 3 个联赛 → 这是后续调参的线索

### 4.4 基线快照（示意）

```text
== 基线 v1.0 · 2026-04-21 ==
窗口：2026-01-21 ~ 2026-04-20（90 天）
total_bets = 48
hit_rate   = 0.354
roi_fixed  = +0.21
roi_kelly  = +0.064
max_losing_streak = 7
by_bet_type:
  draw            22 场, 命中 9,  ROI +0.30
  handicap_draw   26 场, 命中 8,  ROI +0.14
by_league_top:    意甲 +0.45 / 日职联 +0.32
by_league_bottom: 英超 -0.18 / 德甲 -0.09
```

> 未来每次改权重，都必须和**这份快照**对比，不是和上一次改对比。

---

## 5. Phase 2：日常纪律（每日 / 每赛事日）

### 5.1 每日晨间（比赛日 08:30–09:30）

```text
[ ] 08:40 检查 /admin/scrape：schedule / odds 均 success
[ ] 09:00 检查 team_stats 是否 success
[ ] 09:20 打开 /dashboard，勾选「仅推荐」
[ ] 逐条看推荐比赛（通常 0–3 场）
```

### 5.2 下注决策（硬性纪律）

| 规则 | 为什么 |
| --- | --- |
| 推荐 **< 78 分**：一律不下注 | 低于让平阈值 |
| 每日最多 **2 场** | 手册 §7.6 原则 |
| 至少 1 场 ≥ 84 分（若无则全部跳过） | 防止两个低分盘硬凑 2 串 1 |
| 金额 = `bankroll × kelly_pct`，**不打折不加码** | Kelly 的价值全在机械执行 |
| **不做 2 串 1** | 0.12² ≈ 1.4% 命中率，MVP 期承受不起 |
| **不做倍投** | 手册 §8.3 已论证，连黑 20 场不罕见 |

### 5.3 下注后登记

每次真实下注后，在 **同场比赛**的 Dashboard 行点进去 → `/review` 先填 `bet_amount`（`actual_hit` 留空）。这样即使当天没开赛，账也不会漏。

### 5.4 赛后回填

**当天 23:40 或次日早上**：

```text
[ ] /admin/scrape 确认 result job 成功
[ ] /dashboard「已结束」Tab 或 /review，筛选当天
[ ] 对每条已下注记录：
    - 确认 suggested_actual_hit（系统推断的命中与否）与实际一致
    - 在 actual_hit 下拉里选「命中」或「未中」
    - notes 写一句话：例如「欧冠半决赛，主队控球占优但把握机会差」
```

> **禁止"只下不填"**：样本不回填，3 个月后你什么也总结不出来。

---

## 6. Phase 3：周度与月度复盘

### 6.1 每周一次（周一晚）· 15 分钟

```text
[ ] /review 过滤上周 7 天
[ ] 看汇总条：命中率、Σ 投注额、Σ 净盈亏
[ ] 不改任何权重，只回答 2 个问题：
    1. 本周是否出现违反纪律的下注？（情绪加码 / 凑串 / 跟跌）
    2. 有没有数据缺口的一天？（赔率没抓到、赛果延迟）
[ ] 违规次数 > 0 → 在 baseline.md 写一句警示
[ ] 数据缺口 → 安排 CLI 补抓
```

### 6.2 每月一次（月底）· 60 分钟

#### Step 1：跑月度回测

- `/backtest` 近 30 天，默认模型，both 模式
- 和 **基线** 比较 7 个指标的变化

#### Step 2：找结构性信号（而不是随机波动）

值得注意的信号（**必须样本 ≥ 30 场**才算数）：

| 信号 | 处理方式 |
| --- | --- |
| 某联赛 ROI 持续 < -0.10，样本 ≥ 30 | 下月在 `matches.competition_type` 手工下调该联赛战意分 |
| 84+ 分段命中率 < 30%，样本 ≥ 30 | 考虑把 `draw_min_score` 上调到 86 |
| Kelly ROI > 固定 ROI 很多 | 说明高分段确实更稳，可考虑把 Kelly 分带往上微调 |
| 让平命中率 < 20% 连续 2 个月 | 考虑暂时关闭 `handicap_draw` 推荐（`handicap_draw_min_score=999`） |

#### Step 3：若要调参，只动一个变量

流程见 `docs/superpowers/guides/model-config-workflow.md`：

```text
克隆当前激活版 → 只改 1 个维度权重 / 1 个阈值 → 保存
    ↓
/backtest 双模型对比（新 vs 当前激活）
    ↓
ROI 改善 ≥ 2% 且样本 ≥ 100 场 → 激活新版
否则 → 保留为候选，不激活
```

> **绝对禁止**：一次改多个参数。你会永远分不清到底是哪个在起作用。

#### Step 4：归档

- 本月数据快照追加到 `baseline.md`
- 新模型版本（即便未激活）都留在 `/model` 列表里，`parent_id` 血缘链是你的实验档案

### 6.3 季度回顾（每 3 个月一次）· 2 小时

此时应已积累：

- `match_scores.actual_hit` 非空记录 **≥ 200 条**
- 3 个月的月度快照
- 2–3 个候选模型版本

回答一个问题：**"下个季度是继续守 MVP，还是进入 V2？"**

判断依据见下一节。

---

## 7. 禁忌清单（MVP 期必须抵制）

| 冲动 | 真相 |
| --- | --- |
| "这场盘口明显好，多下一点" | 一次情绪加注 = 半个月纪律归零；Kelly 公式本身已考虑了你的优势 |
| "连黑 5 场了，下一场必中，加倍" | 连黑 10 场在 12.25% 命中率下概率 = 27%，完全正常 |
| "今天没推荐，找一场 3 倍以上的冷门玩一下" | 手册 §9.4 的核心 —— 必须接受"今天不下注" |
| "加一维'伤停指数'到评分里" | 6 维都还没验证完，加维度只会让回测噪声变大 |
| "上 ML 吧，XGBoost 肯定更强" | 样本 < 500 条全是过拟合；先让规则式跑满一季度 |
| "改一下 `euro_score` 的甜区阈值" | MVP 期**只改权重**，不改评分函数代码 |
| "今天凑个 2 串 1 提升赔率" | 命中率指数级衰减，期望值不变但方差剧增，爆仓加速器 |

---

## 8. 升级到 V2 的触发条件

满足 **任意一条** 再考虑动 V2，否则继续守 MVP：

### 8.1 数据充足信号

- [ ] `match_scores.actual_hit IS NOT NULL` 的记录 ≥ **300 条**
- [ ] 覆盖至少 **3 个完整自然月**
- [ ] 每个主要联赛（英超/西甲/意甲/德甲/法甲/日职联）样本 ≥ 20 条

### 8.2 瓶颈信号

- [ ] 连续 **3 个月**月度 ROI 在基线 ±5% 内震荡，手动调参已无改善
- [ ] 发现某维度（最可能是 `team_stats` 或 `intent`）的分段命中率与其他维度**几乎无区分度** → 规则式评分已到天花板

### 8.3 V2 优先级排序（仅列方向，届时再规划）

| 优先级 | 增量 | 价值 |
| --- | --- | --- |
| P0 | 引入单场命中概率 `p_draw`（逻辑回归，特征=现有 6 维原始值） | 让 Kelly 用真实 p 而非分档 pct |
| P1 | `match_odds_history` 快照表 + 盘口异动特征 | 新增维度；V2 最值得做的一维 |
| P1 | 权重自动寻优（简单网格 + 交叉验证） | 解放人工月度调参 |
| P2 | 回测扣佣金、cancelled/postponed 状态、`/admin/users` UI | 技术债（见 P8 H2） |
| P3 | 特征重要性分析（把无用的维度砍掉） | 回到"奥卡姆剃刀" |

---

## 9. 附录：记录模板

把下面的模板复制到 `docs/usage/baseline.md`（自行创建），每月填一次。

```markdown
# Baseline & Monthly Snapshots

## Baseline v1.0（2026-04-21）

- 窗口：2026-01-21 ~ 2026-04-20
- 模型：default（seed v1）
- total_bets:
- hit_rate:
- by_bet_type:
  - draw:           场, 命中 , ROI
  - handicap_draw:  场, 命中 , ROI
- roi_fixed:
- roi_kelly:
- max_losing_streak:
- top_3_leagues（ROI 最好）：
- bottom_3_leagues（ROI 最差）：

---

## 2026-05 月度快照

- 窗口：2026-04-21 ~ 2026-05-20
- 真实下注 N 场，实际命中率 X%
- 回测命中率对比基线：+/- X 个百分点
- 结构性信号：
- 本月是否调参：否 / 是（版本 name：_____；改了什么：_____）
- 下月计划：

---

## 2026-06 月度快照

...
```

---

## 10. 一页纸总结

```text
┌───────────────────────────────────────────────────┐
│  MVP 期 · 三条底线                                 │
├───────────────────────────────────────────────────┤
│  1. 抓数据 ≥ 90% 覆盖，爬虫不能断                   │
│  2. 下注严格照系统输出，不加不减                     │
│  3. 每月只动一个参数，每次调参都对标基线             │
├───────────────────────────────────────────────────┤
│  出现以下任一情况，立刻停手回到纪律：                │
│    · 连黑 3 场开始手痒加码                          │
│    · 一周没在 /review 回填                          │
│    · 想一次改 2 个以上权重                          │
└───────────────────────────────────────────────────┘
```

**版本**：V1.0
**用途**：MVP 运营节奏约束，非开发文档
**下次更新**：V2 启动前，或连续 3 个月月度复盘后
