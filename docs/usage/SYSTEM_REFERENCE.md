# Sporttery 10x · 系统功能全览

**版本**：2026-04-23
**面向读者**：admin / 运营人员
**配套文档**：[USAGE.md](./USAGE.md)（UI 操作）、[MVP_OPERATIONS.md](./MVP_OPERATIONS.md)（运营节奏）

---

## 目录

- [1. 系统架构概览](#1-系统架构概览)
- [2. 定时任务（自动）](#2-定时任务自动)
- [3. 手动任务](#3-手动任务)
- [4. 数据抓取器详解](#4-数据抓取器详解)
- [5. 数据模型与表结构](#5-数据模型与表结构)
- [6. API 端点全表](#6-api-端点全表)
- [7. 前端页面](#7-前端页面)
- [8. 配置项](#8-配置项)
- [9. 常用运维命令](#9-常用运维命令)

---

## 1. 系统架构概览

```
┌─────────────┐   ┌───────────────┐   ┌───────────────┐   ┌──────────┐
│  frontend   │   │   backend     │   │  scheduler    │   │  mysql   │
│  Next.js    │──▶│   FastAPI     │──▶│  APScheduler  │   │  8.0     │
│  :3000      │   │   :8000       │   │  5 jobs       │   │  :3308   │
└─────────────┘   └───────────────┘   └───────────────┘   └──────────┘
                          │                   │                  ▲
                          └───────────────────┴──────────────────┘
```

4 个 Docker 容器通过 `docker-compose.yml` 编排，MySQL 使用 healthcheck 确保启动顺序。

---

## 2. 定时任务（自动）

由 `scheduler` 容器运行（`python -m app.scheduler.main`），基于 APScheduler CronTrigger，时区 `Asia/Shanghai`。

| # | 任务 ID | 默认时间 | 执行函数 | 行为 |
|---|---------|----------|----------|------|
| 1 | `schedule` | **每天 08:30** | `run_schedule_job` | 一条龙：赛程 → 赔率 → 球队统计 |
| 2 | `result` | **每天 23:30** | `run_result_job` | 回收已赛比分和赛果 |
| 3 | `odds` | **每 2h，分15** (08:15, 10:15…) | `run_odds_job` | 刷新澳门实时欧赔/亚盘 |
| 4 | `team_stats` | **每天 09:00** | `run_team_stats_job` | 未来 3 天比赛的球队统计 |
| 5 | `scoring` | **每天 09:15** | `run_scoring_job` | 用激活 ModelConfig 计算今日+明日评分 |

### 2.1 schedule 任务详细流程

```
1. SportterySchedule
   → GET getMatchCalculatorV1.qry（竞彩赛程 API）
   → 写入 sporttery_matches（含竞彩 HAD/HHAD 赔率）
   → 9 场约 0.5s

2. Titan007Odds
   → GET bf_jc.txt + goallottery1.txt（澳门实时 XML feed）
   → 写入 sporttery_match_odds（source=titan007，欧赔+亚盘）
   → 9 场约 0.5s

3. run_team_stats_job(days_ahead=7)
   → 对每场未来比赛调用竞彩 3 个 API
   → 写入 sporttery_match_team_stats（排名/战绩/近况/交锋）
   → 9 场约 4s
```

### 2.2 result 任务详细流程

```
SportteryResult
  → GET getUniformMatchResultV1.qry（近 3 天赛果）
  → 更新 sporttery_matches.status → 'finished'
  → 更新 sporttery_matches 的 HAD 赔率 + 让球数
  → 写入 sporttery_match_results（比分 + 赛果分类）
```

### 2.3 odds 任务详细流程

```
Titan007Odds
  → GET bf_jc.txt（比赛列表，titan007_id ↔ 竞彩编号映射）
  → GET goallottery1.txt（澳门欧赔+亚盘，全部在售比赛）
  → 写入/更新 sporttery_match_odds（source=titan007）
```

### 2.4 scoring 任务详细流程

```
ScoringService.compute_for_date(today)
ScoringService.compute_for_date(tomorrow)
  → 读取 sporttery_matches + odds + team_stats
  → 计算 6 维评分（欧赔/亚盘/大小球/战意/平赔压缩/球队状态）
  → 写入 sporttery_match_scores（含推荐/Kelly 下注比例）
```

### 2.5 覆盖定时时间

激活的 `ModelConfig.scrape_schedule_json` 中若含 `jobs` 键，可按任务名覆盖 cron 字段（`hour`/`minute`）。

---

## 3. 手动任务

### 3.1 历史数据回补（CLI）

```bash
docker compose exec backend python -m app.scripts.backfill \
  --from 2025-10-01 --to 2026-04-22 \
  --delay 0.8 --stats-delay 0.3
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--from` | 必填 | 起始日期（含） |
| `--to` | 必填 | 截止日期（含） |
| `--force` | false | 跳过"已同步"检查，强制重跑 |
| `--delay` | 0.8 | 每日之间间隔（秒） |
| `--no-stats` | false | 不抓球队统计（加速） |
| `--stats-delay` | 0.5 | 每场球队统计间隔（秒） |

**回补流程（每天循环）**：

```
1. GET getUniformMatchResultV1.qry   → 竞彩赛果 + HAD 赔率 + 让球数
2. GET JcResult.aspx                 → Titan007 比赛列表（获取 titan007_match_id）
3. GET oddsData.aspx?cid=1           → 澳门欧赔 + 亚盘（历史终盘）
4. GET getFixedBonusV1.qry           → 竞彩 HHAD 赔率（让球胜平负终盘）
5. GET getMatchHeadV1 + getResultHistoryV1 + getMatchResultV1 → 球队统计
```

### 3.2 种子数据初始化

```bash
docker compose exec backend python -m app.scripts.seed
```

幂等执行：创建默认 `ModelConfig` + `admin` 用户（读取环境变量 `ADMIN_DEFAULT_*`）。

### 3.3 数据库迁移

```bash
docker compose exec backend alembic upgrade head
```

当前迁移链：`0001` → `0002` → … → `0008`（最新：sporttery_matches 增加竞彩赔率列）。

### 3.4 通过 API 手动触发任务

```bash
# 获取 admin token
TOKEN=$(curl -sX POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800000000","password":"Admin@1234"}' | jq -r .token)

# 立即运行某个任务
curl -X POST http://localhost:8000/api/scrape/jobs/schedule/run \
  -H "Authorization: Bearer $TOKEN"
```

可用任务名：`schedule` / `result` / `odds` / `team_stats` / `scoring`

### 3.5 手动计算评分

```bash
curl -X POST "http://localhost:8000/api/scores/compute?date=2026-04-23" \
  -H "Authorization: Bearer $TOKEN"
```

可选参数 `model_config_id=N`，不传则用当前激活模型。

### 3.6 清理数据重跑

```bash
docker compose exec -e PYTHONPATH=/app -w /app backend python -c "
from app.core.database import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    db.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
    db.execute(text('TRUNCATE TABLE sporttery_match_team_stats'))
    db.execute(text('TRUNCATE TABLE sporttery_match_odds'))
    db.execute(text('TRUNCATE TABLE sporttery_match_results'))
    db.execute(text('DELETE FROM sporttery_matches'))
    db.execute(text('DELETE FROM scrape_logs'))
    db.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
    db.commit()
    print('清理完成')
"
```

---

## 4. 数据抓取器详解

### 4.1 数据源总览

```
竞彩网 (sporttery.cn)
  ├─ getMatchCalculatorV1.qry    → 新赛程 + 竞彩 HAD/HHAD 赔率
  ├─ getUniformMatchResultV1.qry → 历史赛果 + HAD 赔率
  ├─ getFixedBonusV1.qry         → HHAD 赔率历史（终盘）
  ├─ getMatchHeadV1.qry          → 球队排名/赛季战绩
  ├─ getResultHistoryV1.qry      → 交锋记录
  └─ getMatchResultV1.qry        → 近期战绩（生成 form 字符串）

Titan007 (jc.titan007.com)
  ├─ xml/bf_jc.txt               → 实时比赛列表（ID 映射）
  ├─ xml/goallottery1.txt        → 实时澳门欧赔+亚盘
  ├─ handle/JcResult.aspx        → 历史比赛列表
  └─ handle/oddsData.aspx?cid=1  → 历史澳门欧赔+亚盘（终盘）
```

### 4.2 赔率存储策略

| 表 | 存什么 | 用途 |
|----|--------|------|
| `sporttery_matches.had_*` | 竞彩官网胜平负赔率 | 计算奖金（返奖率低，非真实概率） |
| `sporttery_matches.hhad_*` | 竞彩官网让球胜平负赔率 | 计算让球盘奖金 |
| `sporttery_match_odds` (source=titan007) | 澳门欧赔+亚盘 | **模型评分使用**（更接近真实概率） |

### 4.3 oddsData.aspx 欧赔格式

```
section[2]: id ^ 初和 ^ 初主 ^ 初客 ^ 即和 ^ 即主 ^ 即客
                Draw   Home   Away   Draw   Home   Away
```

> 注意：列顺序为 Draw/Home/Away（已验证），非 Home/Draw/Away。

### 4.4 抓取器类列表

| 类名 | 文件 | 数据源 | 产出表 |
|------|------|--------|--------|
| `SportterySchedule` | `scrapers/sporttery/schedule.py` | `getMatchCalculatorV1.qry` | `sporttery_matches` |
| `SportteryResult` | `scrapers/sporttery/result.py` | `getUniformMatchResultV1.qry` | `sporttery_matches` + `sporttery_match_results` |
| `Titan007Odds` | `scrapers/titan007/odds.py` | `bf_jc.txt` + `goallottery1.txt` | `sporttery_match_odds` |
| `fetch_stats_for_mid` | `scrapers/sporttery/team_stats.py` | 3 个竞彩 API | `sporttery_match_team_stats` |

---

## 5. 数据模型与表结构

### 5.1 sporttery_matches（比赛主表）

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | BIGINT PK | **12 位逻辑 ID**（日期+星期+编号，如 202604190005） |
| `sporttery_match_id` | VARCHAR | 竞彩网内部 matchId（如 2039279） |
| `match_date` | DATETIME | 开赛时间 |
| `league_id` | INT FK → leagues | 联赛 |
| `home_team` / `away_team` | VARCHAR | 主客队名 |
| `round` | VARCHAR | 竞彩编号（如"周日005"） |
| `status` | ENUM | scheduled / in_progress / finished |
| `had_h` / `had_d` / `had_a` | DECIMAL(6,3) | 竞彩胜/平/负赔率 |
| `hhad_h` / `hhad_d` / `hhad_a` | DECIMAL(6,3) | 竞彩让球胜/平/负赔率 |
| `hhad_goal_line` | DECIMAL(4,1) | 让球数（如 -1, +1） |

### 5.2 sporttery_match_odds（真实赔率表）

| 列 | 类型 | 说明 |
|----|------|------|
| `match_id` | BIGINT FK → sporttery_matches | 比赛逻辑 ID |
| `source` | VARCHAR | 数据源（titan007） |
| `win_odds` / `draw_odds` / `lose_odds` | DECIMAL | 主胜/和/客胜赔率 |
| `handicap_value` | DECIMAL | 亚盘盘口 |
| `win_handicap_odds` / `lose_handicap_odds` | DECIMAL | 亚盘水位 |
| `asian_handicap` | VARCHAR | 亚盘描述 |
| `total_goals` | DECIMAL | 大小球盘口 |

### 5.3 sporttery_match_results（赛果表）

| 列 | 类型 | 说明 |
|----|------|------|
| `match_id` | BIGINT FK | 比赛逻辑 ID |
| `home_score` / `away_score` | INT | 全场比分 |
| `result` | VARCHAR | home_win / draw / away_win |
| `handicap_result` | VARCHAR | 让球后结果 |

### 5.4 sporttery_match_team_stats（球队统计表）

| 列 | 说明 |
|----|------|
| `home_rank` / `away_rank` | 联赛排名 |
| `home_season_wins/draws/losses` | 主队赛季总战绩 |
| `home_home_wins/draws/losses` | 主队主场战绩 |
| `away_away_wins/draws/losses` | 客队客场战绩 |
| `home_recent_form` / `away_recent_form` | 近 6 场走势（如"WDLWWL"） |
| `h2h_home_wins` / `h2h_draws` / `h2h_away_wins` | 交锋记录 |

### 5.5 sporttery_match_scores（评分表）

| 列 | 说明 |
|----|------|
| `match_id` / `model_config_id` / `user_id` | 三维关联 |
| 6 维分数 | `euro_score` / `asian_score` / `goals_score` / `intent_score` / `draw_pressure_score` / `team_stats_score` |
| `total_score` | 总分（满分 120） |
| `bet_type` | draw / handicap_draw / null |
| `kelly_pct` | Kelly 下注比例 |
| `is_recommended` | 是否推荐 |
| `actual_hit` / `bet_amount` / `notes` | 复盘字段 |

### 5.6 其他表

| 表 | 说明 |
|----|------|
| `leagues` | 联赛（name, country, draw_rate_tier） |
| `users` | 用户（phone, role, bankroll_cny） |
| `model_configs` | 模型配置（权重/阈值/Kelly 分带，`is_active`） |
| `backtest_sessions` | 回测会话（日期范围/ROI/权益曲线） |
| `scrape_logs` | 抓取日志（source, job_name, status, error） |

---

## 6. API 端点全表

### 6.1 公开接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/auth/login` | 登录（手机号+密码 → JWT） |

### 6.2 需登录（member + admin）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/me` | 当前用户 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/scores/today` | 今日评分 |
| GET | `/api/scores/by-date?d=YYYY-MM-DD` | 按日期查评分 |
| GET | `/api/scores/{id}/breakdown` | 评分明细（6 维） |
| POST | `/api/backtest` | 创建回测 |
| GET | `/api/backtest` | 回测列表（member 仅本人） |
| GET | `/api/backtest/{id}` | 回测详情 |
| GET | `/api/backtest/compare?a=X&b=Y` | 对比两个回测 |
| GET | `/api/model-configs` | 模型列表 |
| GET | `/api/model-configs/active` | 当前激活模型 |
| GET | `/api/model-configs/{id}` | 模型详情 |
| GET | `/api/reviews` | 复盘列表 |
| GET | `/api/reviews/{score_id}` | 复盘详情 |

### 6.3 仅 admin

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/scores/compute` | 手动触发评分计算 |
| PUT | `/api/scores/{id}` | 覆写评分（notes/bet_amount/actual_hit） |
| GET | `/api/scrape/jobs` | 查看所有可调度任务 |
| GET | `/api/scrape/logs` | 抓取日志 |
| POST | `/api/scrape/jobs/{name}/run` | 手动运行任务 |
| POST | `/api/model-configs` | 创建模型 |
| PATCH | `/api/model-configs/{id}` | 编辑模型 |
| POST | `/api/model-configs/{id}/clone` | 克隆模型 |
| POST | `/api/model-configs/{id}/activate` | 激活模型（同步重算当日评分） |
| PATCH | `/api/reviews/{score_id}` | 复盘回写（带乐观锁） |
| GET/POST/PATCH/DELETE | `/api/users/*` | 用户管理 |

---

## 7. 前端页面

| 路由 | 页面 | 权限 | 功能 |
|------|------|------|------|
| `/login` | 登录 | 公开 | 手机号+密码登录 |
| `/` | 首页 | 登录 | 重定向到 Dashboard |
| `/dashboard` | 今日推荐 | 登录 | 评分列表、明细抽屉、"已结束" Tab |
| `/backtest` | 回测 | 登录 | 创建回测、查看历史、双模型对比 |
| `/model` | 模型配置 | admin | 查看/编辑/克隆/激活模型 |
| `/review` | 复盘 | 登录(写需admin) | 批量复盘、汇总条 |
| `/admin/scrape` | 抓取管理 | admin | 5 个任务卡片、日志表、手动运行 |

---

## 8. 配置项

### 8.1 环境变量（`.env`）

| 变量 | 示例 | 说明 |
|------|------|------|
| `MYSQL_HOST` | mysql | 数据库主机 |
| `MYSQL_PORT` | 3306 | 数据库端口 |
| `MYSQL_USER` | sporttery | 数据库用户 |
| `MYSQL_PASSWORD` | *** | 数据库密码 |
| `MYSQL_DATABASE` | sporttery_10x | 数据库名 |
| `JWT_SECRET` | *** | JWT 签名密钥 |
| `JWT_ALGORITHM` | HS256 | JWT 算法 |
| `JWT_EXPIRE_MINUTES` | 43200 | Token 有效期（默认 30 天） |
| `ADMIN_DEFAULT_PHONE` | 13800000000 | 种子管理员手机号 |
| `ADMIN_DEFAULT_NAME` | admin | 种子管理员名称 |
| `ADMIN_DEFAULT_PASSWORD` | Admin@1234 | 种子管理员密码 |
| `TIMEZONE` | Asia/Shanghai | 系统时区 |
| `LOG_LEVEL` | INFO | 日志级别 |
| `CORS_ORIGINS` | http://localhost:3000 | 允许跨域的前端地址 |
| `BACKEND_PORT` | 8000 | 后端暴露端口 |
| `FRONTEND_PORT` | 3000 | 前端暴露端口 |
| `NEXT_PUBLIC_API_BASE_URL` | http://backend:8000 | 前端调后端地址 |

### 8.2 模型配置（数据库 model_configs 表）

```json
{
  "weights_json": {
    "euro": 25, "asian": 20, "goals": 20,
    "intent": 15, "draw_pressure": 20, "team_stats": 20
  },
  "thresholds_json": {
    "recommend_total_score": 84,
    "draw_min_score": 84,
    "handicap_draw_min_score": 78
  },
  "kelly_bands_json": [
    {"min": 96,  "max": 120, "pct": 0.02},
    {"min": 84,  "max": 96,  "pct": 0.015},
    {"min": 78,  "max": 84,  "pct": 0.01}
  ]
}
```

---

## 9. 常用运维命令

### 9.1 容器管理

```bash
docker compose ps                      # 查看容器状态
docker compose up -d                   # 启动全部
docker compose restart backend         # 重启后端
docker compose build backend --no-cache # 重建后端镜像
docker compose logs -f scheduler       # 查看调度器日志
```

### 9.2 数据检查

```bash
# 查看数据完整性
docker compose exec backend python -c "
from app.core.database import SessionLocal
from sqlalchemy import text
with SessionLocal() as db:
    rows = db.execute(text('''
        SELECT status, COUNT(*) total,
               SUM(CASE WHEN o.id IS NOT NULL THEN 1 ELSE 0 END) has_odds,
               SUM(CASE WHEN ts.id IS NOT NULL THEN 1 ELSE 0 END) has_stats,
               SUM(CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END) has_result
        FROM sporttery_matches m
        LEFT JOIN sporttery_match_odds o ON o.match_id = m.id
        LEFT JOIN sporttery_match_team_stats ts ON ts.match_id = m.id
        LEFT JOIN sporttery_match_results r ON r.match_id = m.id
        GROUP BY status
    ''')).fetchall()
    for r in rows:
        print(f'{r[0]}: total={r[1]} odds={r[2]} stats={r[3]} result={r[4]}')
"
```

### 9.3 手动执行任务（容器内）

```bash
# 赛程（一条龙：赛程+赔率+球队统计）
docker compose exec -e PYTHONPATH=/app backend python -c "
from app.core.database import SessionLocal
from app.scheduler.jobs import run_schedule_job
print(run_schedule_job(SessionLocal))
"

# 赛果
docker compose exec -e PYTHONPATH=/app backend python -c "
from app.core.database import SessionLocal
from app.scheduler.jobs import run_result_job
print(run_result_job(SessionLocal))
"

# 赔率
docker compose exec -e PYTHONPATH=/app backend python -c "
from app.core.database import SessionLocal
from app.scheduler.jobs import run_odds_job
print(run_odds_job(SessionLocal))
"

# 评分
docker compose exec -e PYTHONPATH=/app backend python -c "
from app.core.database import SessionLocal
from app.scheduler.jobs import run_scoring_job
print(run_scoring_job(SessionLocal))
"
```

### 9.4 历史回补

```bash
# 回补近 30 天
docker compose exec backend python -m app.scripts.backfill \
  --from 2026-03-24 --to 2026-04-23 --force --delay 1.0

# 仅回补比赛+赔率，跳过球队统计（快速）
docker compose exec backend python -m app.scripts.backfill \
  --from 2026-03-24 --to 2026-04-23 --force --no-stats --delay 0.5
```

### 9.5 数据库直查

```bash
# 进入 MySQL
docker compose exec mysql mysql -u sporttery -p sporttery_10x

# 常用查询
SELECT COUNT(*) FROM sporttery_matches;
SELECT * FROM scrape_logs ORDER BY id DESC LIMIT 10;
SELECT id, home_team, away_team, total_score, bet_type, kelly_pct
  FROM sporttery_match_scores WHERE is_recommended = 1 ORDER BY total_score DESC;
```
