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

## Feature Matrix（按设计文档第六章）

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| ① 数据抓取 | ✅ | 500/竞彩/sofascore/FBref 抓取 + APScheduler 调度 |
| ② 复盘回写 | ✅ P7 | `/api/reviews`、`/review`、Dashboard「已结束」Tab |
| ③ 评分推荐 | ✅ | 6 维模型 + Kelly 带，active 版本自动生效 |
| ④ 模型配置 | ✅ P7 | `/model` 克隆 / 权重 / 阈值 / Kelly 带在线编辑 + 激活 |
| ⑤ 回测对比 | ✅ | `/backtest`，多版本 ROI/命中率/Sharpe 对比 |
| ⑥ 盘口异动告警 | ⏳ P8+ | 延后 |
| ⑦ 爬虫管理面板 | ⏳ P8+ | 延后 |

## 运营文档

- 模型调参与复盘手册：`docs/superpowers/guides/model-config-workflow.md`
- 部署手册：`docs/deployment/DEPLOYMENT.md`
- 使用手册：`docs/usage/USAGE.md`
- 产品需求（PRD）：`docs/prd/PRD.md`

## 项目规划

- 架构设计：`docs/superpowers/specs/2026-04-21-sporttery-trading-system-design.md`（V1.0；与实现差异见 `docs/specs/DESIGN_REVIEW_2026-04-21.md`）
- 分阶段计划：`docs/superpowers/plans/2026-04-21-p1..p7-*.md`
- 技术债清理：`docs/superpowers/plans/2026-04-27-p8-tech-debt.md`（H1 已落地：`ModelConfig.name` 唯一、`/api/reviews` 乐观锁、激活即时重算）
