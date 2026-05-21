# 模型配置 · 运营手册

**受众**：`admin` 角色运营 / 分析师
**前置**：P7 已部署（alembic `0006_model_config_active_parent` 完成，`/model`、`/review`、`/api/model-configs`、`/api/reviews` 均可访问）

本文描述「调权重 → 回测验证 → 激活 → 复盘 → 再调」一整个闭环的最短路径。任何 `admin` 登录后都可以完整执行，一次性改动不超过 5 分钟。

---

## 1. 术语速查

| 概念 | 说明 |
| --- | --- |
| `ModelConfig` | 一个完整评分模型，由 `weights_json`、`thresholds_json`、`kelly_bands_json` 三块组成 |
| `is_active` | 全局唯一（软约束），默认打分 / 定时任务读这个版本 |
| `parent_id` | 克隆来源，便于追溯 A→B→C 演化链 |
| `MatchScore.actual_hit / bet_amount / notes` | 人工复盘回写字段 |

---

## 2. 权限矩阵

| 接口 / 页面 | member | admin |
| --- | --- | --- |
| `GET /api/model-configs` | ✅ | ✅ |
| `POST /api/model-configs` | ❌ 403 | ✅ |
| `PATCH /api/model-configs/{id}` | ❌ | ✅ |
| `POST /api/model-configs/{id}/clone` | ❌ | ✅ |
| `POST /api/model-configs/{id}/activate` | ❌ | ✅ |
| `GET /api/reviews` | ✅ | ✅ |
| `PATCH /api/reviews/{score_id}` | ❌ 403 | ✅ |
| `/model` 表单编辑 | 只读 | 可编辑 |
| `/review`、Dashboard「已结束」Tab 录入 | 只读 | 可写 |

所有变更接口仅 admin，前端 UI 也严格对应（按钮和输入在 member 下 disabled）。

---

## 3. 调权重的正确姿势

1. **克隆**：进入 `/model`，选中现行版本（显示「激活」badge），点「克隆」，弹窗输入新版本名例如 `v2026-04-21-euro-up`。

   → 后端 `POST /api/model-configs/{parent_id}/clone`，返回的新版 `is_active=false`、`parent_id=parent_id`。

2. **微调**：在新版本详情页修改：
   - 6 维权重总分自动合计（常规保持 ~100）
   - 4 个阈值：`min_total_score / recommend_total_score / draw_min_score / handicap_draw_min_score` 等
   - Kelly 带：至少一条，`min_score/max_score` 不允许重叠，`kelly_pct ∈ (0, 1)`
   - 点「保存」→ `PATCH /api/model-configs/{id}`。

3. **回测验证**（推荐做完再激活）：
   - 打开 `/backtest`，把「模型」下拉切到新版，选一个 1-3 个月历史区间。
   - 与 `default`（或上个激活版）对比 ROI、命中率、Sharpe。
   - 若指标回撤超过 -5% 或命中率下跌 >3%，建议再克隆再调，不要直接激活。

4. **激活**：在新版本上点「激活」。后端做两步事务：
   ```
   UPDATE model_configs SET is_active = false WHERE id != :new_id AND is_active = true;
   UPDATE model_configs SET is_active = true  WHERE id = :new_id;
   ```
   Dashboard、定时评分任务、默认 `/api/scores/compute`、默认 `/api/reviews` 立即读新版。

5. **回滚**：若发现问题，只要在原版本上再点「激活」即可。历史版本从不删除。

---

## 4. 复盘录入

### 场景 A：日常盯盘

- 打开 Dashboard → 「已结束 · 复盘」Tab
- 默认近 14 天、全部状态；按需改日期或勾「仅推荐」
- 每行可直接：
  - 设 `命中` / `未中` / `待定`（下拉 select，离开即 `PATCH`）
  - 填 `投注金额`（number input，`onBlur` 提交）
  - 写 `备注`

### 场景 B：批量深度复盘

- 打开 `/review`（顶部导航「复盘」）
- 筛选多联赛 / 命中状态 / 仅推荐等
- 底部汇总条实时显示「已复盘条数 / 命中率 / 投注金额 / 净盈亏」

> 净盈亏 = Σ(actual_hit ? bet_amount : -bet_amount)。如需叠加赔率，后续接入 `match_odds_history` 后再精细化。

### 字段规则

- `actual_hit`：`true / false / null`。`null` 意味着还没人判过。
- `bet_amount`：`Decimal(10,2) >= 0`。负数直接 422。
- `notes`：纯文本，长度受数据库 `TEXT` 限制。
- `suggested_actual_hit`（只读）：后端基于 `bet_type` 和 `MatchResult.handicap_result/result` 给出的「建议值」，帮助快速判断；仍以人工 `actual_hit` 为准。

---

## 5. 失败排查

| 症状 | 可能原因 | 处置 |
| --- | --- | --- |
| 激活后 Dashboard 没切版本 | 浏览器缓存了 `ModelConfig` 列表 | 在 Dashboard 点「刷新」；`/api/model-configs` 返回最新 `is_active` |
| PATCH 422 `bet_amount must be >= 0` | 输入负数或非数值 | 改为 >=0 数字 |
| PATCH 403 `admin required` | 当前账号非 admin | 使用 admin 账号登录 |
| 克隆名字冲突（`400 model_config name already exists`） | 后端 `ModelConfig.name` 唯一约束（P8 H1 TD-2，由 alembic `0001` 初始化时建立） | 改一个独立名字 |
| Kelly 带互相重叠 | 前端 & 后端双重校验 | 调整 min_score / max_score |

---

## 6. 相关实现文件索引

- 后端：`backend/app/api/model_config.py`、`services/model_config.py`、`schemas/model_config.py`
- 后端：`backend/app/api/reviews.py`、`schemas/review.py`
- 前端：`frontend/app/model/model-client.tsx`、`frontend/app/review/review-client.tsx`
- 测试：`backend/tests/test_api_model_config.py`、`test_api_reviews.py`、`test_p7_smoke.py`
- 前端测试：`frontend/tests/model-client.test.tsx`、`review-client.test.tsx`、`p7-routes.test.tsx`

---

## 7. 每次上线自检 checklist

- [ ] `alembic current` 指到 `0006_model_config_active_parent`
- [ ] `python -m app.scripts.seed` 成功（默认管理员 + `default` 配置 active）
- [ ] 以 admin 登录，`/model` 可见 `default` 版本并有「激活」badge
- [ ] 点克隆、改权重、`/backtest` 对比、激活——每一步响应 2xx
- [ ] Dashboard「已结束」Tab 可写入 `actual_hit`
- [ ] 以 member 登录，所有写操作按钮 disabled、PATCH 请求返回 403
