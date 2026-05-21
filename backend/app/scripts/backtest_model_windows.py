"""Run full-range and 90-day model backtests, then write a Markdown report."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.core.database import SessionLocal
from app.engine.backtest_service import BacktestService
from app.models import BacktestSession, ModelConfig

DEFAULT_MODELS = ["default", "empirical-v32-filtered-candidate"]


@dataclass(frozen=True)
class RunResult:
    model: str
    window_start: date
    window_end: date
    session: BacktestSession


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _pct(value: Decimal) -> str:
    return f"{(Decimal(value) * Decimal('100')):.2f}%"


def _money(value: Decimal) -> str:
    return f"{Decimal(value):.2f}"


def _md_summary_row(label: str, session: BacktestSession) -> str:
    return (
        f"| {label} | {session.total_bets} | {session.hit_count} | "
        f"{_pct(session.hit_rate)} | {_pct(session.roi)} | "
        f"{_pct(session.kelly_roi)} | {_money(session.profit_loss)} |"
    )


def _window_ranges(start: date, end: date, days: int) -> list[tuple[date, date]]:
    ranges: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        ranges.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return ranges


def _bet_type_rows(session: BacktestSession) -> list[str]:
    buckets: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "bets": 0,
            "hits": 0,
            "profit_loss_fixed": Decimal("0"),
            "profit_loss_kelly": Decimal("0"),
            "stake_fixed": Decimal("0"),
            "stake_kelly": Decimal("0"),
        }
    )
    for bet in session.bets_detail or []:
        bucket = buckets[str(bet["bet_type"])]
        bucket["bets"] = int(bucket["bets"]) + 1
        if bet.get("is_hit"):
            bucket["hits"] = int(bucket["hits"]) + 1
        bucket["profit_loss_fixed"] = Decimal(bucket["profit_loss_fixed"]) + Decimal(
            str(bet["pnl_fixed"])
        )
        bucket["profit_loss_kelly"] = Decimal(bucket["profit_loss_kelly"]) + Decimal(
            str(bet["pnl_kelly"])
        )
        bucket["stake_fixed"] = Decimal(bucket["stake_fixed"]) + Decimal(
            str(bet["stake_fixed"])
        )
        bucket["stake_kelly"] = Decimal(bucket["stake_kelly"]) + Decimal(
            str(bet["stake_kelly"])
        )

    rows = []
    for bet_type in ("draw", "handicap_draw"):
        bucket = buckets[bet_type]
        bets = int(bucket["bets"])
        hits = int(bucket["hits"])
        fixed_stake = Decimal(bucket["stake_fixed"])
        kelly_stake = Decimal(bucket["stake_kelly"])
        hit_rate = Decimal(hits) / Decimal(bets) if bets else Decimal("0")
        fixed_roi = (
            Decimal(bucket["profit_loss_fixed"]) / fixed_stake
            if fixed_stake
            else Decimal("0")
        )
        kelly_roi = (
            Decimal(bucket["profit_loss_kelly"]) / kelly_stake
            if kelly_stake
            else Decimal("0")
        )
        rows.append(
            f"| {bet_type} | {bets} | {hits} | {_pct(hit_rate)} | "
            f"{_pct(fixed_roi)} | {_pct(kelly_roi)} |"
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument("--report", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    report_path = Path(args.report)

    with SessionLocal() as db:
        service = BacktestService(db)
        configs = {
            cfg.name: cfg
            for cfg in db.query(ModelConfig)
            .filter(ModelConfig.name.in_(args.models))
            .all()
        }
        missing = [name for name in args.models if name not in configs]
        if missing:
            raise SystemExit(f"missing model configs: {', '.join(missing)}")

        full: list[RunResult] = []
        windows: list[RunResult] = []
        for model_name in args.models:
            cfg = configs[model_name]
            session = service.run(model_config_id=cfg.id, date_from=start, date_to=end)
            full.append(RunResult(model_name, start, end, session))
            print(
                f"full model={model_name} id={session.id} bets={session.total_bets} "
                f"hits={session.hit_count} roi={session.roi}"
            )

            for window_start, window_end in _window_ranges(start, end, args.window_days):
                win_session = service.run(
                    model_config_id=cfg.id,
                    date_from=window_start,
                    date_to=window_end,
                )
                windows.append(RunResult(model_name, window_start, window_end, win_session))
                print(
                    f"window model={model_name} {window_start}->{window_end} "
                    f"id={win_session.id} bets={win_session.total_bets} roi={win_session.roi}"
                )

        windows_by_key = {
            (result.model, result.window_start, result.window_end): result.session
            for result in windows
        }

        window_rows = []
        for window_start, window_end in _window_ranges(start, end, args.window_days):
            cells = []
            for model_name in args.models:
                session = windows_by_key[(model_name, window_start, window_end)]
                cells.append(
                    f"{_pct(session.roi)} / {session.total_bets} 注 / "
                    f"{_pct(session.hit_rate)}"
                )
            window_rows.append(
                f"| {window_start} 至 {window_end} | " + " | ".join(cells) + " |"
            )

    report = [
        "# 当前模型 90 天窗口回测报告",
        "",
        f"数据范围: {start.isoformat()} 至 {end.isoformat()}",
        f"回测模型: {', '.join(args.models)}",
        "",
        "## 1. 全样本对比",
        "",
        "| 模型 | 下注数 | 命中 | 命中率 | 固定 ROI | Kelly ROI | 盈亏 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        *[_md_summary_row(result.model, result.session) for result in full],
        "",
        "## 2. 90 天窗口对比",
        "",
        "| 窗口 | " + " | ".join(args.models) + " |",
        "| --- | " + " | ".join("---:" for _ in args.models) + " |",
        *window_rows,
        "",
        "## 3. 当前主模型分 bet_type",
        "",
        "| bet_type | 下注数 | 命中 | 命中率 | 固定 ROI | Kelly ROI |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *_bet_type_rows(full[-1].session),
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
