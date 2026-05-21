# P1 · 项目脚手架与基础设施 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 `sporttery_10x` monorepo 的最小可运行骨架——前端能打开落地页、后端能返回 `/health`、MySQL 能连上、CI 能跑通。

**Architecture:** Monorepo 两个子项目 `frontend/`（Next.js 14 + TS + Tailwind + shadcn）和 `backend/`（FastAPI + SQLAlchemy），通过根目录的 `docker-compose.yml` + `Makefile` 统一编排；MySQL 8.0 作为唯一数据库；GitHub Actions 提供 Lint + Test 两条 pipeline。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 · Node 20 · Next.js 14 · pnpm · Tailwind · shadcn/ui · MySQL 8.0 · Docker Compose · GitHub Actions

**Decisions Reference:** `docs/superpowers/brainstorm/2026-04-21-decisions.md`

---

## 前置说明

- **工作目录**：`/Users/wushunxin/wusx/sporttery_10x`（已存在 `docs/` 和 `平让平竞彩交易模型手册.md`，其它文件/目录都要新建）
- **Git 状态**：未初始化，Task 1 第一步 `git init`
- **分支**：本计划在 `feat/p1-scaffolding` 分支执行，完成后合并回 `main`
- **Shell 假设**：执行者有 `pnpm`、`docker`、`docker compose`、`python3.11`、`git` 可用；如缺失，先安装再继续
- **标准 import 风格**：前端使用 Standard.js 风格（2 空格、单引号、无分号、`===`），后端使用 PEP8 via Ruff

---

## 文件总览

本计划结束时，仓库根目录应包含：

```
sporttery_10x/
├── .github/workflows/
│   ├── backend.yml
│   └── frontend.yml
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── config.py
│   │       └── database.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_health.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── requirements.in
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/ui/        (由 shadcn init 生成)
│   ├── lib/
│   │   └── api.ts
│   ├── tests/
│   │   └── smoke.test.tsx
│   ├── .eslintrc.json
│   ├── .prettierrc
│   ├── Dockerfile
│   ├── next.config.js
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── postcss.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── vitest.config.ts
├── docs/                      (已存在)
├── .env.example
├── .gitignore
├── .dockerignore
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## Task 1：仓库初始化与根目录基础文件

**Files:**
- Create: `.gitignore`
- Create: `.dockerignore`
- Create: `README.md`
- Create: `.env.example`

- [ ] **Step 1.1：初始化 Git 仓库并创建 feature 分支**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git init -b main
git checkout -b feat/p1-scaffolding
```

Expected: 终端输出 `Initialized empty Git repository ...`，并切到 `feat/p1-scaffolding` 分支。

- [ ] **Step 1.2：写 `.gitignore`**

创建 `/.gitignore`：

```gitignore
# OS
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
*.swp

# Env
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
htmlcov/
.coverage
coverage.xml

# Node
node_modules/
.next/
out/
dist/
*.log
.pnpm-debug.log*
.eslintcache

# Docker
docker-compose.override.yml

# Logs
backend/logs/
```

- [ ] **Step 1.3：写 `.dockerignore`**

创建 `/.dockerignore`：

```
.git
.gitignore
node_modules
__pycache__
.venv
venv
.pytest_cache
.ruff_cache
.next
docs
*.md
.env
.env.*
docker-compose*.yml
```

- [ ] **Step 1.4：写 `.env.example`**

创建 `/.env.example`：

```
# ===== MySQL =====
MYSQL_ROOT_PASSWORD=rootpass
MYSQL_DATABASE=sporttery_10x
MYSQL_USER=sporttery
MYSQL_PASSWORD=sporttery_pass
MYSQL_HOST=mysql
MYSQL_PORT=3306

# ===== Backend =====
JWT_SECRET=dev-secret-change-me
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200
TIMEZONE=Asia/Shanghai
LOG_LEVEL=INFO
BACKEND_PORT=8000

# ===== Frontend =====
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
FRONTEND_PORT=3000
```

- [ ] **Step 1.5：写最小 `README.md`**

创建 `/README.md`：

````markdown
# Sporttery 10x · 竞彩交易决策系统

基于概率模型的平/让平竞彩交易决策 Web 系统。

## 架构

- **frontend/** — Next.js 14 + TypeScript + Tailwind + shadcn/ui
- **backend/** — FastAPI + SQLAlchemy + APScheduler
- **MySQL 8.0** — 主数据库
- **Docker Compose** — 一键启动

## 快速开始

```bash
cp .env.example .env
make install   # 安装前后端依赖
make dev       # docker-compose up
```

访问：

- 前端：http://localhost:3000
- 后端：http://localhost:8000/docs

## 项目规划

详见 `docs/superpowers/`。
````

- [ ] **Step 1.6：首次提交**

```bash
git add .gitignore .dockerignore README.md .env.example
git commit -m "chore: initial repo scaffolding (gitignore, env template, readme)"
```

Expected: 提交成功，`git log --oneline` 看到一条 commit。

---

## Task 2：Docker Compose + MySQL 服务

**Files:**
- Create: `docker-compose.yml`
- Create: `Makefile`

- [ ] **Step 2.1：写 `docker-compose.yml`（仅 MySQL）**

创建 `/docker-compose.yml`：

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: sporttery_mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      TZ: Asia/Shanghai
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --default-time-zone=+08:00
    ports:
      - '3306:3306'
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ['CMD', 'mysqladmin', 'ping', '-h', 'localhost', '-uroot', '-p${MYSQL_ROOT_PASSWORD}']
      interval: 5s
      timeout: 5s
      retries: 20

volumes:
  mysql_data:
    name: sporttery_mysql_data
```

- [ ] **Step 2.2：写最小 `Makefile`（只含 Docker 命令）**

创建 `/Makefile`（注意：Make 语法要求 recipe 以 TAB 开头）：

```makefile
.PHONY: help env up down logs ps clean

help:
	@echo "Targets:"
	@echo "  env         Copy .env.example to .env (if missing)"
	@echo "  up          docker compose up -d"
	@echo "  down        docker compose down"
	@echo "  logs        docker compose logs -f"
	@echo "  ps          docker compose ps"
	@echo "  clean       Stop services and remove volumes"

env:
	@test -f .env || cp .env.example .env
	@echo ".env ready"

up: env
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v
```

- [ ] **Step 2.3：验证 MySQL 可启动**

Run:

```bash
cp .env.example .env
docker compose up -d mysql
```

Expected: 输出 `Container sporttery_mysql  Started`。

继续等健康检查通过：

```bash
docker compose ps
```

Expected: `sporttery_mysql` 的 STATUS 列包含 `(healthy)`，若尚未 healthy，sleep 10 秒再查一次。

- [ ] **Step 2.4：验证能登录 MySQL**

Run:

```bash
docker compose exec mysql mysql -usporttery -psporttery_pass sporttery_10x -e "SELECT 1 AS ok;"
```

Expected: 输出

```
+----+
| ok |
+----+
|  1 |
+----+
```

- [ ] **Step 2.5：提交**

```bash
git add docker-compose.yml Makefile
git commit -m "feat(infra): add docker-compose with MySQL 8.0 and root Makefile"
```

---

## Task 3：后端骨架 — 目录结构与依赖定义

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/requirements.in`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 3.1：创建目录骨架**

Run:

```bash
mkdir -p backend/app/api backend/app/core backend/tests backend/logs
touch backend/app/__init__.py backend/app/api/__init__.py backend/app/core/__init__.py backend/tests/__init__.py
touch backend/logs/.gitkeep
```

- [ ] **Step 3.2：写 `backend/pyproject.toml`**

创建 `/backend/pyproject.toml`：

```toml
[project]
name = "sporttery-backend"
version = "0.1.0"
description = "Sporttery 10x backend"
requires-python = ">=3.11,<3.12"

[tool.ruff]
line-length = 100
target-version = "py311"
src = ["app", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]
ignore = ["B008"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra -q --strict-markers"
```

- [ ] **Step 3.3：写 `backend/requirements.in`**

创建 `/backend/requirements.in`：

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
sqlalchemy==2.0.*
pymysql==1.1.*
cryptography==43.*
alembic==1.13.*
pydantic==2.9.*
pydantic-settings==2.6.*
python-jose[cryptography]==3.3.*
passlib[bcrypt]==1.7.*
apscheduler==3.10.*
httpx==0.27.*
beautifulsoup4==4.12.*
lxml==5.3.*
numpy==2.1.*
pandas==2.2.*
structlog==24.4.*
python-dotenv==1.0.*

pytest==8.3.*
pytest-asyncio==0.24.*
ruff==0.7.*
black==24.10.*
httpx-sse==0.4.*
```

- [ ] **Step 3.4：生成锁文件 `requirements.txt`**

Run:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip pip-tools
pip-compile requirements.in -o requirements.txt --quiet
pip install -r requirements.txt
```

Expected: `requirements.txt` 生成，`pip install` 无报错。

- [ ] **Step 3.5：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add backend/pyproject.toml backend/requirements.in backend/requirements.txt backend/app backend/tests backend/logs/.gitkeep
git commit -m "feat(backend): add pyproject, requirements and package skeleton"
```

---

## Task 4：后端 `/health` 端点（TDD）

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 4.1：写失败测试 `tests/test_health.py`**

创建 `/backend/tests/test_health.py`：

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "skipped"}


def test_root_redirects_to_docs():
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/docs"
```

- [ ] **Step 4.2：写 `conftest.py` 让 `app` 可导入**

创建 `/backend/tests/conftest.py`：

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 4.3：运行测试，确认失败**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
source .venv/bin/activate
pytest tests/test_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.main'` 或类似失败信息。

- [ ] **Step 4.4：写 `config.py`**

创建 `/backend/app/core/config.py`：

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="sporttery")
    mysql_password: str = Field(default="sporttery_pass")
    mysql_database: str = Field(default="sporttery_10x")

    jwt_secret: str = Field(default="dev-secret-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=43200)

    timezone: str = Field(default="Asia/Shanghai")
    log_level: str = Field(default="INFO")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4.5：写 `api/health.py`**

创建 `/backend/app/api/health.py`：

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "db": "skipped"}
```

> DB 检查逻辑留给 Task 5 覆盖；先让接口返回 `"db": "skipped"` 通过 Step 4.1 的测试。

- [ ] **Step 4.6：写 `main.py`**

创建 `/backend/app/main.py`：

```python
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Sporttery 10x Backend", version="0.1.0")

app.include_router(health_router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
```

- [ ] **Step 4.7：运行测试，确认通过**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
pytest tests/test_health.py -v
```

Expected: `2 passed` 绿色。

- [ ] **Step 4.8：手动冒烟：启动 uvicorn**

Run：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health
kill %1
```

Expected: `{"status":"ok","db":"skipped"}`。

- [ ] **Step 4.9：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add backend/app backend/tests
git commit -m "feat(backend): add FastAPI app with /health endpoint and tests"
```

---

## Task 5：后端 DB 连接与带 DB 检查的 `/health`

**Files:**
- Create: `backend/app/core/database.py`
- Modify: `backend/app/api/health.py`
- Modify: `backend/tests/test_health.py`

- [ ] **Step 5.1：更新失败测试**

编辑 `/backend/tests/test_health.py`，替换全文为：

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_with_db_status():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db"] in {"ok", "down"}


def test_root_redirects_to_docs():
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/docs"
```

- [ ] **Step 5.2：运行测试（预期失败：返回仍是 `"skipped"`）**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
pytest tests/test_health.py -v
```

Expected: `test_health_returns_ok_with_db_status` FAIL（断言 `"skipped"` 不在 `{"ok","down"}`）。

- [ ] **Step 5.3：写 `database.py`**

创建 `/backend/app/core/database.py`：

```python
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()

engine: Engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_alive() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

- [ ] **Step 5.4：修改 `api/health.py` 调用 `check_db_alive`**

把 `/backend/app/api/health.py` 替换为：

```python
from fastapi import APIRouter

from app.core.database import check_db_alive

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "db": "ok" if check_db_alive() else "down"}
```

- [ ] **Step 5.5：运行测试，确认通过**

前置：确保 MySQL 已启动：

```bash
cd /Users/wushunxin/wusx/sporttery_10x
docker compose up -d mysql
sleep 5
cd backend
MYSQL_HOST=localhost pytest tests/test_health.py -v
```

Expected: `2 passed`。

> `MYSQL_HOST=localhost` 是因为从宿主机跑 pytest 时，MySQL 暴露在 `localhost:3306`。

- [ ] **Step 5.6：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add backend/app/core/database.py backend/app/api/health.py backend/tests/test_health.py
git commit -m "feat(backend): add SQLAlchemy engine and DB liveness check in /health"
```

---

## Task 6：后端 Dockerfile 与 Compose 集成

**Files:**
- Create: `backend/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 6.1：写 `backend/Dockerfile`**

创建 `/backend/Dockerfile`：

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app /app/app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6.2：在 `docker-compose.yml` 增加 backend 服务**

把 `/docker-compose.yml` 整体替换为：

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: sporttery_mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      TZ: Asia/Shanghai
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --default-time-zone=+08:00
    ports:
      - '3306:3306'
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ['CMD', 'mysqladmin', 'ping', '-h', 'localhost', '-uroot', '-p${MYSQL_ROOT_PASSWORD}']
      interval: 5s
      timeout: 5s
      retries: 20

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: sporttery_backend
    restart: unless-stopped
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      MYSQL_HOST: ${MYSQL_HOST}
      MYSQL_PORT: ${MYSQL_PORT}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      JWT_SECRET: ${JWT_SECRET}
      JWT_ALGORITHM: ${JWT_ALGORITHM}
      JWT_EXPIRE_MINUTES: ${JWT_EXPIRE_MINUTES}
      TIMEZONE: ${TIMEZONE}
      LOG_LEVEL: ${LOG_LEVEL}
    ports:
      - '${BACKEND_PORT:-8000}:8000'

volumes:
  mysql_data:
    name: sporttery_mysql_data
```

- [ ] **Step 6.3：构建并启动 backend，验证健康检查**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x
docker compose up -d --build backend
sleep 15
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok","db":"ok"}`。

若返回 `"db":"down"`，检查 `docker compose logs backend` 和 MySQL 是否 healthy。

- [ ] **Step 6.4：提交**

```bash
git add backend/Dockerfile docker-compose.yml
git commit -m "feat(infra): containerize backend and wire into docker-compose"
```

---

## Task 7：前端骨架 — Next.js 14 + Tailwind + shadcn

**Files:**
- Create: `frontend/package.json` (via pnpm create)
- Create: `frontend/app/*`, `frontend/tsconfig.json`, etc.
- Create: `frontend/components/ui/*`（shadcn init 生成）

- [ ] **Step 7.1：用 `pnpm create next-app` 生成 Next.js 14 项目**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x
pnpm create next-app@14 frontend \
  --typescript \
  --tailwind \
  --app \
  --eslint \
  --no-src-dir \
  --import-alias "@/*" \
  --use-pnpm \
  --skip-install
```

Expected: 生成 `frontend/` 目录，包含 `app/`、`tailwind.config.ts`、`next.config.js` 等。

> `--skip-install` 先跳过依赖安装，Step 7.3 统一 `pnpm install`。

- [ ] **Step 7.2：固定 Next 版本为 14**

编辑 `/frontend/package.json`，确保 `dependencies` 中：

```json
{
  "dependencies": {
    "next": "14.2.18",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  }
}
```

（若 `pnpm create` 生成的是 15.x，手动改为上述 14.x 版本。）

- [ ] **Step 7.3：安装依赖**

Run:

```bash
cd frontend
pnpm install
```

Expected: `pnpm-lock.yaml` 生成，无 peer-dependency 错误。

- [ ] **Step 7.4：初始化 shadcn/ui**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/frontend
pnpm dlx shadcn@latest init --yes \
  --style default \
  --base-color zinc \
  --css-variables
```

Expected: 生成 `components.json`、`lib/utils.ts`、`app/globals.css` 中追加 CSS 变量。

- [ ] **Step 7.5：安装常用 shadcn 组件**

Run:

```bash
pnpm dlx shadcn@latest add button card badge --yes
```

Expected: `components/ui/button.tsx`、`card.tsx`、`badge.tsx` 生成。

- [ ] **Step 7.6：冒烟：启动 dev server**

Run:

```bash
pnpm dev &
sleep 10
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000
kill %1
```

Expected: `200`。

- [ ] **Step 7.7：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add frontend
git commit -m "feat(frontend): scaffold Next.js 14 with Tailwind and shadcn/ui"
```

---

## Task 8：前端接入后端 `/health` + 落地页

**Files:**
- Create: `frontend/lib/api.ts`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/.env.local`（可选，dev 时指向 localhost）

- [ ] **Step 8.1：写 `lib/api.ts`**

创建 `/frontend/lib/api.ts`：

```ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export interface HealthResponse {
  status: string
  db: string
}

export async function fetchHealth (): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' })
  if (!res.ok) {
    throw new Error(`health check failed: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 8.2：替换 `app/page.tsx` 为落地页**

把 `/frontend/app/page.tsx` 替换为：

```tsx
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fetchHealth } from '@/lib/api'

export const dynamic = 'force-dynamic'

export default async function HomePage () {
  let health: { status: string, db: string } | null = null
  let error: string | null = null
  try {
    health = await fetchHealth()
  } catch (err) {
    error = err instanceof Error ? err.message : 'unknown error'
  }

  return (
    <main className='min-h-screen bg-background text-foreground flex items-center justify-center p-8'>
      <Card className='w-full max-w-xl'>
        <CardHeader>
          <CardTitle className='flex items-center gap-3 text-2xl'>
            Sporttery 10x
            <Badge variant='secondary'>v0.1.0</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className='space-y-4'>
          <p className='text-muted-foreground'>竞彩交易决策系统 · 项目骨架已就绪。</p>
          <div className='rounded-lg border p-4'>
            <div className='text-sm font-medium mb-2'>Backend Health</div>
            {error !== null && (
              <Badge variant='destructive'>unreachable: {error}</Badge>
            )}
            {health !== null && (
              <div className='flex gap-2'>
                <Badge>status: {health.status}</Badge>
                <Badge variant={health.db === 'ok' ? 'default' : 'destructive'}>
                  db: {health.db}
                </Badge>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
```

- [ ] **Step 8.3：验证**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/frontend
pnpm dev &
sleep 10
curl -s http://localhost:3000 | grep -o 'Sporttery 10x' | head -1
kill %1
```

Expected: 输出 `Sporttery 10x`。

- [ ] **Step 8.4：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add frontend/lib/api.ts frontend/app/page.tsx
git commit -m "feat(frontend): landing page shows backend /health status"
```

---

## Task 9：前端 Lint（Standard.js 风格）+ Prettier

**Files:**
- Modify: `frontend/.eslintrc.json`
- Create: `frontend/.prettierrc`
- Modify: `frontend/package.json`（新增脚本）

- [ ] **Step 9.1：装 Standard + Prettier 依赖**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/frontend
pnpm add -D \
  eslint-config-standard \
  eslint-config-standard-jsx \
  eslint-config-standard-with-typescript \
  eslint-plugin-import \
  eslint-plugin-n \
  eslint-plugin-promise \
  eslint-plugin-react \
  eslint-plugin-react-hooks \
  prettier \
  @typescript-eslint/parser \
  @typescript-eslint/eslint-plugin
```

- [ ] **Step 9.2：覆盖 `.eslintrc.json`**

把 `/frontend/.eslintrc.json` 替换为：

```json
{
  "root": true,
  "parser": "@typescript-eslint/parser",
  "parserOptions": {
    "project": "./tsconfig.json",
    "ecmaVersion": 2022,
    "sourceType": "module",
    "ecmaFeatures": { "jsx": true }
  },
  "extends": [
    "next/core-web-vitals",
    "standard-with-typescript",
    "standard-jsx"
  ],
  "rules": {
    "@typescript-eslint/explicit-function-return-type": "off",
    "@typescript-eslint/strict-boolean-expressions": "off",
    "@typescript-eslint/no-misused-promises": "off",
    "@typescript-eslint/consistent-type-imports": "off",
    "react/react-in-jsx-scope": "off",
    "react/jsx-uses-react": "off"
  },
  "ignorePatterns": ["node_modules", ".next", "out", "dist", "coverage"]
}
```

- [ ] **Step 9.3：写 `.prettierrc`**

创建 `/frontend/.prettierrc`：

```json
{
  "semi": false,
  "singleQuote": true,
  "trailingComma": "none",
  "printWidth": 100,
  "tabWidth": 2,
  "arrowParens": "always"
}
```

- [ ] **Step 9.4：在 `package.json` 加脚本**

编辑 `/frontend/package.json` 的 `scripts`：

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "lint:fix": "next lint --fix",
    "format": "prettier --write .",
    "typecheck": "tsc --noEmit"
  }
}
```

- [ ] **Step 9.5：跑 lint + typecheck**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/frontend
pnpm format
pnpm lint
pnpm typecheck
```

Expected: `lint` 和 `typecheck` 均无错误（warning 允许）。有错就按提示修复到全绿。

- [ ] **Step 9.6：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add frontend/.eslintrc.json frontend/.prettierrc frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(frontend): add Standard.js ESLint config and Prettier"
```

---

## Task 10：前端单元测试（Vitest）

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tests/smoke.test.tsx`
- Modify: `frontend/package.json`

- [ ] **Step 10.1：装 Vitest 依赖**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x/frontend
pnpm add -D vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom @vitejs/plugin-react
```

- [ ] **Step 10.2：写 `vitest.config.ts`**

创建 `/frontend/vitest.config.ts`：

```ts
import path from 'node:path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts']
  }
})
```

- [ ] **Step 10.3：写 `tests/setup.ts`**

创建 `/frontend/tests/setup.ts`：

```ts
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 10.4：写失败测试 `tests/smoke.test.tsx`**

创建 `/frontend/tests/smoke.test.tsx`：

```tsx
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from '@/components/ui/badge'

describe('Badge component', () => {
  it('renders children text', () => {
    render(<Badge>status: ok</Badge>)
    expect(screen.getByText('status: ok')).toBeInTheDocument()
  })

  it('applies variant class for destructive', () => {
    render(<Badge variant='destructive'>down</Badge>)
    const el = screen.getByText('down')
    expect(el.className).toMatch(/destructive/)
  })
})
```

- [ ] **Step 10.5：在 `package.json` 增加 test 脚本**

编辑 `/frontend/package.json` 的 `scripts`，在已有基础上追加：

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 10.6：运行测试**

Run:

```bash
pnpm test
```

Expected: `2 passed`。

- [ ] **Step 10.7：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add frontend/vitest.config.ts frontend/tests frontend/package.json frontend/pnpm-lock.yaml
git commit -m "test(frontend): add Vitest with a smoke test on Badge"
```

---

## Task 11：前端 Dockerfile 与 Compose 集成

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 11.1：写 `frontend/Dockerfile`（多阶段）**

创建 `/frontend/Dockerfile`：

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:20-alpine AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    TZ=Asia/Shanghai
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD wget -qO- http://localhost:3000/ >/dev/null 2>&1 || exit 1
CMD ["pnpm", "start"]
```

- [ ] **Step 11.2：在 `docker-compose.yml` 增加 frontend 服务**

编辑 `/docker-compose.yml`，在 `backend` 之下、`volumes:` 之上追加：

```yaml
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: sporttery_frontend
    restart: unless-stopped
    depends_on:
      - backend
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://backend:8000
      TZ: Asia/Shanghai
    ports:
      - '${FRONTEND_PORT:-3000}:3000'
```

> ⚠️ 注意：`NEXT_PUBLIC_*` 在 build 阶段被编译进 bundle，docker 内浏览器访问 `http://backend:8000` 不可达。Task 8 的落地页是 Server Component，会在服务端调用（容器内可达）。此配置对当前需求够用；后续如加 Client Component 需要改为 `http://localhost:8000`（浏览器可达）或通过 Next.js `rewrites` 代理，留给 P3 处理。

- [ ] **Step 11.3：构建并启动完整栈**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x
docker compose up -d --build
sleep 30
docker compose ps
```

Expected: 三个服务全部 `Up (healthy)`。

- [ ] **Step 11.4：冒烟**

Run:

```bash
curl -s http://localhost:8000/health
curl -s -o /dev/null -w "front=%{http_code}\n" http://localhost:3000
```

Expected: 后端返回 `{"status":"ok","db":"ok"}`；前端 `front=200`。

- [ ] **Step 11.5：提交**

```bash
git add frontend/Dockerfile docker-compose.yml
git commit -m "feat(infra): containerize frontend and wire into docker-compose"
```

---

## Task 12：根 Makefile 增强（install/dev/test/lint）

**Files:**
- Modify: `Makefile`

- [ ] **Step 12.1：替换 `Makefile`**

把 `/Makefile` 整体替换为：

```makefile
.PHONY: help env up down logs ps clean install install-backend install-frontend \
        test test-backend test-frontend lint lint-backend lint-frontend \
        format dev build

help:
	@echo "Targets:"
	@echo "  install          Install backend (.venv) and frontend deps"
	@echo "  dev              docker compose up -d --build"
	@echo "  build            docker compose build"
	@echo "  up / down / logs / ps / clean"
	@echo "  test             Run backend + frontend tests"
	@echo "  lint             Run backend + frontend linters"
	@echo "  format           Auto-format backend + frontend"

env:
	@test -f .env || cp .env.example .env

install-backend:
	cd backend && python3.11 -m venv .venv && . .venv/bin/activate && \
		pip install --upgrade pip pip-tools && pip install -r requirements.txt

install-frontend:
	cd frontend && pnpm install

install: install-backend install-frontend

up: env
	docker compose up -d

dev: env
	docker compose up -d --build

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v

test-backend:
	cd backend && . .venv/bin/activate && MYSQL_HOST=localhost pytest -v

test-frontend:
	cd frontend && pnpm test

test: test-backend test-frontend

lint-backend:
	cd backend && . .venv/bin/activate && ruff check . && black --check .

lint-frontend:
	cd frontend && pnpm lint && pnpm typecheck

lint: lint-backend lint-frontend

format:
	cd backend && . .venv/bin/activate && ruff check --fix . && black .
	cd frontend && pnpm format
```

- [ ] **Step 12.2：验证 `make test`**

前置：MySQL 已启动（`make up`）。

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x
make test
```

Expected: 后端 2 passed，前端 2 passed。

- [ ] **Step 12.3：验证 `make lint`**

Run:

```bash
make lint
```

Expected: 无 error（warning 可接受）。

- [ ] **Step 12.4：提交**

```bash
git add Makefile
git commit -m "chore: enrich root Makefile with install/test/lint/format"
```

---

## Task 13：GitHub Actions CI

**Files:**
- Create: `.github/workflows/backend.yml`
- Create: `.github/workflows/frontend.yml`

- [ ] **Step 13.1：写 `backend.yml`**

创建 `/.github/workflows/backend.yml`：

```yaml
name: backend

on:
  push:
    branches: [main]
    paths:
      - 'backend/**'
      - '.github/workflows/backend.yml'
  pull_request:
    paths:
      - 'backend/**'
      - '.github/workflows/backend.yml'

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: rootpass
          MYSQL_DATABASE: sporttery_10x
          MYSQL_USER: sporttery
          MYSQL_PASSWORD: sporttery_pass
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping -h localhost -uroot -prootpass"
          --health-interval=5s --health-timeout=5s --health-retries=20
    env:
      MYSQL_HOST: 127.0.0.1
      MYSQL_PORT: 3306
      MYSQL_USER: sporttery
      MYSQL_PASSWORD: sporttery_pass
      MYSQL_DATABASE: sporttery_10x
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - run: pip install --upgrade pip
      - run: pip install -r requirements.txt
      - name: Wait for MySQL
        run: |
          for i in {1..30}; do
            if mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent; then break; fi
            sleep 2
          done
      - run: ruff check .
      - run: black --check .
      - run: pytest -v
```

- [ ] **Step 13.2：写 `frontend.yml`**

创建 `/.github/workflows/frontend.yml`：

```yaml
name: frontend

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend.yml'
  pull_request:
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend.yml'

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9.12.0
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test
      - run: pnpm build
        env:
          NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
```

- [ ] **Step 13.3：本地语法校验（可选）**

若本地装了 `act`：

```bash
act -l
```

Expected: 列出 `backend` 和 `frontend` 两个 workflow。没有 `act` 就跳过，提交后由 GitHub 代跑。

- [ ] **Step 13.4：提交**

```bash
git add .github/workflows/backend.yml .github/workflows/frontend.yml
git commit -m "ci: add backend and frontend GitHub Actions workflows"
```

---

## Task 14：合并回 main

**Files:** 无代码修改

- [ ] **Step 14.1：本地最终验收**

Run:

```bash
cd /Users/wushunxin/wusx/sporttery_10x
make clean
make dev
sleep 40
make ps
curl -s http://localhost:8000/health
curl -s -o /dev/null -w "front=%{http_code}\n" http://localhost:3000
make test
make lint
make down
```

Expected: 所有命令无 error；`/health` 返回 `db=ok`；`front=200`；`make test` 和 `make lint` 全绿。

- [ ] **Step 14.2：合并到 main**

```bash
git checkout main
git merge --no-ff feat/p1-scaffolding -m "merge: P1 project scaffolding"
git log --oneline --graph -20
```

Expected: `main` 分支包含本 P1 的所有 commit，图上有合并节点。

- [ ] **Step 14.3（可选）：删除 feature 分支**

```bash
git branch -d feat/p1-scaffolding
```

---

## 完成标准（Definition of Done）

- ✅ `docker compose up -d` 启动 mysql/backend/frontend 三容器全部 healthy
- ✅ `curl http://localhost:8000/health` → `{"status":"ok","db":"ok"}`
- ✅ `curl http://localhost:3000` 返回 HTTP 200，页面渲染后端健康状态
- ✅ `make test` 后端 2 passed，前端 2 passed
- ✅ `make lint` 无 error
- ✅ `main` 分支包含本计划所有提交，GitHub Actions 两个 workflow 文件已存在（仓库有 remote 时会自动跑）
- ✅ `docs/superpowers/brainstorm/2026-04-21-decisions.md` 中的所有决策已落地到代码/配置

---

## 后续衔接

P1 完成后，P2（数据模型与迁移）将基于本计划：

- 在 `backend/app/models/` 下新建所有 ORM 模型
- 用 `alembic init` 初始化迁移目录
- 首次迁移创建 spec 第四节列出的所有 9 张表
- 种子脚本导入联赛字典和 admin 用户
- 扩展 `/health` 检查迁移版本（可选）
