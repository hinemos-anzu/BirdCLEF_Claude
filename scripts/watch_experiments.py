#!/usr/bin/env python3
"""
実験の完了を監視するウォッチャー（ローカルPC常駐用）。
experiments/running/ 内の done.json を検知して events.jsonl に記録し
レポート生成をトリガーする。

【使用方法】
  # 一回だけチェック（CI・手動確認用）
  python scripts/watch_experiments.py --once

  # 600秒ごとに常駐監視（ローカルPC推奨）
  python scripts/watch_experiments.py

  # 間隔を変更
  python scripts/watch_experiments.py --interval-sec 300

【done.jsonの形式（学習スクリプトが生成する）】
  {
    "exp_id": "0001",
    "status": "completed",
    "cv_score": 0.7512,
    "best_epoch": 42,
    "total_time_sec": 3600,
    "completed_at": "2026-05-15T12:00:00Z",
    "log_file": "logs/train/exp_0001_train.log",
    "notes": ""
  }

  status は "completed" または "failed" を指定する。
"""

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVENTS = ROOT / "experiments" / "events.jsonl"
RUNNING_DIR = ROOT / "experiments" / "running"
COMPLETED_DIR = ROOT / "experiments" / "completed"
FAILED_DIR = ROOT / "experiments" / "failed"
REGISTRY = ROOT / "experiments" / "registry.csv"
WATCHER_LOG = ROOT / "logs" / "watcher" / "watcher.log"


def parse_args():
    parser = argparse.ArgumentParser(
        description="実験完了を監視してevents.jsonlに記録する（ローカルPC常駐用）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--interval-sec", type=int, default=600,
                        help="監視間隔（秒） (default: 600)")
    parser.add_argument("--once", action="store_true",
                        help="一回だけチェックして終了")
    parser.add_argument("--registry", default=str(REGISTRY),
                        help="registry.csvのパス")
    parser.add_argument("--no-report", action="store_true",
                        help="完了後のレポート生成をスキップ")
    return parser.parse_args()


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        WATCHER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(WATCHER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def append_event(event: dict):
    line = json.dumps(event, ensure_ascii=False)
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def update_registry_status(exp_id: str, status: str, cv_score: float | None):
    """registry.csv の status と cv_score を更新する（完了時のみ許可）。"""
    if not REGISTRY.exists():
        return
    with open(REGISTRY, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = rows[0].keys() if rows else []

    updated = False
    for row in rows:
        if row["exp_id"] == exp_id:
            row["status"] = status
            if cv_score is not None:
                row["cv_score"] = str(cv_score)
            updated = True
            break

    if updated:
        with open(REGISTRY, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def process_done_file(done_file: Path, no_report: bool) -> bool:
    """done.jsonを処理してイベントを記録する。"""
    try:
        with open(done_file, encoding="utf-8") as f:
            done = json.load(f)
    except Exception as e:
        log(f"ERROR: done.json の読み込み失敗 {done_file}: {e}")
        return False

    exp_id = done.get("exp_id", "unknown")
    status = done.get("status", "completed")
    cv_score = done.get("cv_score")
    ts = datetime.now(timezone.utc).isoformat()

    log(f"実験完了を検出: exp_{exp_id} status={status} cv={cv_score}")

    # events.jsonl に記録
    event = {
        "ts": ts,
        "event": "status_changed",
        "exp_id": exp_id,
        "status": status,
        "cv_score": cv_score,
        "best_epoch": done.get("best_epoch"),
        "total_time_sec": done.get("total_time_sec"),
        "log_file": done.get("log_file", ""),
        "notes": done.get("notes", ""),
    }
    append_event(event)

    # registry.csv を更新
    update_registry_status(exp_id, status, cv_score)

    # running/ → completed/ or failed/ に移動
    src_dir = done_file.parent
    if status == "completed":
        dst_dir = COMPLETED_DIR / f"exp_{exp_id}"
    else:
        dst_dir = FAILED_DIR / f"exp_{exp_id}"

    try:
        if src_dir != ROOT / "experiments" / "running":
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            shutil.rmtree(src_dir)
            log(f"移動完了: {src_dir} → {dst_dir}")
    except Exception as e:
        log(f"WARNING: ディレクトリ移動に失敗: {e}")

    # レポート生成のトリガー
    if not no_report and status == "completed":
        report_script = ROOT / "scripts" / "summarize_log.py"
        log_file = done.get("log_file", "")
        if report_script.exists() and log_file and Path(log_file).exists():
            try:
                subprocess.run(
                    [sys.executable, str(report_script),
                     "--log", log_file,
                     "--exp-id", exp_id,
                     "--save"],
                    capture_output=True, timeout=60,
                )
                log(f"ログサマリーを生成しました: exp_{exp_id}")
            except Exception as e:
                log(f"WARNING: ログサマリー生成失敗: {e}")

    return True


def scan_once(no_report: bool) -> int:
    """running/ディレクトリを一回スキャンして完了済み実験を処理する。"""
    if not RUNNING_DIR.exists():
        return 0

    processed = 0
    for done_file in RUNNING_DIR.rglob("done.json"):
        if process_done_file(done_file, no_report):
            processed += 1

    return processed


def main():
    args = parse_args()

    log(f"=== BirdCLEF Experiment Watcher 起動 ===")
    log(f"監視間隔: {args.interval_sec}秒 | 対象: {RUNNING_DIR}")

    if args.once:
        count = scan_once(args.no_report)
        log(f"チェック完了: {count}件の完了実験を処理しました")
        return

    log(f"常駐監視モード。Ctrl+C で停止。")
    while True:
        try:
            count = scan_once(args.no_report)
            if count > 0:
                log(f"{count}件の実験を処理しました")
            else:
                log(f"完了実験なし。{args.interval_sec}秒後に再チェックします。")
            time.sleep(args.interval_sec)
        except KeyboardInterrupt:
            log("ウォッチャーを停止しました。")
            break


if __name__ == "__main__":
    main()
