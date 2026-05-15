#!/usr/bin/env python3
"""
実験を登録してqueue/に配置するスクリプト。
registry.csvへの追記とevents.jsonlへのイベント記録を行う。
既存行は絶対に変更しない。

使用例:
    python scripts/init_experiment.py \
        --name sed_baseline \
        --hypothesis "SEDモデルでベースラインを確立する" \
        --one-variable model_arch

    python scripts/init_experiment.py \
        --name mixup_augmentation \
        --hypothesis "Mixupで汎化性能を向上させる" \
        --one-variable augmentation_mixup \
        --parent 0001 \
        --notes "sed_baselineが完了してから実施"
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
REGISTRY = ROOT / "experiments" / "registry.csv"
EVENTS = ROOT / "experiments" / "events.jsonl"
QUEUE_DIR = ROOT / "experiments" / "queue"


def parse_args():
    parser = argparse.ArgumentParser(
        description="実験をqueueに登録する（registry.csv追記 + events.jsonl記録）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--name", required=True, help="実験名 (例: sed_baseline)")
    parser.add_argument("--hypothesis", required=True, help="仮説（一文で）")
    parser.add_argument("--one-variable", required=True, dest="variable",
                        help="今回変更する唯一の変数名 (one experiment, one variable 必須)")
    parser.add_argument("--parent", default="none",
                        help="ベースライン実験ID (例: 0001)。なければ 'none'")
    parser.add_argument("--notes", default="", help="備考")
    parser.add_argument("--dry-run", action="store_true", help="書き込まず内容を表示")
    return parser.parse_args()


def load_registry() -> list[dict]:
    if not REGISTRY.exists():
        return []
    with open(REGISTRY, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_next_exp_id(rows: list[dict]) -> str:
    ids = []
    for r in rows:
        try:
            ids.append(int(r["exp_id"]))
        except (ValueError, KeyError):
            pass
    return f"{max(ids) + 1:04d}" if ids else "0001"


def append_event(event: dict, dry_run: bool):
    line = json.dumps(event, ensure_ascii=False)
    if dry_run:
        print(f"[DRY-RUN] events.jsonl 追記予定:\n  {line}")
        return
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_registry(row: dict, dry_run: bool):
    fieldnames = [
        "exp_id", "name", "hypothesis", "variable_changed",
        "baseline_exp_id", "status", "cv_score", "lb_score", "date", "notes",
    ]
    if dry_run:
        print(f"[DRY-RUN] registry.csv 追記予定:")
        for k, v in row.items():
            print(f"  {k}: {v}")
        return
    file_exists = REGISTRY.exists()
    with open(REGISTRY, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def create_queue_config(exp_id: str, row: dict, args, dry_run: bool) -> Path:
    config = {
        "exp_id": exp_id,
        "name": row["name"],
        "hypothesis": row["hypothesis"],
        "variable_changed": row["variable_changed"],
        "baseline_exp_id": row["baseline_exp_id"],
        "status": "planned",
        "registered_at": row["date"],
        "notes": row["notes"],
        "execution": {
            "command": f"python train.py --config configs/experiments/exp_{exp_id}.yaml",
            "log_file": f"logs/train/exp_{exp_id}_train.log",
            "done_signal": f"experiments/running/exp_{exp_id}/done.json",
        },
    }
    out_path = QUEUE_DIR / f"exp_{exp_id}_{row['name']}.json"
    if dry_run:
        print(f"[DRY-RUN] queue config 作成予定: {out_path}")
        print(f"  {json.dumps(config, ensure_ascii=False, indent=2)}")
        return out_path
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return out_path


def validate_one_variable(variable: str, rows: list[dict]):
    """同じ変数が既に計画中/実行中でないか確認する（警告のみ）。"""
    active = [
        r for r in rows
        if r.get("variable_changed") == variable
        and r.get("status") in ("planned", "running")
    ]
    if active:
        print(f"WARNING: 同じ変数 '{variable}' の実験が既に active です:")
        for r in active:
            print(f"  exp_{r['exp_id']} ({r['name']}) status={r['status']}")
        print("  one experiment, one variable の原則に注意してください。")


def main():
    args = parse_args()
    rows = load_registry()

    # one variable チェック（警告）
    validate_one_variable(args.variable, rows)

    exp_id = get_next_exp_id(rows)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    ts = now.isoformat()

    row = {
        "exp_id": exp_id,
        "name": args.name,
        "hypothesis": args.hypothesis,
        "variable_changed": args.variable,
        "baseline_exp_id": args.parent,
        "status": "planned",
        "cv_score": "",
        "lb_score": "",
        "date": date_str,
        "notes": args.notes,
    }

    event = {
        "ts": ts,
        "event": "registered",
        "exp_id": exp_id,
        "name": args.name,
        "hypothesis": args.hypothesis,
        "variable_changed": args.variable,
        "baseline_exp_id": args.parent,
        "notes": args.notes,
    }

    print(f"=== 実験登録: exp_{exp_id} ({args.name}) ===")
    print(f"  仮説      : {args.hypothesis}")
    print(f"  変更変数  : {args.variable}")
    print(f"  ベースライン: exp_{args.parent}")

    append_registry(row, args.dry_run)
    append_event(event, args.dry_run)
    queue_path = create_queue_config(exp_id, row, args, args.dry_run)

    if not args.dry_run:
        print(f"[OK] registry.csv に exp_{exp_id} を追記しました")
        print(f"[OK] events.jsonl にイベントを記録しました")
        print(f"[OK] queue config: {queue_path}")

    print(f"\n次のステップ:")
    print(f"  1. configs/experiments/exp_{exp_id}.yaml を作成して学習設定を記述")
    print(f"  2. ローカルPCで git pull してから学習を開始")
    print(f"  3. 学習完了後: python scripts/watch_experiments.py --once")


if __name__ == "__main__":
    main()
