from pathlib import Path

from app.research.reporting import write_v33_report


def test_write_v33_report_creates_markdown_and_csv(tmp_path: Path):
    report_path = tmp_path / "report.md"
    bucket_path = tmp_path / "buckets.csv"
    combo_path = tmp_path / "combo.csv"
    random_path = tmp_path / "random.csv"

    write_v33_report(
        report_path=report_path,
        bucket_csv_path=bucket_path,
        combo_csv_path=combo_path,
        random_csv_path=random_path,
        summary={
            "model_name": "empirical-v32-filtered-candidate",
            "date_from": "2024-09-28",
            "date_to": "2026-04-22",
        },
        factor_buckets=[{"factor": "league", "label": "英超", "bets": 10, "hits": 4, "roi": 0.2}],
        combo_summaries=[{"strategy": "same_day_strongest", "combo_count": 5, "roi": 0.1}],
        random_summaries=[{"label": "全市场随机", "roi_avg": -0.1, "roi_p90": 0.05}],
    )

    assert "V3.3 单场因子诊断" in report_path.read_text(encoding="utf-8")
    assert bucket_path.read_text(encoding="utf-8-sig").startswith("factor,label")
    assert combo_path.exists()
    assert random_path.exists()
