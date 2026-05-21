# 抓取数据源边界重构设计

## 背景

当前模型依赖三类基础数据：竞彩赛程与官方奖金赔率、Titan007 欧赔/亚盘、球队赛前状态与交锋近况。此前发现一个核心风险：竞彩网的球队状态接口在历史比赛回看时会返回最新状态，而不是当时赛前状态，会造成历史训练和回测数据泄漏。

这次重构不是简单删除某个数据源，而是把数据源按使用场景分层：未来推荐可以使用当前可见的赛前数据，历史回填必须使用对应历史比赛页面保存的赛前快照。

## 目标

1. 未来/今日推荐链路必须同时准备赛程、竞彩官方赔率、Titan007 欧赔/亚盘、Titan007 比赛分析数据。
2. 历史回填链路的球队状态只允许来自 Titan007 `analysis/{match_id}cn.htm`。
3. 代码命名、调度任务、测试和文档都要体现这个边界，降低后续误用竞彩网历史球队状态的概率。
4. 不改变当前模型评分逻辑，只重构数据准备链路。

## 非目标

1. 本次不新增模型因子。
2. 本次不改今日推荐页面策略。
3. 本次不做大规模数据库迁移，除非发现必须记录新映射字段。

## 数据源边界

| 场景 | 赛程 | 官方奖金赔率 | 欧赔/亚盘 | 球队状态/近况/交锋 |
|---|---|---|---|---|
| 未来/今日推荐 | Sporttery `getMatchCalculatorV1` | Sporttery HAD/HHAD | Titan007 实时 feed | Titan007 `analysis/{id}cn.htm` |
| 历史回填 | Sporttery 赛果接口可用于官方赛果和奖金赔率补充；Titan007 JcResult 用于映射 | Sporttery 历史奖金赔率 | Titan007 `oddsData.aspx` | Titan007 `analysis/{id}cn.htm` |

关键约束：`SportteryTeamStats` 不再作为推荐或历史回填的默认球队状态来源。它可以保留为遗留解析器，但调度链路不再调用它。

## 推荐链路设计

`run_schedule_job` 保持一条龙思想，但步骤改为：

1. `SportterySchedule` 抓未来赛程和竞彩官方赔率，写入 `sporttery_matches`。
2. `Titan007Odds` 抓实时比赛映射和欧赔/亚盘，写入 `sporttery_match_odds`。
3. 新增 `Titan007AnalysisStats` 抓需要状态但还没有状态的未来比赛，写入 `sporttery_match_team_stats`。

`Titan007AnalysisStats` 不直接依赖 Sporttery 内部 `matchId`，而是依赖 Titan007 实时 feed 中的 `jc_code -> titan007_match_id` 映射，再用比赛表里的 `round`/逻辑 ID 匹配。

## 历史回填设计

`backfill.py` 继续按天执行，但需要在文档和命名上改成“历史回填组合源”：

1. Sporttery 历史结果接口只用于比赛列表、赛果、竞彩官方赔率补充。
2. Titan007 `JcResult.aspx` 用于 `jc_code -> titan007_match_id` 精确映射。
3. Titan007 `oddsData.aspx` 用于历史欧赔/亚盘。
4. Titan007 `analysis/{id}cn.htm` 用于历史球队状态。

历史链路不得调用 `SportteryTeamStats` 或 `fetch_stats_for_mid`。

## 代码结构

新增文件：

- `backend/app/scrapers/titan007/analysis_stats.py`：面向调度任务的 Titan007 analysis 状态抓取器。
- `backend/tests/test_scrapers_titan007_analysis_stats.py`：锁定未来推荐状态抓取的映射和写库行为。

修改文件：

- `backend/app/scheduler/jobs.py`：`team_stats` job 改用 `Titan007AnalysisStats`。
- `backend/app/scrapers/titan007/analysis.py`：确保只使用 `cn.htm` URL，保留纯解析职责。
- `backend/app/scripts/backfill.py`：更新命名和注释，增加历史状态来源约束测试所需接口。
- `backend/tests/test_scheduler_jobs.py`：更新调度链路预期。
- `docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`：追加当前数据源边界说明，避免文档腐败。

## 测试策略

1. 单元测试 `Titan007AnalysisStats`：给定未来比赛和 Titan007 映射，只抓 `analysis/{id}cn.htm` 并写入球队状态。
2. 单元测试历史回填：`upsert_day` 使用 Titan007 match id 调用 `_upsert_team_stats`，不触碰 Sporttery 状态接口。
3. 调度测试：`run_team_stats_job` 调用 `Titan007AnalysisStats`，不再调用 `SportteryTeamStats`。
4. 回归测试：Titan007 analysis parser、history parser、schedule parser、scheduler job 通过。

## 验收标准

1. 未来 `schedule` 链路包含：赛程、Titan007 欧赔、Titan007 analysis 状态。
2. 历史回填状态来源只来自 Titan007 analysis `cn.htm`。
3. 相关测试和 ruff 通过。
4. 文档明确说明数据源边界，后续维护者不会把竞彩网球队状态用于历史回测。
