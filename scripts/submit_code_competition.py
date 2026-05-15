#!/usr/bin/env python3
"""
Kaggle code competition への提出スクリプト。
--approval-file が存在する場合のみ提出を実行する（承認ゲート必須）。

【承認ファイルの作成方法】
  submissions/approved/exp_XXXX_approval.yaml を手動で作成する。

  フォーマット:
    exp_id: "0001"
    submission_file: "submissions/candidates/submission_blend_50_50.csv"
    notebook_kernel: "your_user/birdclef2026-inference"
    notebook_version: 12
    approved_by: "your_name"
    approved_at: "2026-05-15T10:00:00"
    reason: "SED baseline のLBテスト"
    validation_passed: true

使用例:
    # 承認ファイルあり（実際に提出）
    python scripts/submit_code_competition.py \
        --competition birdclef-2026 \
        --approval-file submissions/approved/exp_0001_approval.yaml

    # dry-run（提出せずに確認のみ）
    python scripts/submit_code_competition.py \
        --competition birdclef-2026 \
        --approval-file submissions/approved/exp_0001_approval.yaml \
        --dry-run
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVENTS = ROOT / "experiments" / "events.jsonl"

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Kaggle code competition へ提出（承認ファイル必須）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--competition", required=True,
                        help="コンペティション名 (例: birdclef-2026)")
    parser.add_argument("--approval-file", required=True,
                        help="承認YAMLファイルのパス (submissions/approved/exp_XXXX_approval.yaml)")
    parser.add_argument("--message", default=None,
                        help="提出メッセージ（省略時はapproval fileのreasonを使用）")
    parser.add_argument("--dry-run", action="store_true",
                        help="提出せず内容を表示するだけ")
    return parser.parse_args()


def load_approval(path: Path) -> dict:
    """承認ファイルを読み込む。YAMLまたはJSON形式を受け付ける。"""
    if not path.exists():
        print(f"ERROR: 承認ファイルが見つかりません: {path}", file=sys.stderr)
        print(f"", file=sys.stderr)
        print(f"  提出するには先に承認ファイルを作成してください:", file=sys.stderr)
        print(f"  submissions/approved/exp_XXXX_approval.yaml", file=sys.stderr)
        print(f"", file=sys.stderr)
        print(f"  フォーマット例:", file=sys.stderr)
        print(f"    exp_id: \"0001\"", file=sys.stderr)
        print(f"    submission_file: \"submissions/candidates/submission_blend.csv\"", file=sys.stderr)
        print(f"    notebook_kernel: \"your_user/birdclef2026-inference\"", file=sys.stderr)
        print(f"    notebook_version: 12", file=sys.stderr)
        print(f"    approved_by: \"your_name\"", file=sys.stderr)
        print(f"    approved_at: \"2026-05-15T10:00:00\"", file=sys.stderr)
        print(f"    reason: \"SED baseline のLBテスト\"", file=sys.stderr)
        print(f"    validation_passed: true", file=sys.stderr)
        sys.exit(1)

    if HAS_YAML:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    else:
        # YAMLがない場合はJSONとして試みる
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("ERROR: PyYAML が未インストールです。pip install pyyaml", file=sys.stderr)
            sys.exit(1)


def validate_approval(approval: dict) -> list[str]:
    """承認ファイルの必須フィールドを検証する。"""
    required = ["exp_id", "submission_file", "notebook_kernel",
                "notebook_version", "approved_by", "approved_at", "reason"]
    missing = [f for f in required if f not in approval]

    errors = []
    if missing:
        errors.append(f"必須フィールドが不足: {missing}")

    if approval.get("validation_passed") is not True:
        errors.append("validation_passed が true でありません。validate_submission.py を実行してください。")

    sub_path = ROOT / approval.get("submission_file", "")
    if not sub_path.exists():
        errors.append(f"submission_file が見つかりません: {sub_path}")

    return errors


def run_kaggle_submit(competition: str, kernel: str, version: int,
                      sub_file: str, message: str, dry_run: bool) -> bool:
    cmd = [
        "kaggle", "competitions", "submit",
        "-c", competition,
        "-k", kernel,
        "-f", sub_file,
        "-v", str(version),
        "-m", message,
    ]

    print(f"\n実行コマンド:")
    print(f"  {' '.join(cmd)}")

    if dry_run:
        print(f"\n[DRY-RUN] 実際の提出はスキップします。")
        return True

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"[OK] 提出成功")
            print(result.stdout)
            return True
        else:
            print(f"[ERROR] 提出失敗 (exit code {result.returncode})")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("ERROR: kaggle CLI が見つかりません。pip install kaggle でインストールしてください。", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("ERROR: kaggle コマンドがタイムアウトしました。", file=sys.stderr)
        return False


def append_event(event: dict):
    line = json.dumps(event, ensure_ascii=False)
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def archive_submission(approval: dict, dry_run: bool):
    """提出済みファイルを submitted/ に移動する。"""
    src = ROOT / approval["submission_file"]
    submitted_dir = ROOT / "submissions" / "submitted"
    submitted_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = submitted_dir / f"exp_{approval['exp_id']}_{ts}_{src.name}"

    if dry_run:
        print(f"[DRY-RUN] {src} → {dst} にアーカイブ予定")
        return

    import shutil
    shutil.copy2(src, dst)
    print(f"[OK] submission をアーカイブ: {dst}")


def main():
    args = parse_args()

    print(f"\n{'='*55}")
    print(f"BirdCLEF+ 2026 — Kaggle 提出ゲート")
    print(f"{'='*55}")

    approval_path = Path(args.approval_file)
    approval = load_approval(approval_path)

    print(f"\n--- 承認ファイル内容 ---")
    for k, v in approval.items():
        print(f"  {k}: {v}")

    errors = validate_approval(approval)
    if errors:
        print(f"\n[BLOCKED] 承認ファイルに問題があります:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    print(f"\n[OK] 承認ファイルの検証通過")

    message = args.message or approval.get("reason", f"exp_{approval['exp_id']}")
    success = run_kaggle_submit(
        competition=args.competition,
        kernel=approval["notebook_kernel"],
        version=int(approval["notebook_version"]),
        sub_file=str(ROOT / approval["submission_file"]),
        message=message,
        dry_run=args.dry_run,
    )

    if success and not args.dry_run:
        ts = datetime.now(timezone.utc).isoformat()
        event = {
            "ts": ts,
            "event": "submitted",
            "exp_id": approval["exp_id"],
            "competition": args.competition,
            "kernel": approval["notebook_kernel"],
            "version": approval["notebook_version"],
            "submission_file": approval["submission_file"],
            "approved_by": approval["approved_by"],
            "reason": approval.get("reason", ""),
        }
        append_event(event)
        archive_submission(approval, dry_run=False)
        print(f"\n次のステップ:")
        print(f"  LBスコアを確認したら:")
        print(f"  python scripts/ingest_lb_result.py --exp-id {approval['exp_id']} --public-lb <score>")

    elif not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
