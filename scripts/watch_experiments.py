#!/usr/bin/env python3
"""
実験完了を監視するウォッチャー（ローカルPC常駐用）。
experiments/running/ 内の status.json を検知して events.jsonl に記録し
レポート生成をトリガーする。

【完了判定条件（全て満たすこと）】
  1. experiments/running/exp_XXXX/status.json が存在する
  2. status.json["status"] == "completed" または "failed"
  3. experiments/running/exp_XXXX/metrics.json が存在する（completed時のみ）
  4. experiments/running/exp_XXXX/stdout.log が存在する
  5. error.log が存在する場合、空または known warning のみ（未実装の場合は警告のみ）

【status.json の形式（学習スクリプトが生成する）】
  {
    "exp_id": "0001",
    "status": "completed",
    "cv_score": 0.7512,
    "best_epoch": 42,
    "total_time_sec": 3600,
    "completed_at": "2026-05-15T12:00:00Z"
  }

【metrics.json の形式】
  {
    "cv_score": 0.7512,
    "fold_scores": [0.74, 0.75, 0.76, 0.73, 0.75],
    "best_epoch": 42,
    "train_loss": 0.312,
    "val_loss": 0.298
  }

【使用方法】
  python scripts/watch_experiments.py --once    # 一回だけチェック
  python scripts/watch_experiments.py           # 600秒ごとに常駐監視
  python scripts/watch_experiments.py --interval-sec 300
"""

import argparse
import csv
import hashlib
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_info(path: Path) -> dict:
    """ファイルのSHA256・サイズ・パスを返す。"""
    if not path.exists():
        return {"path": str(path), "exists": False}
    info = {
        "path": str(path.relative_to(ROOT)),
        "exists": True,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }
    # submission.csv の場合は shape も記録
    if path.suffix == ".csv" and path.stat().st_size > 0:
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            info["shape"] = [len(lines) - 1, len(lines[0].split(","))]
        except Exception:
            pass
    return info


def check_completion(exp_dir: Path) -> tuple[bool, str, dict]:
    """
    完了判定を行う。
    Returns: (is_complete, status, status_data)
    """
    status_file = exp_dir / "status.json"
    metrics_file = exp_dir / "metrics.json"
    stdout_file = exp_dir / "stdout.log"

    # done.json もサポート（後方互換）
    done_file = exp_dir / "done.json"
    if not status_file.exists() and done_file.exists():
        status_file = done_file

    if not status_file.exists():
        return False, "pending", {}

    try:
        with open(status_file, encoding="utf-8") as f:
            status_data = json.load(f)
    except Exception as e:
        log(f"WARNING: status.json の読み込み失敗 {status_file}: {e}")
        return False, "error", {}

    exp_status = status_data.get("status", "unknown")

    if exp_status == "failed":
        return True, "failed", status_data

    if exp_status != "completed":
        return False, exp_status, status_data

    # completed の場合: metrics.json と stdout.log の存在確認
    missing = []
    if not metrics_file.exists():
        missing.append("metrics.json")
    if not stdout_file.exists():
        missing.append("stdout.log")

    if missing:
        log(f"WARNING: exp_{status_data.get('exp_id', '?')} は status=completed だが {missing} が欠けています")
        # 警告のみ。ブロックしない（学習スクリプトによっては生成しないケースもある）

    return True, "completed", status_data


def append_event(event: dict):
    line = json.dumps(event, ensure_ascii=False)
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def update_registry_status(exp_id: str, status: str, cv_score: float | None):
    if not REGISTRY.exists():
        return
    with open(REGISTRY, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    updated = False
    for row in rows:
        if row["exp_id"] == exp_id:
            row["status"] = status
            if cv_score is not None:
                row["cv_score"] = str(cv_score)
            updated = True
            break

    if updated and fieldnames:
        with open(REGISTRY, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def process_experiment(exp_dir: Path, no_report: bool) -> bool:
    is_complete, status, status_data = check_completion(exp_dir)
    if not is_complete:
        return False

    exp_id = status_data.get("exp_id") or exp_dir.name.replace("exp_", "")
    cv_score = status_data.get("cv_score")
    log(f"実験完了を検出: exp_{exp_id} status={status} cv={cv_score}")

    # 成果物のSHA256を収集
    artifacts = {}
    for artifact_name, pattern in [
        ("metrics_json", "metrics.json"),
        ("stdout_log", "stdout.log"),
        ("status_json", "status.json"),
        ("config_yaml", "config.yaml"),
    ]:
        artifact_path = exp_dir / pattern
        artifacts[artifact_name] = artifact_info(artifact_path)

    # submission.csv があれば記録
    for sub_candidate in exp_dir.glob("submission*.csv"):
        artifacts["submission_csv"] = artifact_info(sub_candidate)
        break

    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "ts": ts,
        "event": "status_changed",
        "exp_id": exp_id,
        "status": status,
        "cv_score": cv_score,
        "best_epoch": status_data.get("best_epoch"),
        "total_time_sec": status_data.get("total_time_sec"),
        "artifacts": artifacts,
        "notes": status_data.get("notes", ""),
    }
    append_event(event)

    # registry.csv を更新
    update_registry_status(exp_id, status, cv_score)

    # running/ → completed/ or failed/ に移動
    dst_dir = (COMPLETED_DIR if status == "completed" else FAILED_DIR) / f"exp_{exp_id}"
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(exp_dir, dst_dir, dirs_exist_ok=True)
        shutil.rmtree(exp_dir)
        log(f"移動完了: {exp_dir.name} → {'completed' if status == 'completed' else 'failed'}/")
    except Exception as e:
        log(f"WARNING: ディレクトリ移動に失敗: {e}")

    # ログサマリーのトリガー（completed のみ）
    if not no_report and status == "completed":
        log_file = status_data.get("log_file", str(FAILED_DIR.parent / "train" / f"exp_{exp_id}_train.log"))
        report_script = ROOT / "scripts" / "summarize_log.py"
        if report_script.exists() and Path(log_file).exists():
            try:
                subprocess.run(
                    [sys.executable, str(report_script),
                     "--log", log_file, "--exp-id", exp_id, "--save"],
                    capture_output=True, timeout=60,
                )
                log(f"ログサマリー生成: exp_{exp_id}")
            except Exception as e:
                log(f"WARNING: ログサマリー生成失敗: {e}")

    return True


def scan_once(no_report: bool) -> int:
    if not RUNNING_DIR.exists():
        return 0

    processed = 0
    for exp_dir in RUNNING_DIR.iterdir():
        if exp_dir.is_dir() and not exp_dir.name.startswith("."):
            if process_experiment(exp_dir, no_report):
                processed += 1
    return processed


def main():
    args = parse_args()

    log(f"=== BirdCLEF Experiment Watcher 起動 ===")
    log(f"完了判定条件: status.json[status==completed] + metrics.json + stdout.log")
    log(f"監視対象: {RUNNING_DIR}")

    if args.once:
        count = scan_once(args.no_report)
        log(f"チェック完了: {count}件の完了実験を処理しました")
        return

    log(f"常駐監視モード（間隔: {args.interval_sec}秒）。Ctrl+C で停止。")
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
