# 删除中间模型运行逻辑设计

## 背景

数据库已经清理为干净环境，只保留历史比赛/赔率/赛果/球队状态/用户数据，并且 `model_configs` 只保留：

- `default`
- `empirical-v32-filtered-candidate`

为了避免后续 seed、脚本或页面测试再次创建和使用已删除的中间模型，需要同步删除运行代码中的相关逻辑。

## 目标

1. 运行态只允许 `default` 和 `empirical-v32-filtered-candidate` 两个模型配置。
2. 删除会自动创建 `empirical-v3-candidate` 的 seed 逻辑。
3. 删除 score/backtest 脚本中默认指向 `empirical-v2-d104-h104-clean`、`empirical-v3-candidate`、`empirical-v31-combination-candidate` 的逻辑。
4. 保留 `empirical-v32-filtered-candidate` 所需的候选规则实现。
5. 更新测试，避免测试继续要求中间模型存在。
6. 更新文档，明确中间模型已经退休。

## 非目标

1. 不删除历史研究报告文档。旧报告是模型演进证据，可保留归档。
2. 不改变历史比赛、赔率、赛果、球队状态数据结构。
3. 不改变 V3.2 候选规则本身。
4. 不删除 V3.4 二串一报告功能；它仍基于 `empirical-v32-filtered-candidate`。

## 设计

### Seed

`backend/app/scripts/seed.py` 只确保：

- `default`
- `empirical-v32-filtered-candidate`

不再创建 `empirical-v3-candidate`。

### ScoringService

删除 `strategy=empirical_v3` 的运行分支。`empirical_v2` 不再作为推荐运行策略使用。

保留：

- 默认策略路径。
- V3.2 历史 score 生成脚本所需的规则函数。

### 历史 score 脚本

`score_history.py` 示例和使用说明改为 `empirical-v32-filtered-candidate`。

### 90 天窗口回测脚本

`backtest_model_windows.py` 默认比较模型改为：

- `default`
- `empirical-v32-filtered-candidate`

不再内置 v2/v3 报告结构。

### V3.2 候选脚本

`v31_combination_candidate_backtest.py` 保留 V3.2 输出能力，但不再作为创建 `empirical-v31-combination-candidate` 的入口使用。底层规则名称中出现 `V31` 属于历史因子命名，不再代表运行态模型。

## 验收标准

1. `rg "empirical-v2-d104-h104-clean|empirical-v3-candidate|empirical-v31-combination-candidate" backend/app frontend` 不再出现运行态引用。
2. Seed 测试不再创建 v3。
3. 后端相关测试通过。
4. 前端测试不再使用 v2 作为示例模型。
5. 当前模型文档说明只保留 `default` 和 `empirical-v32-filtered-candidate`。
