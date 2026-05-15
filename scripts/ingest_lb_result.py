#!/usr/bin/env python3
"""
LBスコアをevents.jsonl・lb_history・registry.csvに取り込むスクリプト。

使用例:
    python scripts/ingest_lb_result.py --exp-id 0001 --public-lb 0.7234
    python scripts/ingest_lb_result.py --exp-id 0001 --public-lb 0.7234 --private-lb 0.7198
    python scripts/ingest_lb_result.py --exp-id 0001 --public-lb 0.7234 \
        --cv-score 0.7512 --note "SED baseline, public LB" --failed
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVENTS = ROOT / "experiments" / "events.jsonl"
REGISTRY = ROOT / "experiments" / "registry.csv"
LB_HISTORY_MD = ROOT / "knowledge" / "lb_history.md"
LB_HISTORY_DIR = ROOT / "knowledge" / "lb_history"
FAILED_MD = ROOT / "knowledge" / "failed_methods.md"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Kaggle LBスコアを知識ベースに取り込む",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--exp-id", required=True, help="実験ID (例: 0001)")
    parser.add_argument("--public-lb", required=True, type=float,
                        help="public LB スコア")
    parser.add_argument("--private-lb", type=float, default=None,
                        help="private LB スコア（コンペ終了後）")
    parser.add_argument("--cv-score", type=float, default=None,
                        help="CV/OOFスコア（オプション）")
    parser.add_argument("--note", default="", help="メモ・備考")
    parser.add_argument("--failed", action="store_true",
                        help="この実験を失敗として記録する（failed_methods.mdに追記）")
    parser.add_argument("--dry-run", action="store_true",
                        help="実際には書き込まず内容を表示")
    return parser.parse_args()


def load_registry() -> list[dict]:
    if not REGISTRY.exists():
        print(f"ERROR: {REGISTRY} が見つかりません", file=sys.stderr)
        sys.exit(1)
    with open(REGISTRY, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_event(event: dict, dry_run: bool):
    line = json.dumps(event, ensure_ascii=False)
    if dry_run:
        print(f"[DRY-RUN] events.jsonl 追記予定:\n  {line}")
        return
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def update_registry(exp_id: str, public_lb: float, private_lb: float | None,
                    cv_score: float | None, dry_run: bool):
    rows = load_registry()
    target = next((r for r in rows if r["exp_id"] == exp_id), None)

    if target is None:
        print(f"WARNING: exp_id={exp_id} がregistry.csvに見つかりません。スキップします。")
        return

    if dry_run:
        print(f"[DRY-RUN] registry.csv の exp_{exp_id} を更新予定:")
        print(f"  lb_score: {target.get('lb_score', '')} -> {public_lb}")
        if cv_score is not None:
            print(f"  cv_score: {target.get('cv_score', '')} -> {cv_score}")
        print(f"  status: {target.get('status', '')} -> completed")
        return

    target["lb_score"] = str(public_lb)
    if cv_score is not None:
        target["cv_score"] = str(cv_score)
    target["status"] = "completed"

    fieldnames = list(rows[0].keys())
    with open(REGISTRY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] registry.csv を更新しました (exp_{exp_id})")


def append_lb_history(args, dry_run: bool):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M")

    cv_str = f"{args.cv_score:.4f}" if args.cv_score is not None else "—"
    priv_str = f"{args.private_lb:.4f}" if args.private_lb is not None else "—"
    lb_cv_diff = "—"
    if args.cv_score is not None:
        diff = args.cv_score - args.public_lb
        lb_cv_diff = f"+{diff:.4f}" if diff >= 0 else f"{diff:.4f}"

    log_line = (
        f"# {time_str} | exp_{args.exp_id} | public={args.public_lb:.4f}"
        f" | private={priv_str} | cv={cv_str} | {args.note}\n"
    )

    if dry_run:
        print(f"[DRY-RUN] lb_history.md に追記予定:\n  {log_line.strip()}")
        return

    # versioned snapshot を lb_history/ ディレクトリに保存
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    snapshot_path = LB_HISTORY_DIR / f"lb_{args.exp_id}_{ts_str}.json"
    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "exp_id": args.exp_id,
        "public_lb": args.public_lb,
        "private_lb": args.private_lb,
        "cv_score": args.cv_score,
        "lb_cv_diff": args.cv_score - args.public_lb if args.cv_score else None,
        "note": args.note,
    }
    LB_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"[OK] lb_history スナップショット: {snapshot_path.name}")

    # lb_history.md にも追記
    if LB_HISTORY_MD.exists():
        content = LB_HISTORY_MD.read_text(encoding="utf-8")
        if "# 以下に追記" in content:
            content = content.replace(
                "# 以下に追記\n```",
                f"# 以下に追記\n{log_line}```",
            )
        else:
            content += f"\n{log_line}"
        LB_HISTORY_MD.write_text(content, encoding="utf-8")
        print(f"[OK] lb_history.md を更新しました")


def append_failed_methods(exp_id: str, note: str, dry_run: bool):
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

    if FAILED_MD.exists():
        content = FAILED_MD.read_text(encoding="utf-8")
        content += entry
        FAILED_MD.write_text(content, encoding="utf-8")

    # versioned snapshot
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_dir = ROOT / "knowledge" / "failed_methods"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"fail_{exp_id}_{ts_str}.md"
    snap_path.write_text(entry, encoding="utf-8")
    print(f"[OK] failed_methods.md と {snap_path.name} に記録しました")


def main():
    args = parse_args()

    if not (0.0 <= args.public_lb <= 1.0):
        print(f"WARNING: public_lb={args.public_lb} が [0,1] の範囲外です。正しいですか？")

    print(f"=== LB結果取り込み: exp_{args.exp_id} | public LB={args.public_lb:.4f} ===")

    # events.jsonl に記録
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "ts": ts,
        "event": "lb_ingested",
        "exp_id": args.exp_id,
        "public_lb": args.public_lb,
        "private_lb": args.private_lb,
        "cv_score": args.cv_score,
        "failed": args.failed,
        "note": args.note,
    }
    append_event(event, args.dry_run)

    update_registry(args.exp_id, args.public_lb, args.private_lb, args.cv_score, args.dry_run)
    append_lb_history(args, args.dry_run)

    if args.failed:
        append_failed_methods(args.exp_id, args.note, args.dry_run)
        print(f"[INFO] --failed フラグあり → failed_methods に記録しました")

    print("=== 完了 ===")
    print("次のステップ: python scripts/update_master_report.py")


if __name__ == "__main__":
    main()
