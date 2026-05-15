#!/usr/bin/env python3
"""
LBスコアをlb_history.mdとexperiments/registry.csvに取り込むスクリプト。

使用例:
    python scripts/ingest_lb_result.py --exp-id 0001 --lb-score 0.7234 --note "SED baseline"
    python scripts/ingest_lb_result.py --exp-id 0001 --lb-score 0.7234 \
        --cv-score 0.7512 --submission-file submissions/submitted/submission_sed.csv
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Kaggle LBスコアを知識ベースに取り込む",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--exp-id", required=True, help="実験ID (例: 0001)")
    parser.add_argument("--lb-score", required=True, type=float, help="public LB スコア")
    parser.add_argument("--cv-score", type=float, default=None, help="CV/OOFスコア（オプション）")
    parser.add_argument("--submission-file", default="", help="提出したsubmissionファイルのパス")
    parser.add_argument("--note", default="", help="メモ・備考")
    parser.add_argument("--failed", action="store_true", help="この実験を失敗として記録する")
    parser.add_argument("--dry-run", action="store_true", help="実際には書き込まず内容を表示")
    return parser.parse_args()


def load_registry() -> list[dict]:
    registry_path = ROOT / "experiments" / "registry.csv"
    if not registry_path.exists():
        print(f"ERROR: {registry_path} が見つかりません", file=sys.stderr)
        sys.exit(1)
    with open(registry_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def update_registry(exp_id: str, lb_score: float, cv_score: float | None, dry_run: bool):
    registry_path = ROOT / "experiments" / "registry.csv"
    rows = load_registry()

    target = None
    for row in rows:
        if row["exp_id"] == exp_id:
            target = row
            break

    if target is None:
        print(f"WARNING: exp_id={exp_id} がregistry.csvに見つかりません。スキップします。")
        return

    if dry_run:
        print(f"[DRY-RUN] registry.csv の exp_{exp_id} を更新予定:")
        print(f"  lb_score: {target['lb_score']} -> {lb_score}")
        if cv_score is not None:
            print(f"  cv_score: {target['cv_score']} -> {cv_score}")
        print(f"  status: {target['status']} -> completed")
        return

    target["lb_score"] = str(lb_score)
    if cv_score is not None:
        target["cv_score"] = str(cv_score)
    target["status"] = "completed"

    fieldnames = list(rows[0].keys())
    with open(registry_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] registry.csv を更新しました (exp_{exp_id})")


def append_lb_history(args, dry_run: bool):
    lb_path = ROOT / "knowledge" / "lb_history.md"
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M")

    cv_str = f"{args.cv_score:.4f}" if args.cv_score is not None else "—"
    lb_cv_diff = ""
    if args.cv_score is not None:
        diff = args.cv_score - args.lb_score
        lb_cv_diff = f"+{diff:.4f}" if diff >= 0 else f"{diff:.4f}"
    else:
        lb_cv_diff = "—"

    sub_file = Path(args.submission_file).name if args.submission_file else "—"

    log_line = (
        f"# {time_str} | exp_{args.exp_id} | {args.lb_score:.4f} | {sub_file} | {args.note}\n"
    )

    if dry_run:
        print(f"[DRY-RUN] lb_history.md に追記予定:")
        print(f"  {log_line.strip()}")
        return

    # ログ行を追記
    content = lb_path.read_text(encoding="utf-8")
    marker = "# 以下に追記\n```\n"
    if "# 以下に追記" in content:
        content = content.replace(
            "# 以下に追記\n```",
            f"# 以下に追記\n{log_line}```",
        )
    else:
        content += f"\n{log_line}"

    # テーブル行も更新
    rows = load_registry()
    count = sum(1 for r in rows if r.get("lb_score", ""))
    table_row = f"| {count} | exp_{args.exp_id} | {sub_file} | {args.lb_score:.4f} | {cv_str} | {lb_cv_diff} | {date_str} | {args.note} |\n"

    old_last_row = "| — | — | — | — | — | — | — | 初期状態 |"
    if old_last_row in content:
        content = content.replace(old_last_row, old_last_row + "\n" + table_row.rstrip())
    else:
        # テーブルの末尾に追記
        content = content.replace(
            "| — | — | — | — | — | — | — | — |",
            f"| — | — | — | — | — | — | — | — |\n{table_row.rstrip()}",
        )

    lb_path.write_text(content, encoding="utf-8")
    print(f"[OK] lb_history.md を更新しました")


def append_failed_methods(exp_id: str, note: str, dry_run: bool):
    failed_path = ROOT / "knowledge" / "failed_methods.md"
    date_str = datetime.now().strftime("%Y-%m-%d")

    rows = load_registry()
    exp_info = next((r for r in rows if r["exp_id"] == exp_id), {})
    name = exp_info.get("name", "unknown")
    variable = exp_info.get("variable_changed", "unknown")

    fail_id = f"FAIL-{exp_id}"
    entry = f"""
### [{fail_id}] {name}
- **実験ID**: exp_{exp_id}
- **日付**: {date_str}
- **失敗の種類**: LB低下
- **詳細**: {note}
- **変更した変数**: {variable}
- **CV変化**: （手動追記）
- **LB変化**: （手動追記）
- **教訓**: （手動追記）
- **再試行禁止条件**: （手動追記）

"""
    if dry_run:
        print(f"[DRY-RUN] failed_methods.md に追記予定:\n{entry}")
        return

    content = failed_path.read_text(encoding="utf-8")
    content = content.replace(
        "現在の失敗記録: 0件",
        f"現在の失敗記録: （自動カウント無効 — 手動で確認）",
    )
    content += entry
    failed_path.write_text(content, encoding="utf-8")
    print(f"[OK] failed_methods.md に {fail_id} を追記しました")


def main():
    args = parse_args()

    if not (0.0 <= args.lb_score <= 1.0):
        print(f"WARNING: lb_score={args.lb_score} が [0,1] の範囲外です。正しいですか？")

    print(f"=== LB結果取り込み: exp_{args.exp_id} | LB={args.lb_score:.4f} ===")

    update_registry(args.exp_id, args.lb_score, args.cv_score, args.dry_run)
    append_lb_history(args, args.dry_run)

    if args.failed:
        append_failed_methods(args.exp_id, args.note, args.dry_run)
        print(f"[INFO] failed フラグあり → failed_methods.md にも記録しました")

    print("=== 完了 ===")
    print("次のステップ: python scripts/update_master_report.py")


if __name__ == "__main__":
    main()
