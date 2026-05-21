from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

Rows = list[dict[str, Any]]


def _write_csv(path: Path, rows: Rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    all_keys = sorted({key for row in rows for key in row})
    preferred = ["factor", "label", "strategy"]
    keys = [key for key in preferred if key in all_keys] + [
        key for key in all_keys if key not in preferred
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _markdown_table(rows: Rows, keys: list[str]) -> str:
    if not rows:
        return "无数据\n"
    lines = ["| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return "\n".join(lines) + "\n"


def write_v33_report(
    *,
    report_path: Path,
    bucket_csv_path: Path,
    combo_csv_path: Path,
    random_csv_path: Path,
    summary: dict[str, Any],
    factor_buckets: Rows,
    combo_summaries: Rows,
    random_summaries: Rows,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(bucket_csv_path, factor_buckets)
    _write_csv(combo_csv_path, combo_summaries)
    _write_csv(random_csv_path, random_summaries)

    content = [
        "# V3.3 单场因子诊断与二串一可行性评估报告",
        "",
        "## 1. 摘要",
        _markdown_table([summary], sorted(summary)),
        "## 2. 单场因子 Top 观察",
        _markdown_table(
            factor_buckets[:20],
            sorted({key for row in factor_buckets[:20] for key in row}) if factor_buckets else [],
        ),
        "## 3. 二串一策略对比",
        _markdown_table(
            combo_summaries,
            sorted({key for row in combo_summaries for key in row}) if combo_summaries else [],
        ),
        "## 4. 随机对照组",
        _markdown_table(
            random_summaries,
            sorted({key for row in random_summaries for key in row}) if random_summaries else [],
        ),
        "## 5. 说明",
        "- 本报告用于研究诊断, 不接今日推荐。",
        "- 随机对照用于判断模型是否显著优于随机买。",
    ]
    report_path.write_text("\n".join(content) + "\n", encoding="utf-8")
