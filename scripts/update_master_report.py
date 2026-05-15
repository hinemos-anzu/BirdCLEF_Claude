#!/usr/bin/env python3
"""
experiments/registry.csv と knowledge/lb_history.md を読んで
knowledge/master_report.md のサマリーテーブルを自動更新するスクリプト。

使用例:
    python scripts/update_master_report.py
    python scripts/update_master_report.py --dry-run
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="master_report.md のサマリーを実験レジストリから自動更新",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true", help="書き込まず差分だけ表示")
    return parser.parse_args()


def load_registry() -> list[dict]:
    path = ROOT / "experiments" / "registry.csv"
    if not path.exists():
        print(f"ERROR: {path} が見つかりません", file=sys.stderr)
        sys.exit(1)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r["exp_id"] != "0000"]  # テンプレート行を除外


def compute_summary(rows: list[dict]) -> dict:
    total = len(rows)
    completed = [r for r in rows if r.get("status") == "completed"]
    lb_scores = []
    for r in completed:
        try:
            lb_scores.append((float(r["lb_score"]), r["exp_id"], r["name"]))
        except (ValueError, KeyError):
            pass

    best_lb = max(lb_scores, key=lambda x: x[0]) if lb_scores else None

    return {
        "total": total,
        "completed": len(completed),
        "best_lb": f"{best_lb[0]:.4f}" if best_lb else "—",
        "best_exp_id": f"exp_{best_lb[1]}" if best_lb else "—",
        "best_name": best_lb[2] if best_lb else "—",
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def build_lb_table(rows: list[dict]) -> str:
    completed = [r for r in rows if r.get("status") == "completed" and r.get("lb_score")]
    if not completed:
        return "| — | — | — | — | — |\n"

    lines = []
    for r in completed:
        cv = r.get("cv_score", "—") or "—"
        lb = r.get("lb_score", "—") or "—"
        try:
            cv_f = float(cv)
            lb_f = float(lb)
            cv_str = f"{cv_f:.4f}"
            lb_str = f"{lb_f:.4f}"
        except ValueError:
            cv_str, lb_str = cv, lb
        date = r.get("date", "—")
        lines.append(f"| exp_{r['exp_id']} | {r['name']} | {cv_str} | {lb_str} | {date} |")

    return "\n".join(lines) + "\n"


def update_master_report(summary: dict, lb_table: str, dry_run: bool):
    path = ROOT / "knowledge" / "master_report.md"
    content = path.read_text(encoding="utf-8")

    # 最終更新日
    content = re.sub(
        r"最終更新: .+",
        f"最終更新: {summary['updated']}",
        content,
    )

    # サマリーテーブル
    def replace_table_cell(text: str, label: str, value: str) -> str:
        pattern = rf"(\| {re.escape(label)} \| ).+?( \|)"
        return re.sub(pattern, rf"\g<1>{value}\2", text)

    content = replace_table_cell(content, "実験総数", str(summary["total"]))
    content = replace_table_cell(content, "完了実験数", str(summary["completed"]))
    content = replace_table_cell(content, "現在のベストLB", summary["best_lb"])
    content = replace_table_cell(content, "ベストsubmission", summary["best_exp_id"])
    content = replace_table_cell(content, "最終更新", summary["updated"])

    # LBテーブル更新
    old_table_row = "| — | — | — | — | — |"
    if old_table_row in content and lb_table.strip() != old_table_row:
        content = content.replace(
            "| 実験ID | モデル/手法 | CV | LB | 日付 |\n|--------|------------|----|----|------|\n| — | — | — | — | — |",
            f"| 実験ID | モデル/手法 | CV | LB | 日付 |\n|--------|------------|----|----|------|\n{lb_table.rstrip()}",
        )

    if dry_run:
        print("[DRY-RUN] master_report.md 更新後のサマリー:")
        print(f"  実験総数: {summary['total']}")
        print(f"  完了実験数: {summary['completed']}")
        print(f"  ベストLB: {summary['best_lb']} ({summary['best_exp_id']})")
        print(f"  最終更新: {summary['updated']}")
        return

    path.write_text(content, encoding="utf-8")
    print(f"[OK] master_report.md を更新しました")


def print_status(rows: list[dict], summary: dict):
    print(f"\n{'='*50}")
    print(f"BirdCLEF+ 2026 実験状況サマリー")
    print(f"{'='*50}")
    print(f"実験総数      : {summary['total']}")
    print(f"完了実験数    : {summary['completed']}")
    print(f"ベストLB      : {summary['best_lb']}")
    print(f"ベスト実験    : {summary['best_exp_id']} ({summary['best_name']})")
    print(f"最終更新      : {summary['updated']}")

    planned = [r for r in rows if r.get("status") == "planned"]
    running = [r for r in rows if r.get("status") == "running"]
    if planned:
        print(f"\n計画中の実験  : {len(planned)}件")
        for r in planned[:3]:
            print(f"  - exp_{r['exp_id']}: {r['name']}")
        if len(planned) > 3:
            print(f"  ... 他{len(planned)-3}件")
    if running:
        print(f"\n実行中の実験  : {len(running)}件")
        for r in running:
            print(f"  - exp_{r['exp_id']}: {r['name']}")
    print(f"{'='*50}\n")


def main():
    args = parse_args()
    rows = load_registry()
    summary = compute_summary(rows)
    lb_table = build_lb_table(rows)

    print_status(rows, summary)
    update_master_report(summary, lb_table, args.dry_run)

    print("次のステップ:")
    print("  python scripts/suggest_next_experiments.py  # 次実験を提案")
    print("  python scripts/ingest_lb_result.py --help   # LB結果を取り込む")


if __name__ == "__main__":
    main()
