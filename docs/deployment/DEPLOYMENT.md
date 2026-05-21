# Sporttery 10x · 部署文档

**版本**：2026-04-27（P7 + P8 H1 已上线）
**目标读者**：运维 / 搭建 Home Server 的个人玩家
**适用环境**：Linux、macOS、WSL2；amd64 / arm64 均可

---

## 目录

- [1. 架构拓扑](#1-架构拓扑)
- [2. 前置条件](#2-前置条件)
- [3. 环境变量](#3-环境变量)
- [4. Docker Compose 一键部署（推荐）](#4-docker-compose-一键部署推荐)
- [5. 本地开发部署（无 Docker）](#5-本地开发部署无-docker)
- [6. 数据库迁移与种子数据](#6-数据库迁移与种子数据)
- [7. 首个管理员账号](#7-首个管理员账号)
- [8. 定时任务（Scheduler）调度配置](#8-定时任务scheduler调度配置)
- [9. 升级与回滚](#9-升级与回滚)
- [10. 备份与恢复](#10-备份与恢复)
- [11. 日志与监控](#11-日志与监控)
- [12. 反向代理 / HTTPS（可选）](#12-反向代理--https可选)
- [13. 常见故障排查](#13-常见故障排查)

---

## 1. 架构拓扑

```
                    ┌──────────────┐
         :3000 ────▶│   frontend   │ Next.js 14 standalone
                    └──────┬───────┘
                           │ NEXT_PUBLIC_API_BASE_URL
                           ▼
                    ┌──────────────┐
         :8000 ────▶│    backend   │ FastAPI + Uvicorn
                    └──────┬───────┘
                           │ SQLAlchemy
                           ▼
                    ┌──────────────┐
         :3306 ────▶│    mysql     │ 8.0 + utf8mb4
                    └──────────────┘
                           ▲
                    ┌──────┴───────┐
                    │  scheduler   │ APScheduler (blocking)
                    └──────────────┘
```

4 个容器共一个 Docker Compose network；默认只暴露 3000/8000/3306 到 host，scheduler 无端口。

---

## 2. 前置条件

| 软件 | 最低版本 | 推荐 | 用途 |
| --- | --- | --- | --- |
| Docker | 24.x | 27.x | 容器运行 |
| Docker Compose | v2 | v2.29+ | 编排 |
| Make | 任意 | - | Makefile 快捷命令 |
| Git | 2.30+ | 最新 | 拉代码 |

**可选（非 Docker 开发）**：Python 3.11、Node 20、pnpm 9、MySQL 8。

**机器规格**：建议 2 vCPU / 4GB RAM / 20GB 磁盘。树莓派 4B 也能跑（arm64）。

---

## 3. 环境变量

项目根目录复制一份：

```bash
cp .env.example .env
```

关键字段（来源 `.env.example`）：

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `MYSQL_ROOT_PASSWORD` | `rootpass` | 只用于容器初始化 |
| `MYSQL_DATABASE` | `sporttery_10x` | 业务库名 |
| `MYSQL_USER` / `MYSQL_PASSWORD` | `sporttery` / `sporttery_pass` | 应用账号 |
| `MYSQL_HOST` | `mysql`（容器内部）/ `localhost`（宿主） | 连接地址 |
| `MYSQL_PORT` | `3306` | - |
| `JWT_SECRET` | **必须更换** 为 ≥ 32 位随机串 | JWT 签名密钥 |
| `JWT_ALGORITHM` | `HS256` | - |
| `JWT_EXPIRE_MINUTES` | `43200`（30d） | token 寿命 |
| `TIMEZONE` | `Asia/Shanghai` | scheduler / MySQL 时区 |
| `LOG_LEVEL` | `INFO` | `DEBUG` 用于排错 |
| `BACKEND_PORT` | `8000` | host 端口，可改 |
| `FRONTEND_PORT` | `3000` | host 端口，可改 |
| `NEXT_PUBLIC_API_BASE_URL` | 部署域名 e.g. `https://api.example.com` | 前端构建时注入 |
| `ADMIN_DEFAULT_*` | 初始 admin 引导值 | 见 §7 |

> **安全建议**：生产必须覆盖 `JWT_SECRET` / `MYSQL_*_PASSWORD` / `ADMIN_DEFAULT_PASSWORD`。不要把 `.env` 提交到仓库（已在 `.gitignore`）。

---

## 4. Docker Compose 一键部署（推荐）

### 4.1 首次启动

```bash
git clone <repo> sporttery_10x && cd sporttery_10x
cp .env.example .env
# 编辑 .env，替换 JWT_SECRET / MYSQL_*_PASSWORD / NEXT_PUBLIC_API_BASE_URL
make dev        # 等价 docker compose up -d --build
make ps         # 检查 4 个容器健康
```

第一次构建约 3-6 分钟。

### 4.2 健康检查

```bash
curl -sf http://localhost:8000/health     # {"status":"ok"}
curl -sfI http://localhost:3000/ | head -1  # HTTP/1.1 200 OK
docker compose exec mysql mysqladmin ping -uroot -p"$MYSQL_ROOT_PASSWORD"
```

### 4.3 迁移 + 种子（首次必做）

backend 容器启动时**不会**自动跑迁移，需手动触发：

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed
```

`seed.py` 幂等：若 `default` ModelConfig 或 admin 用户已存在，会跳过。

### 4.4 常用操作

```bash
make logs           # 跟踪全部容器日志
make ps             # 状态
make down           # 停止 + 删容器（保留 volume）
make clean          # 停止 + 删容器 + 删 volume（⚠ 数据丢失）
docker compose logs -f scheduler    # 只看 scheduler
docker compose restart backend      # 重启单个服务
```

### 4.5 升级代码

```bash
git pull
docker compose build backend frontend scheduler
docker compose up -d
docker compose exec backend alembic upgrade head   # 若有新 migration
```

---

## 5. 本地开发部署（无 Docker）

适合调试代码或 Home Server 习惯用 systemd 的场景。

### 5.1 安装依赖

```bash
make install-backend    # backend/.venv + pip install
make install-frontend   # pnpm install
```

手动：

```bash
cd backend && python3.11 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip pip-tools
pip install -r requirements.txt

cd ../frontend && corepack enable && corepack prepare pnpm@9 --activate
pnpm install
```

### 5.2 本机 MySQL

可用 host 上已有的 MySQL 8，也可只跑一个 docker MySQL：

```bash
docker run -d --name sporttery_mysql -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=sporttery_10x \
  -e MYSQL_USER=sporttery -e MYSQL_PASSWORD=sporttery_pass \
  mysql:8.0 \
  --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci \
  --default-time-zone=+08:00
```

然后把 `.env` 里 `MYSQL_HOST=localhost`。

### 5.3 启动三进程

三个终端并行：

```bash
# 终端 A：backend
cd backend && . .venv/bin/activate
alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 B：scheduler
cd backend && . .venv/bin/activate
python -m app.scheduler.main

# 终端 C：frontend
cd frontend && pnpm dev
```

访问 <http://localhost:3000>。

---

## 6. 数据库迁移与种子数据

### 6.1 迁移命令

```bash
# 升级到最新
docker compose exec backend alembic upgrade head

# 查看当前版本
docker compose exec backend alembic current

# 回滚一版
docker compose exec backend alembic downgrade -1

# 回滚到具体 revision
docker compose exec backend alembic downgrade 0003
```

当前迁移链：

```
0001_initial_schema
  → 0002_scrape_status_running
  → 0003_match_scores_unique
  → 0004_backtest_fields
  → 0005_normalize_legacy_weights
  → 0006_model_config_active_parent   (HEAD)
```

`0006` 给 `model_configs` 加 `is_active`（Boolean）、`parent_id`（FK self，存克隆血缘）。升级后 `seed.py` 会保证至少一条 `is_active=true`。

### 6.2 种子数据

`python -m app.scripts.seed` 完成：

1. 创建 `default` ModelConfig（最新校准权重 + 默认阈值 + 默认 kelly_bands + `is_active=true`）
2. 创建初始 admin（使用 `.env` 中的 `ADMIN_DEFAULT_*`）

两步均幂等，可重复运行。若已有多条 ModelConfig 但无一条 active，seed 会把 `id` 最小的那条标 active（不会覆盖已有 active）。

---

## 7. 首个管理员账号

### 方式 A：环境变量引导

已配置在 `.env` 的 `ADMIN_DEFAULT_*` 会被 `seed.py` 使用：

```bash
docker compose exec backend python -m app.scripts.seed
# 若 13800000000 不存在 → 自动创建 admin
```

### 方式 B：交互式 CLI

```bash
docker compose exec -it backend \
  python -m app.cli.create_admin --phone 13900000000 --name bob
# 若不带 --password 会提示输入
```

**密码规则**：长度 8-64，必须包含字母和数字。手机号必须匹配 `^1[3-9]\d{9}$`。

### 登录

```bash
curl -sX POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800000000","password":"Admin@1234"}'
```

---

## 8. 定时任务（Scheduler）调度配置

默认 cron（在 `app/scheduler/main.py:DEFAULT_CRONS`）：

| Job | 默认 cron | 职责 |
| --- | --- | --- |
| `schedule` | 每天 08:30 | 抓体彩赛程（当日 + 近期） |
| `result` | 每天 23:30 | 抓体彩赛果 |
| `odds` | 每 2 小时的 15 分 | 抓 titan007 赔率 |
| `team_stats` | 每天 09:00 | 抓体彩球队状态（按 mid 维度） |
| `scoring` | 每天 09:15 | 运行评分引擎落 `match_scores` |

### 覆盖默认 cron

可在 `ModelConfig.scrape_schedule_json` 中写：

```json
{
  "jobs": {
    "odds": {"hour": "*/1", "minute": 0},
    "scoring": {"hour": 10, "minute": 0}
  }
}
```

下次 scheduler 启动时自动合并；**改完需重启 scheduler 容器**：

```bash
docker compose restart scheduler
```

### 手动触发（无需等 cron）

```bash
# 管理员 API
curl -X POST http://localhost:8000/api/scrape/jobs/schedule/run \
  -H "Authorization: Bearer $TOKEN"
```

或在 `/admin/scrape` 页面点击 job 卡片。

> **激活模型即时重算**：P8 H1 后，`POST /api/model-configs/{id}/activate` 会同步调用 `ScoringService.compute_for_date(today, new_id)`，响应体返回 `scores_recomputed: N`。这意味着**不等 09:15 cron**，Dashboard 刷新即可看到新模型的结果。`scoring` 定时任务仍每日兜底，二者幂等。

---

## 8.5 P7+ 新增路由速览

所有下列路由默认走 `/api/` 前缀，部署不需额外配置：

| 路由 | 方法 | 权限 | 说明 |
| --- | --- | --- | --- |
| `/api/model-configs` | GET | 登录 | 列表（带 `is_active` / `parent_id`） |
| `/api/model-configs/active` | GET | 登录 | 当前激活版本 |
| `/api/model-configs/{id}` | GET / PATCH | 读登录 / 写 admin | 详情 / 编辑权重阈值 |
| `/api/model-configs/{id}/clone` | POST | admin | 以某版本为 parent 克隆新版本 |
| `/api/model-configs/{id}/activate` | POST | admin | 激活 + 同步重算今日评分（返回 `scores_recomputed`） |
| `/api/reviews` | GET | 登录 | 已结束场次列表（支持 date/league/hit 过滤） |
| `/api/reviews/{score_id}` | GET / PATCH | 读登录 / 写 admin | 查询 / 回写 `actual_hit`、`bet_amount`、`notes`；PATCH 支持 `expected_updated_at` 乐观锁 |

前端页面：`/model`（模型配置 UI）、`/review`（批量复盘 UI），Dashboard 新增「已结束」Tab 作为轻量入口。

---

## 9. 升级与回滚

### 升级

```bash
git fetch --all
git checkout <new-tag>
docker compose build
docker compose up -d
docker compose exec backend alembic upgrade head
```

### 回滚

```bash
docker compose exec backend alembic downgrade <previous-rev>
git checkout <previous-tag>
docker compose build
docker compose up -d
```

注意：如果新版本删了字段，回滚前应当有数据备份。

---

## 10. 备份与恢复

### 10.1 备份

```bash
# 数据库
docker compose exec mysql \
  mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" \
  --single-transaction --routines --triggers \
  sporttery_10x > backup_$(date +%Y%m%d).sql

# 压缩
gzip backup_$(date +%Y%m%d).sql
```

建议配一个 cron：每天凌晨 3 点执行并同步到对象存储（S3 / 阿里云 OSS）。

### 10.2 恢复

```bash
docker compose exec -T mysql \
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" sporttery_10x < backup_20260421.sql
```

### 10.3 Volume 级备份

```bash
docker run --rm \
  -v sporttery_mysql_data:/from \
  -v "$PWD":/to \
  alpine tar czf /to/mysql_volume_$(date +%Y%m%d).tar.gz -C /from .
```

---

## 11. 日志与监控

### 日志位置

- 容器 stdout：`docker compose logs -f <service>`
- Scheduler job 状态：查库 `SELECT source,status,records,message,created_at FROM scrape_logs ORDER BY id DESC LIMIT 50;`
- backend 也会输出到 `backend/logs/`（如挂载）

### 推荐监控指标

| 指标 | 采集方式 |
| --- | --- |
| `/health` 可用性 | HTTP uptime 监控（UptimeRobot 等） |
| 最近一次 job 成功时间 | `SELECT MAX(created_at) FROM scrape_logs WHERE source='sporttery' AND status='success'` |
| MySQL 连接数 | `SHOW STATUS LIKE 'Threads_connected'` |
| 容器 healthcheck | `docker inspect --format='{{.State.Health.Status}}' sporttery_backend` |

没有内置 Prometheus exporter；如需要可接 `mysqld_exporter` + `cadvisor`。

---

## 12. 反向代理 / HTTPS（可选）

生产部署建议用 Caddy 或 Nginx：

### Caddy 示例 `Caddyfile`

```caddy
sporttery.example.com {
  encode zstd gzip
  reverse_proxy localhost:3000
}

api.sporttery.example.com {
  encode zstd gzip
  reverse_proxy localhost:8000
}
```

然后在 `.env`：

```
NEXT_PUBLIC_API_BASE_URL=https://api.sporttery.example.com
```

重新构建 `frontend`：

```bash
docker compose build frontend && docker compose up -d frontend
```

---

## 13. 常见故障排查

| 症状 | 排查 |
| --- | --- |
| `docker compose ps` 看到 `backend (unhealthy)` | `docker compose logs backend`，通常是 MySQL 未就绪或迁移未执行 |
| 前端页面空白 / 404 | 检查 `NEXT_PUBLIC_API_BASE_URL`；rebuild frontend |
| 登录返回 401 | 检查用户是否创建；`JWT_SECRET` 是否在两个容器一致 |
| scheduler 不执行 | 查 scheduler 日志；检查 `TIMEZONE` 是否 `Asia/Shanghai`；手动 `POST /api/scrape/jobs/{name}/run` 验证 job 本身 |
| 回测命中率为 0 | 多半是老 `ModelConfig.weights_json={1.0}` 未升级。跑 `alembic upgrade head`（0005 自动修） |
| 激活模型后 Dashboard 未变 | 响应体已返回 `scores_recomputed`，但浏览器还缓存旧列表。Dashboard 点右上「刷新」或 `/api/scores/today` 直查 |
| 复盘 PATCH 报 409 `conflict` | 有另一个 admin 同时改了这条。前端会自动重新拉取列表，再次提交即可（P8 H1 TD-1） |
| 同名克隆报 400 `model_config name already exists` | P8 H1 TD-2 新增 `ModelConfig.name` 唯一约束，改个独立名字即可 |
| `/admin/scrape` 显示 403 | 当前 token 不是 admin，用 create_admin CLI 新建或 `UPDATE users SET role='admin' WHERE phone='...'` |
| MySQL 中文乱码 | 确认 compose 命令行有 `--character-set-server=utf8mb4`；检查连接串 |
| titan007 抓取失败 | 目标站反爬。查 `scrape_logs.message`；可暂停 job、手动补数 |
| 磁盘占满 | `docker system df` / `docker system prune -a`，MySQL volume 单独评估 |

---

## 附录 A · Dockerfile 要点

- **backend**：基于 `python:3.11-slim`，安装 `default-libmysqlclient-dev`，Uvicorn 单进程（多工并发可在 compose 加 `command: uvicorn app.main:app --workers 2`）
- **frontend**：多阶段构建，最终产物运行在 `node:20-alpine`，依赖由 pnpm standalone fetch
- **healthcheck**：backend `curl /health`，frontend `wget /`，mysql `mysqladmin ping`

## 附录 B · 非 Docker 产线部署（systemd）

如果完全不走 Docker，可以把三个进程放到 systemd：

```ini
# /etc/systemd/system/sporttery-backend.service
[Unit]
Description=Sporttery backend
After=network.target mysql.service
[Service]
User=sporttery
WorkingDirectory=/opt/sporttery_10x/backend
EnvironmentFile=/opt/sporttery_10x/.env
ExecStart=/opt/sporttery_10x/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
[Install]
WantedBy=multi-user.target
```

同理复制 `sporttery-scheduler.service`（ExecStart 换成 `python -m app.scheduler.main`）与 `sporttery-frontend.service`（ExecStart 用 `pnpm start`）。
