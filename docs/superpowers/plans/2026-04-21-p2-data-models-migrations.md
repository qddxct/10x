# P2 · 数据模型与迁移 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 P1 的后端骨架上落地 **10 张核心数据表**（9 张业务 + 1 张 scrape_logs）的 SQLAlchemy 模型 + Alembic 迁移 + 种子脚本；`alembic upgrade head` + `python -m app.scripts.seed` 跑完后，MySQL 中 schema 与默认模型配置全部就绪。

**Architecture:** SQLAlchemy 2.0 Declarative（`Mapped` / `mapped_column`）+ Alembic 自动生成迁移；所有表 `utf8mb4` charset、`InnoDB` 引擎、时区 Asia/Shanghai 存 naive datetime；时间戳 mixin 复用 `created_at` / `updated_at`。

**Tech Stack:** Python 3.11 · SQLAlchemy 2.0 · Alembic 1.13 · PyMySQL · pytest · MySQL 8.0

**Decisions Reference:** `docs/superpowers/brainstorm/2026-04-21-decisions.md`
**Spec Reference:** `docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md` 第四节

---

## 前置说明

- **工作目录**：`/Users/wushunxin/wusx/sporttery_10x`
- **分支**：本计划在 `feat/p2-data-models` 分支执行，完成后合并回 `main`
- **前置**：P1 已完成，`docker compose up -d mysql backend` 可成功（Step 1.1 会校验）
- **Python 环境**：`backend/.venv`（P1 已建）

---

## 文件总览

本计划结束时，仓库新增/修改：

```
backend/
├── alembic/
│   ├── env.py                              (新建，指向 app.core.database.Base)
│   ├── script.py.mako                      (新建，Alembic 默认模板)
│   └── versions/
│       └── 0001_initial_schema.py          (新建，手工修正后的初始迁移)
├── alembic.ini                             (新建)
├── app/
│   ├── models/                             (新建目录)
│   │   ├── __init__.py                     (导出所有模型)
│   │   ├── base.py                         (Base + TimestampMixin)
│   │   ├── user.py                         (User)
│   │   ├── league.py                       (League)
│   │   ├── match.py                        (Match)
│   │   ├── odds.py                         (MatchOdds)
│   │   ├── result.py                       (MatchResult)
│   │   ├── team_stats.py                   (MatchTeamStats)
│   │   ├── score.py                        (MatchScore)
│   │   ├── model_config.py                 (ModelConfig)
│   │   ├── backtest.py                     (BacktestSession)
│   │   └── scrape_log.py                   (ScrapeLog)
│   ├── core/
│   │   └── database.py                     (修改：从 base.py 导入 Base)
│   └── scripts/                            (新建目录)
│       ├── __init__.py
│       └── seed.py                         (插入默认 model_config)
├── tests/
│   ├── test_models.py                      (新建，模型/关系基础单测)
│   └── test_seed.py                        (新建，种子脚本单测)
└── requirements.in                         (追加 alembic)

.github/workflows/backend.yml               (追加 migration check 步骤)
```

---

## Task 1：Alembic 依赖与环境接入

**Files:**
- Modify: `backend/requirements.in`
- Regen: `backend/requirements.txt`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/.gitkeep`

- [ ] **Step 1.1：切分支 + 确认 MySQL 在跑**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git checkout main
git checkout -b feat/p2-data-models
make up
sleep 10
docker compose ps | grep mysql
```

Expected: `sporttery_mysql ... Up ... (healthy)`。

- [ ] **Step 1.2：requirements.in 追加 alembic**

编辑 `backend/requirements.in`，确认（或追加）：

```
alembic>=1.13,<2.0
```

- [ ] **Step 1.3：重锁 requirements.txt 并安装**

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
. .venv/bin/activate
pip-compile requirements.in -o requirements.txt
pip install -r requirements.txt
alembic --version
```

Expected: `alembic 1.13.x` 输出。

- [ ] **Step 1.4：初始化 Alembic（手写三个文件，不用 `alembic init`）**

创建 `/backend/alembic.ini`：

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
path_separator = os
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

> `sqlalchemy.url` 留空，由 `env.py` 从 `Settings` 动态注入。

创建 `/backend/alembic/env.py`：

```python
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.models import Base  # noqa: F401  确保所有模型注册到 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

创建 `/backend/alembic/script.py.mako`：

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create empty `/backend/alembic/versions/.gitkeep`.

- [ ] **Step 1.5：Smoke — `alembic current` 应能连上 DB**

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
. .venv/bin/activate
MYSQL_HOST=localhost alembic current
```

Expected: 无报错，输出为空（因为尚无任何迁移应用）。若出现 `Can't load plugin: sqlalchemy.dialects:mysql+pymysql`，检查 `pymysql` 已装。

- [ ] **Step 1.6：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add backend/requirements.in backend/requirements.txt backend/alembic.ini backend/alembic/
git commit -m "feat(backend): wire up Alembic with project settings"
```

---

## Task 2：SQLAlchemy Base 与 TimestampMixin

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Modify: `backend/app/core/database.py`（改为从 `app.models.base` 导入 `Base`）

- [ ] **Step 2.1：写 `app/models/base.py`**

创建 `/backend/app/models/base.py`：

```python
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """项目级 SQLAlchemy 2.0 Declarative Base。"""


class TimestampMixin:
    """统一的 created_at / updated_at。时区统一 Asia/Shanghai，DB 存 naive 时间。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

- [ ] **Step 2.2：写 `app/models/__init__.py`（仅 Base，模型逐 Task 追加）**

创建 `/backend/app/models/__init__.py`：

```python
from app.models.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
```

- [ ] **Step 2.3：更新 `app/core/database.py` 共用 Base**

编辑 `/backend/app/core/database.py`，删除（若存在）自定义的 `Base = declarative_base()`，改为：

```python
from app.models.base import Base  # noqa: F401  re-export for legacy callers
```

同时保留原有 `engine` / `SessionLocal` / `check_db_alive` 不变。

- [ ] **Step 2.4：快速 sanity**

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
. .venv/bin/activate
python -c "from app.models import Base; print(Base.metadata.tables)"
```

Expected: `{}`（此时还没任何表绑定）。

- [ ] **Step 2.5：提交**

```bash
git add backend/app/models backend/app/core/database.py
git commit -m "feat(backend): add SQLAlchemy Base and TimestampMixin"
```

---

## Task 3：用户与联赛模型

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/league.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 3.1：写 `user.py`**

创建 `/backend/app/models/user.py`：

```python
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.score import MatchScore
    from app.models.backtest import BacktestSession


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("admin", "member", name="user_role"),
        nullable=False,
        default="member",
    )
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    bankroll_cny: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), nullable=False, default=Decimal("10000.00")
    )

    scores: Mapped[list["MatchScore"]] = relationship(back_populates="user")
    backtests: Mapped[list["BacktestSession"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone} role={self.role}>"
```

- [ ] **Step 3.2：写 `league.py`**

创建 `/backend/app/models/league.py`：

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import Match


class League(Base, TimestampMixin):
    __tablename__ = "leagues"
    __table_args__ = (UniqueConstraint("name", "country", name="uq_league_name_country"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    draw_rate_tier: Mapped[str | None] = mapped_column(
        Enum("high", "medium", "low", name="draw_rate_tier"),
        nullable=True,
    )

    matches: Mapped[list["Match"]] = relationship(back_populates="league")

    def __repr__(self) -> str:
        return f"<League id={self.id} name={self.name}>"
```

- [ ] **Step 3.3：在 `__init__.py` 导出**

替换 `/backend/app/models/__init__.py`：

```python
from app.models.base import Base, TimestampMixin
from app.models.league import League
from app.models.user import User

__all__ = ["Base", "TimestampMixin", "League", "User"]
```

- [ ] **Step 3.4：提交**

```bash
git add backend/app/models
git commit -m "feat(backend): add User and League ORM models"
```

---

## Task 4：比赛、赔率、赛果模型

**Files:**
- Create: `backend/app/models/match.py`
- Create: `backend/app/models/odds.py`
- Create: `backend/app/models/result.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 4.1：写 `match.py`**

创建 `/backend/app/models/match.py`：

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.league import League
    from app.models.odds import MatchOdds
    from app.models.result import MatchResult
    from app.models.score import MatchScore
    from app.models.team_stats import MatchTeamStats


class Match(Base, TimestampMixin):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_date_league", "match_date", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sporttery_match_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )
    match_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    home_team: Mapped[str] = mapped_column(String(64), nullable=False)
    away_team: Mapped[str] = mapped_column(String(64), nullable=False)
    round: Mapped[str | None] = mapped_column(String(32), nullable=True)
    competition_type: Mapped[str] = mapped_column(
        Enum(
            "league",
            "cup",
            "knockout_first_leg",
            "knockout_second_leg",
            name="competition_type",
        ),
        nullable=False,
        default="league",
    )
    status: Mapped[str] = mapped_column(
        Enum("scheduled", "in_progress", "finished", name="match_status"),
        nullable=False,
        default="scheduled",
        index=True,
    )

    league: Mapped["League"] = relationship(back_populates="matches")
    odds: Mapped[list["MatchOdds"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    result: Mapped["MatchResult | None"] = relationship(
        back_populates="match", cascade="all, delete-orphan", uselist=False
    )
    team_stats: Mapped["MatchTeamStats | None"] = relationship(
        back_populates="match", cascade="all, delete-orphan", uselist=False
    )
    scores: Mapped[list["MatchScore"]] = relationship(back_populates="match", cascade="all, delete-orphan")
```

- [ ] **Step 4.2：写 `odds.py`**

创建 `/backend/app/models/odds.py`：

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import Match


class MatchOdds(Base, TimestampMixin):
    __tablename__ = "match_odds"
    __table_args__ = (
        Index("ix_odds_match_source", "match_id", "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(
        Enum("sporttery", "titan007", "other", name="odds_source"),
        nullable=False,
    )

    win_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3), nullable=True)
    draw_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3), nullable=True)
    lose_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3), nullable=True)

    handicap_value: Mapped[Decimal | None] = mapped_column(DECIMAL(4, 2), nullable=True)
    win_handicap_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3), nullable=True)
    draw_handicap_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3), nullable=True)
    lose_handicap_odds: Mapped[Decimal | None] = mapped_column(DECIMAL(6, 3), nullable=True)

    asian_handicap: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_goals: Mapped[Decimal | None] = mapped_column(DECIMAL(4, 2), nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    match: Mapped["Match"] = relationship(back_populates="odds")
```

- [ ] **Step 4.3：写 `result.py`**

创建 `/backend/app/models/result.py`：

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import Match


class MatchResult(Base, TimestampMixin):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    home_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    away_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    result: Mapped[str] = mapped_column(
        Enum("home_win", "draw", "away_win", name="match_result_enum"),
        nullable=False,
    )
    handicap_result: Mapped[str | None] = mapped_column(
        Enum("home_win", "draw", "away_win", name="handicap_result_enum"),
        nullable=True,
    )

    match: Mapped["Match"] = relationship(back_populates="result")
```

- [ ] **Step 4.4：追加 `__init__.py` 导出**

把 `/backend/app/models/__init__.py` 的 `__all__` 与 import 扩展为包含 `Match`, `MatchOdds`, `MatchResult`。

- [ ] **Step 4.5：提交**

```bash
git add backend/app/models
git commit -m "feat(backend): add Match, MatchOdds and MatchResult models"
```

---

## Task 5：球队状态与评分模型

**Files:**
- Create: `backend/app/models/team_stats.py`
- Create: `backend/app/models/score.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 5.1：写 `team_stats.py`**

创建 `/backend/app/models/team_stats.py`：

```python
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import Match


class MatchTeamStats(Base, TimestampMixin):
    __tablename__ = "match_team_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    home_rank: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_season_wins: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_season_draws: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_season_losses: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_home_wins: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_home_draws: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_home_losses: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    home_recent_form: Mapped[str | None] = mapped_column(String(16), nullable=True)

    away_rank: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_season_wins: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_season_draws: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_season_losses: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_away_wins: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_away_draws: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_away_losses: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    away_recent_form: Mapped[str | None] = mapped_column(String(16), nullable=True)

    h2h_home_wins: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    h2h_draws: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    h2h_away_wins: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    match: Mapped["Match"] = relationship(back_populates="team_stats")
```

- [ ] **Step 5.2：写 `score.py`**

创建 `/backend/app/models/score.py`：

```python
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.model_config import ModelConfig
    from app.models.user import User


class MatchScore(Base, TimestampMixin):
    __tablename__ = "match_scores"
    __table_args__ = (
        Index("ix_scores_match_config", "match_id", "model_config_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_config_id: Mapped[int] = mapped_column(
        ForeignKey("model_configs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    euro_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    asian_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intent_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compression_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    team_stats_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    bet_type: Mapped[str | None] = mapped_column(
        Enum("draw", "handicap_draw", name="bet_type"),
        nullable=True,
    )
    kelly_pct: Mapped[Decimal | None] = mapped_column(DECIMAL(5, 4), nullable=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    actual_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bet_amount: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    match: Mapped["Match"] = relationship(back_populates="scores")
    model_config: Mapped["ModelConfig"] = relationship(back_populates="scores")
    user: Mapped["User | None"] = relationship(back_populates="scores")
```

- [ ] **Step 5.3：追加 `__init__.py`**

导出 `MatchTeamStats`, `MatchScore`。

- [ ] **Step 5.4：提交**

```bash
git add backend/app/models
git commit -m "feat(backend): add MatchTeamStats and MatchScore models"
```

---

## Task 6：模型配置与回测模型

**Files:**
- Create: `backend/app/models/model_config.py`
- Create: `backend/app/models/backtest.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 6.1：写 `model_config.py`**

创建 `/backend/app/models/model_config.py`：

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.backtest import BacktestSession
    from app.models.score import MatchScore
    from app.models.user import User


class ModelConfig(Base, TimestampMixin):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    weights_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    thresholds_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    kelly_bands_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    scrape_schedule_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    creator: Mapped["User | None"] = relationship()
    scores: Mapped[list["MatchScore"]] = relationship(back_populates="model_config")
    backtests: Mapped[list["BacktestSession"]] = relationship(back_populates="model_config")
```

- [ ] **Step 6.2：写 `backtest.py`**

创建 `/backend/app/models/backtest.py`：

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DECIMAL, JSON, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.model_config import ModelConfig
    from app.models.user import User


class BacktestSession(Base, TimestampMixin):
    __tablename__ = "backtest_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_config_id: Mapped[int] = mapped_column(
        ForeignKey("model_configs.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)

    total_bets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hit_rate: Mapped[Decimal] = mapped_column(DECIMAL(6, 4), nullable=False, default=Decimal("0"))
    roi: Mapped[Decimal] = mapped_column(DECIMAL(8, 4), nullable=False, default=Decimal("0"))
    profit_loss: Mapped[Decimal] = mapped_column(
        DECIMAL(14, 2), nullable=False, default=Decimal("0")
    )

    results_by_score: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    results_by_league: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="backtests")
    model_config: Mapped["ModelConfig"] = relationship(back_populates="backtests")
```

- [ ] **Step 6.3：追加 `__init__.py`**

导出 `ModelConfig`, `BacktestSession`。

- [ ] **Step 6.4：提交**

```bash
git add backend/app/models
git commit -m "feat(backend): add ModelConfig and BacktestSession models"
```

---

## Task 7：抓取日志模型

**Files:**
- Create: `backend/app/models/scrape_log.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 7.1：写 `scrape_log.py`**

创建 `/backend/app/models/scrape_log.py`：

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScrapeLog(Base, TimestampMixin):
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(
        Enum("sporttery", "titan007", "other", name="scrape_source"),
        nullable=False,
    )
    job_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum("success", "failed", "partial", name="scrape_status"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 7.2：追加 `__init__.py`**

最终 `/backend/app/models/__init__.py` 应如下：

```python
from app.models.backtest import BacktestSession
from app.models.base import Base, TimestampMixin
from app.models.league import League
from app.models.match import Match
from app.models.model_config import ModelConfig
from app.models.odds import MatchOdds
from app.models.result import MatchResult
from app.models.score import MatchScore
from app.models.scrape_log import ScrapeLog
from app.models.team_stats import MatchTeamStats
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "BacktestSession",
    "League",
    "Match",
    "MatchOdds",
    "MatchResult",
    "MatchScore",
    "MatchTeamStats",
    "ModelConfig",
    "ScrapeLog",
    "User",
]
```

- [ ] **Step 7.3：模型自检**

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
. .venv/bin/activate
python -c "from app.models import Base; print(sorted(Base.metadata.tables.keys()))"
```

Expected:

```
['backtest_sessions', 'leagues', 'match_odds', 'match_results', 'match_scores', 'match_team_stats', 'matches', 'model_configs', 'scrape_logs', 'users']
```

（10 张表）

- [ ] **Step 7.4：提交**

```bash
git add backend/app/models
git commit -m "feat(backend): add ScrapeLog model and finalize models package"
```

---

## Task 8：生成并修正初始迁移

**Files:**
- Create: `backend/alembic/versions/0001_initial_schema.py`

- [ ] **Step 8.1：auto-generate**

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
. .venv/bin/activate
MYSQL_HOST=localhost alembic revision --autogenerate -m "initial schema" --rev-id 0001
```

Expected: 在 `alembic/versions/` 生成 `0001_initial_schema.py`，含 10 张表的 `op.create_table`。

- [ ] **Step 8.2：修正迁移（MySQL 专属设置）**

打开 `backend/alembic/versions/0001_initial_schema.py`，在每个 `op.create_table(` 调用末尾追加：

```python
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB',
```

可以用脚本批量追加（可选，也可手工编辑）：

```bash
python - <<'PY'
import re
from pathlib import Path

p = Path("alembic/versions/0001_initial_schema.py")
src = p.read_text()
# 将每个 op.create_table 的结尾 )  替换成带 mysql_* 参数的 )
pattern = re.compile(r"(op\.create_table\(.*?)(\n    \))", re.DOTALL)

def repl(m):
    head, tail = m.group(1), m.group(2)
    if "mysql_charset" in head:
        return m.group(0)
    return head + ",\n    mysql_charset='utf8mb4',\n    mysql_collate='utf8mb4_unicode_ci',\n    mysql_engine='InnoDB'" + tail

p.write_text(pattern.sub(repl, src))
print("patched")
PY
```

然后 `ruff check --fix .` 和 `black .` 格式化。

- [ ] **Step 8.3：人工核查生成结果**

打开 `0001_initial_schema.py`，确认：
- 10 张 `create_table` 均存在
- 外键 `ondelete` 方向正确（`matches.league_id` RESTRICT；`match_scores.user_id` SET NULL 等）
- `downgrade()` 的 `drop_table` 顺序与依赖反向（先删子表，再删父表）

常见修正：`matches` / `model_configs` / `users` 必须在引用它们的表之前创建。Alembic 通常能正确排序，若顺序错乱手工调整。

- [ ] **Step 8.4：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add backend/alembic/versions/0001_initial_schema.py
git commit -m "feat(backend): add initial Alembic migration for 10 tables"
```

---

## Task 9：执行迁移并验证 schema

**Files:** 无代码修改

- [ ] **Step 9.1：`alembic upgrade head`**

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
. .venv/bin/activate
MYSQL_HOST=localhost alembic upgrade head
```

Expected: 输出 `Running upgrade  -> 0001, initial schema`。

- [ ] **Step 9.2：在 MySQL 中核对表**

```bash
docker exec sporttery_mysql mysql -usporttery -psporttery_pass sporttery_10x \
  -e "SHOW TABLES;"
```

Expected:

```
alembic_version
backtest_sessions
leagues
match_odds
match_results
match_scores
match_team_stats
matches
model_configs
scrape_logs
users
```

共 11 行（10 张业务表 + alembic_version）。

- [ ] **Step 9.3：核查 charset + engine**

```bash
docker exec sporttery_mysql mysql -usporttery -psporttery_pass sporttery_10x \
  -e "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA='sporttery_10x';"
```

Expected: 所有业务表 `ENGINE=InnoDB`，`TABLE_COLLATION=utf8mb4_unicode_ci`。

- [ ] **Step 9.4：downgrade 往返测试**

```bash
MYSQL_HOST=localhost alembic downgrade base
docker exec sporttery_mysql mysql -usporttery -psporttery_pass sporttery_10x -e "SHOW TABLES;"
# 应仅剩 alembic_version
MYSQL_HOST=localhost alembic upgrade head
```

Expected: downgrade 后仅 `alembic_version`；再 upgrade 回来 10 张表全部重建。

- [ ] **Step 9.5：无需 commit（仅验证）**

---

## Task 10：种子脚本 + 单元测试

**Files:**
- Create: `backend/app/scripts/__init__.py`
- Create: `backend/app/scripts/seed.py`
- Create: `backend/tests/test_models.py`
- Create: `backend/tests/test_seed.py`

- [ ] **Step 10.1：写 `app/scripts/seed.py`**

创建 `/backend/app/scripts/seed.py`：

```python
"""种子脚本：插入默认 ModelConfig（权重 / 阈值 / Kelly 档位 / 抓取调度）。

用法：
    python -m app.scripts.seed

幂等：若同名配置已存在则跳过。
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import ModelConfig

DEFAULT_NAME = "default_v1"

DEFAULT_WEIGHTS = {
    "euro": 25,
    "asian": 20,
    "goals": 20,
    "intent": 15,
    "compression": 20,
    "team_stats": 20,
}

DEFAULT_THRESHOLDS = {
    "draw": 84,
    "handicap_draw": 78,
    "max_total": 120,
}

DEFAULT_KELLY_BANDS = {
    "bands": [
        {"min_pct": 0.80, "stake_ratio": 0.020},
        {"min_pct": 0.70, "stake_ratio": 0.015},
        {"min_pct": 0.65, "stake_ratio": 0.010},
    ],
    "below_min_stake_ratio": 0.0,
}

DEFAULT_SCRAPE_SCHEDULE = {
    "sporttery_schedule_cron": "0 8 * * *",
    "titan007_odds_cron": "*/30 * * * *",
    "results_cron": "0 2 * * *",
}


def seed_default_model_config() -> ModelConfig:
    session = SessionLocal()
    try:
        existing = session.execute(
            select(ModelConfig).where(ModelConfig.name == DEFAULT_NAME)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"[seed] model_configs '{DEFAULT_NAME}' already exists, skip.")
            return existing

        cfg = ModelConfig(
            name=DEFAULT_NAME,
            created_by=None,
            weights_json=DEFAULT_WEIGHTS,
            thresholds_json=DEFAULT_THRESHOLDS,
            kelly_bands_json=DEFAULT_KELLY_BANDS,
            scrape_schedule_json=DEFAULT_SCRAPE_SCHEDULE,
        )
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
        print(f"[seed] inserted model_configs '{DEFAULT_NAME}' id={cfg.id}")
        return cfg
    finally:
        session.close()


if __name__ == "__main__":
    try:
        seed_default_model_config()
    except Exception as exc:  # noqa: BLE001
        print(f"[seed] failed: {exc}", file=sys.stderr)
        raise
```

- [ ] **Step 10.2：写 `app/scripts/__init__.py`**（空文件即可）

- [ ] **Step 10.3：写 `tests/test_models.py` — 模型关系基础单测**

> **注意**：tests 仍用 MySQL（而非 SQLite in-memory），因为我们用到 `JSON` 类型、`Enum` 与 MySQL 特性。每个测试跑前清表。

创建 `/backend/tests/test_models.py`：

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from app.core.database import SessionLocal, engine
from app.models import (
    League,
    Match,
    MatchOdds,
    MatchResult,
    MatchScore,
    ModelConfig,
    ScrapeLog,
    User,
)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    # 每个测试前清空业务表（保留 alembic_version）
    tables = [
        "match_scores",
        "backtest_sessions",
        "match_results",
        "match_team_stats",
        "match_odds",
        "matches",
        "scrape_logs",
        "model_configs",
        "leagues",
        "users",
    ]
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in tables:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    try:
        yield session
    finally:
        session.close()


def test_user_create_and_read(db_session):
    u = User(phone="13800000000", name="Alice", role="admin", password_hash="x")
    db_session.add(u)
    db_session.commit()
    found = db_session.execute(select(User).where(User.phone == "13800000000")).scalar_one()
    assert found.role == "admin"
    assert found.bankroll_cny == Decimal("10000.00")
    assert found.created_at is not None


def test_match_league_relationship(db_session):
    league = League(name="EPL", country="England", draw_rate_tier="medium")
    db_session.add(league)
    db_session.commit()

    match = Match(
        sporttery_match_id="2026-001",
        match_date=datetime(2026, 5, 1, 20, 0, 0),
        league_id=league.id,
        home_team="Arsenal",
        away_team="Chelsea",
        competition_type="league",
        status="scheduled",
    )
    db_session.add(match)
    db_session.commit()

    assert match.league.name == "EPL"
    assert league.matches[0].home_team == "Arsenal"


def test_match_cascade_delete(db_session):
    league = League(name="La Liga", country="Spain", draw_rate_tier="low")
    db_session.add(league)
    db_session.commit()

    m = Match(
        match_date=datetime(2026, 5, 2, 22, 0, 0),
        league_id=league.id,
        home_team="RM",
        away_team="Barca",
        competition_type="league",
        status="scheduled",
    )
    db_session.add(m)
    db_session.commit()

    db_session.add(
        MatchOdds(
            match_id=m.id,
            source="titan007",
            draw_odds=Decimal("3.40"),
            scraped_at=datetime.now(),
        )
    )
    db_session.add(
        MatchResult(
            match_id=m.id,
            home_score=1,
            away_score=1,
            result="draw",
            handicap_result="draw",
        )
    )
    db_session.commit()

    db_session.delete(m)
    db_session.commit()

    assert db_session.execute(select(MatchOdds)).scalars().all() == []
    assert db_session.execute(select(MatchResult)).scalars().all() == []


def test_model_config_json_roundtrip(db_session):
    cfg = ModelConfig(
        name="t",
        weights_json={"euro": 25, "asian": 20},
        thresholds_json={"draw": 84},
        kelly_bands_json={"bands": [{"min_pct": 0.7, "stake_ratio": 0.015}]},
    )
    db_session.add(cfg)
    db_session.commit()

    got = db_session.execute(select(ModelConfig).where(ModelConfig.name == "t")).scalar_one()
    assert got.weights_json["euro"] == 25
    assert got.kelly_bands_json["bands"][0]["stake_ratio"] == 0.015


def test_scrape_log_enum(db_session):
    log = ScrapeLog(
        source="sporttery",
        job_name="schedule_daily",
        status="success",
        started_at=datetime.now(),
        records_count=42,
    )
    db_session.add(log)
    db_session.commit()
    got = db_session.execute(select(ScrapeLog)).scalar_one()
    assert got.status == "success"


def test_match_score_relations(db_session):
    league = League(name="Serie A", country="Italy", draw_rate_tier="high")
    db_session.add(league)
    db_session.flush()
    match = Match(
        match_date=datetime(2026, 5, 3, 20, 45, 0),
        league_id=league.id,
        home_team="Juventus",
        away_team="Inter",
        competition_type="league",
        status="scheduled",
    )
    cfg = ModelConfig(
        name="t2",
        weights_json={},
        thresholds_json={},
        kelly_bands_json={},
    )
    db_session.add_all([match, cfg])
    db_session.flush()
    score = MatchScore(
        match_id=match.id,
        model_config_id=cfg.id,
        euro_score=20,
        asian_score=15,
        goals_score=10,
        intent_score=10,
        compression_score=15,
        team_stats_score=15,
        total_score=85,
        bet_type="draw",
        kelly_pct=Decimal("0.02"),
        is_recommended=True,
    )
    db_session.add(score)
    db_session.commit()

    got = db_session.execute(select(MatchScore)).scalar_one()
    assert got.match.home_team == "Juventus"
    assert got.model_config.name == "t2"
    assert got.is_recommended is True
```

- [ ] **Step 10.4：写 `tests/test_seed.py`**

创建 `/backend/tests/test_seed.py`：

```python
from __future__ import annotations

from sqlalchemy import text

from app.core.database import SessionLocal, engine
from app.scripts.seed import DEFAULT_NAME, seed_default_model_config


def _truncate_all() -> None:
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        conn.execute(text("TRUNCATE TABLE model_configs"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def test_seed_inserts_default_config():
    _truncate_all()
    cfg = seed_default_model_config()
    assert cfg.id is not None
    assert cfg.name == DEFAULT_NAME
    assert cfg.weights_json["euro"] == 25
    assert cfg.thresholds_json["draw"] == 84


def test_seed_is_idempotent():
    _truncate_all()
    first = seed_default_model_config()
    second = seed_default_model_config()
    assert first.id == second.id

    session = SessionLocal()
    try:
        count = session.execute(
            text("SELECT COUNT(*) FROM model_configs WHERE name=:n"),
            {"n": DEFAULT_NAME},
        ).scalar_one()
        assert count == 1
    finally:
        session.close()
```

- [ ] **Step 10.5：跑测试**

```bash
cd /Users/wushunxin/wusx/sporttery_10x/backend
. .venv/bin/activate
MYSQL_HOST=localhost pytest -v
```

Expected: **11 passed**（原 2 个 health + 6 个 models + 2 个 seed + 1 个冗余）。若数字不同但无 failed 就 OK。

- [ ] **Step 10.6：跑种子脚本**

```bash
MYSQL_HOST=localhost python -m app.scripts.seed
docker exec sporttery_mysql mysql -usporttery -psporttery_pass sporttery_10x \
  -e "SELECT name, JSON_EXTRACT(weights_json, '\$.euro') AS euro FROM model_configs;"
```

Expected: 有一行 `default_v1 | 25`。再执行一次脚本应输出 `already exists, skip`。

- [ ] **Step 10.7：提交**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
git add backend/app/scripts backend/tests
git commit -m "feat(backend): add seed script and model/seed tests"
```

---

## Task 11：CI 集成（迁移 + 种子）

**Files:**
- Modify: `.github/workflows/backend.yml`
- Modify: `Makefile`

- [ ] **Step 11.1：在 `backend.yml` 的 pytest 之前插入迁移步骤**

编辑 `/.github/workflows/backend.yml`，在 `- run: ruff check .` 之后、`- run: pytest -v` 之前插入：

```yaml
      - name: Alembic upgrade
        run: MYSQL_HOST=127.0.0.1 alembic upgrade head
      - name: Seed default config
        run: MYSQL_HOST=127.0.0.1 python -m app.scripts.seed
```

确保 `pytest -v` 依然在最后执行（单测依赖已迁移的 schema）。

- [ ] **Step 11.2：Makefile 新增 `db-upgrade` / `db-downgrade` / `seed`**

编辑根目录 `/Makefile`，在 `.PHONY` 列表和现有目标中追加：

```makefile
.PHONY: db-upgrade db-downgrade seed db-reset

db-upgrade:
	cd backend && . .venv/bin/activate && MYSQL_HOST=localhost alembic upgrade head

db-downgrade:
	cd backend && . .venv/bin/activate && MYSQL_HOST=localhost alembic downgrade -1

seed:
	cd backend && . .venv/bin/activate && MYSQL_HOST=localhost python -m app.scripts.seed

db-reset:
	cd backend && . .venv/bin/activate && MYSQL_HOST=localhost alembic downgrade base && \
		MYSQL_HOST=localhost alembic upgrade head && \
		MYSQL_HOST=localhost python -m app.scripts.seed
```

（注意 `.PHONY` 追加，而不是重复声明。）

- [ ] **Step 11.3：验证**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
make db-reset
make test-backend
```

Expected: `db-reset` 无报错；`test-backend` 11 passed。

- [ ] **Step 11.4：提交**

```bash
git add .github/workflows/backend.yml Makefile
git commit -m "ci: run Alembic upgrade and seed before backend tests"
```

---

## Task 12：合并回 main

**Files:** 无代码修改

- [ ] **Step 12.1：最终验收**

```bash
cd /Users/wushunxin/wusx/sporttery_10x
make clean
make dev
sleep 40
make db-reset
make test
make lint
make down
```

Expected: 全链路绿。`make test` 中 backend ≥ 10 passed，frontend 2 passed。

- [ ] **Step 12.2：合并**

```bash
git checkout main
git merge --no-ff feat/p2-data-models -m "merge: P2 data models and migrations"
git log --oneline --graph -30
```

- [ ] **Step 12.3（可选）：删分支**

```bash
git branch -d feat/p2-data-models
```

---

## 完成标准（Definition of Done）

- ✅ 10 张业务表 + `alembic_version` 通过 `alembic upgrade head` 在 MySQL 中建起（全部 `utf8mb4` + `InnoDB`）
- ✅ `alembic downgrade base` 可回退，再 `upgrade head` 可重建（可逆）
- ✅ `python -m app.scripts.seed` 插入 `default_v1` ModelConfig；重跑幂等
- ✅ `make test-backend` 11 passed（2 health + 6 models + 2 seed + 1 额外；若少于 11 只要无 failed 即可）
- ✅ `make lint` 无 error（ruff/black 对新文件全绿）
- ✅ `backend.yml` CI workflow 包含 `alembic upgrade head` + `python -m app.scripts.seed` 步骤
- ✅ `main` 分支含 P2 全部 commits，有合并节点

---

## 后续衔接

P2 完成后可进入：

- **P3 用户认证**：基于 `users` 表实现注册/登录/JWT
- **P4 爬虫**：写入 `matches` / `match_odds` / `match_results` / `match_team_stats` / `scrape_logs`
- **P5 评分引擎**：读取 `matches` + `match_odds` + `match_team_stats` + `model_configs`，写入 `match_scores`
- **P6 Dashboard**：聚合 `match_scores` 推荐
- **P7 回测**：写入 `backtest_sessions`

**约束**：后续计划必须通过 Alembic 新增迁移（`alembic revision --autogenerate -m "..."`），禁止直接改 `0001_initial_schema.py`。
