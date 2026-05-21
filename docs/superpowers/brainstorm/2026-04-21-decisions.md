# Sporttery 10x 系统 Brainstorming 决策记录

**日期**：2026-04-21
**关联 Spec**：`docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`
**用途**：统一锁定 P1-P7 所有子计划共享的技术决策。后续子计划必须遵循本文件。

---

## 一、技术栈版本

| 项 | 决策 |
| --- | --- |
| Python | **3.11** |
| Python 包管理 | **pip + requirements.txt**（兼容性优先；requirements.in + pip-compile 锁定） |
| Node.js | **20 LTS** |
| 前端包管理 | **pnpm**（>= 9.x） |
| Next.js | **14.x**（App Router，TypeScript） |
| MySQL | **8.0** |
| ORM | SQLAlchemy 2.0 + Alembic |
| 后端框架 | FastAPI（最新稳定） |
| 爬虫 | httpx + BeautifulSoup4（主策略） + 预留 Playwright 接口作为备份 |
| 定时任务 | APScheduler `BlockingScheduler`（独立容器进程，cron 任务于进程内存，无持久 JobStore；重启不丢任务因 job 定义写死在代码） |
| 认证 | **手机号 + 密码**（bcrypt），JWT via `python-jose` |
| 部署 | Docker Compose，**仅本地开发**（单机 VPS 后续再加 Nginx/HTTPS） |
| CI | **GitHub Actions** |
| Lint/Format | Python: Ruff + Black；前端：ESLint（Standard.js 风格规则）+ Prettier |

---

## 二、目录结构

```
sporttery_10x/
├── .github/workflows/           # CI
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI 路由
│   │   ├── core/                # 配置、安全、DB session
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── schemas/             # Pydantic DTO
│   │   ├── scrapers/            # 爬虫
│   │   ├── engine/              # 评分/Kelly/回测
│   │   └── scheduler/           # APScheduler
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.in
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                     # Next.js App Router
│   ├── components/
│   ├── lib/
│   ├── styles/
│   ├── tests/
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── superpowers/
│   │   ├── specs/
│   │   ├── brainstorm/
│   │   └── plans/
│   └── ...
├── docker-compose.yml
├── docker-compose.override.yml  # 本地开发用
├── .env.example
├── .gitignore
├── README.md
└── Makefile
```

> **Monorepo 策略**：`frontend/` + `backend/` 两个独立子项目，不引入 Turborepo/Nx。根目录 Makefile 提供统一入口。

---

## 三、业务规则

| 项 | 决策 |
| --- | --- |
| **满分** | 6 维总分 = **120**（欧赔 25 + 亚盘 20 + 大小球 20 + 战意 15 + 平赔压缩 20 + 球队状态 20） |
| **下注阈值** | **可配置**（存 `model_configs.thresholds_json`）。默认值来自手册：平局 ≥ 70%（=84），让平 ≥ 65%（=78），日常通过回测调优 |
| **Kelly 策略** | 半 Kelly 档位表写入 `model_configs.kelly_bands_json`，默认值同 spec 第五节 |
| **球队状态评分** | 默认公式见下（P5 计划会写完整测试用例） |
| **联赛 draw_rate_tier** | **自动计算**：nightly job 统计每联赛最近 N=200 场平局率，≥30% 高/25-30% 中/<25% 低；无足量历史时置 `NULL`，评分时退化为"中" |
| **时区** | 全栈 **Asia/Shanghai**，DB 存 naive 本地时间，所有日期字段解析一律用本地时间 |
| **账户本金** | 每个用户独立 `bankroll_cny`（存 `users.bankroll_cny`，默认 10000），Kelly 建议金额在推荐/回测时按本金乘比例计算 |
| **抓取频率** | `model_configs.thresholds_json` 之外，`scrape_schedule` 存 admin 可调配置表 |

### 3.1 球队状态评分默认公式（满分 20）

**规则**：三档子项累加，缺数据时按档位 0 处理。

| 子项 | 满分 | 评分规则 |
| --- | --- | --- |
| 排名接近度 | 7 | 排名差 ≤ 3 → 7；4-6 → 5；7-10 → 3；>10 → 0；缺排名 → 0 |
| 主客场战绩差 | 7 | `主队主场胜率 - 客队客场胜率` 的绝对值：≤ 0.10 → 7；0.10-0.25 → 4；> 0.25 → 1；缺数据 → 0 |
| 近 5 场状态差 | 6 | 主/客近 5 场积分（W=3, D=1, L=0），差的绝对值：≤ 3 → 6；4-6 → 3；> 6 → 0；缺数据 → 0 |

*注：胜率 = 胜场 / max(1, 主/客场总场次)。该公式是起点，P5 计划会给 10 个单元测试 fixture 固定行为。*

### 3.2 抓取反爬策略

- **V1 默认**：随机 UA + 1-3s 随机延迟 + 失败指数退避（最多 3 次）
- **接口可插拔**：爬虫层暴露 `FetcherStrategy` 协议，后期可接入 Playwright 无头浏览器或代理池

### 3.3 历史数据补录

- **首选**：爬虫回溯抓取（支持 `--date-from / --date-to` 命令）
- **补充**：支持 CSV 导入接口（admin 上传，backend 解析后写 `match_results` / `match_odds`）

---

## 四、前端/UX

| 项 | 决策 |
| --- | --- |
| 语言 | TypeScript（严格模式） |
| UI 组件 | shadcn/ui（Tailwind CSS + CSS 变量） |
| 样式策略 | Tailwind 为主；复杂组件用 Stylus Module（`*.module.styl`，camelCase 类名） |
| 主题 | **暗色模式优先**，按钮可切浅色（`next-themes`） |
| 国际化 | **暂纯中文**，但文案集中管理在 `frontend/lib/i18n/zh.ts`，便于未来加 `en.ts` |
| 图表 | Recharts（优先，shadcn 生态原生支持） |
| 表单 | react-hook-form + zod |
| 全局状态 | Zustand |
| URL 状态 | nuqs |
| 路由守卫 | Next.js Middleware + JWT |

---

## 五、测试策略

| 层 | 工具 | 覆盖 |
| --- | --- | --- |
| 后端单元测试 | pytest + pytest-asyncio | 评分函数、Kelly、爬虫解析器（用 HTML fixture） |
| 后端集成测试 | pytest + FastAPI TestClient | API 路由 + SQLite in-memory DB（或 testcontainers mysql） |
| 前端单元测试 | Vitest + React Testing Library | 组件、hooks |
| E2E | **不做**（V1 不引入 Playwright E2E，仅作为爬虫备份存在） |
| 覆盖率目标 | 后端核心 engine ≥ 85%，API ≥ 70%，前端关键页面 ≥ 60% |

---

## 六、Git / 分支策略

| 项 | 决策 |
| --- | --- |
| 仓库状态 | **当前未 init**，P1 计划第一步 `git init` |
| 默认分支 | `main` |
| 工作流 | 每份子计划（P1-P7）开一个 feature 分支，完成后合并回 `main`（不强制 PR，单人开发） |
| 提交规范 | Conventional Commits（`feat:` / `fix:` / `chore:` / `docs:` / `test:` / `refactor:`） |
| 远端 | 暂不配置（用户未提供） |

---

## 七、日志与可观测性

- **后端日志**：`structlog` 或 `loguru`，默认 JSON 格式，文件 `backend/logs/app.log`
- **抓取日志**：文件 + `scrape_logs` 表（记录每次 job：起止时间、抓取数量、失败原因）
- **前端**：`console` + Sentry 集成点预留（V1 不接入真实 Sentry）

---

## 八、环境变量清单（放入 `.env.example`）

```
# Backend
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=sporttery
MYSQL_PASSWORD=changeme
MYSQL_DATABASE=sporttery_10x
JWT_SECRET=change-me-in-prod
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200
TIMEZONE=Asia/Shanghai
LOG_LEVEL=INFO

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## 九、后续计划编号

| # | 主题 | 产出 |
| --- | --- | --- |
| P1 | 项目脚手架与基础设施 | Monorepo 目录、Docker Compose、健康检查、CI 模板 |
| P2 | 数据模型与迁移 | 9 张表 SQLAlchemy 模型 + Alembic 迁移 + 种子脚本 |
| P3 | 用户认证模块 | 注册/登录/角色/JWT/前端登录页 |
| P4 | 爬虫与定时任务 | sporttery + titan007 爬虫、APScheduler、补抓 API、抓取面板 |
| P5 | 评分引擎与 Kelly 计算 | 纯函数 + 单测 + 固定 fixture + Dashboard 推荐页 |
| P6 | 回测与对比 | 批处理引擎 + 统计输出 + 图表页 + 双模型对比 + equity_curve |
| P7 | 模型配置 UI + 复盘闭环 | `/model`（克隆/调权重/激活）+ `/review` + Dashboard「已结束」Tab |
| P8 H1 | 技术债清理 | `ModelConfig.name` 唯一（TD-2）+ `/api/reviews` 乐观锁（TD-1）+ 激活即时重算（TD-6） |

> **补注**（2026-04-27）：实际交付顺序与文档略有调整 —— P6 承载"回测"，P7 承载"模型配置 + 复盘"；两者并非同一阶段。决策本表已同步更新。
