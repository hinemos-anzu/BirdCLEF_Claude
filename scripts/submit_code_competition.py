#!/usr/bin/env python3
"""
Kaggle code competition への提出スクリプト。

承認ゲートの仕様:
  - approval YAML が存在すること（必須）
  - allow_submit: true であること（必須）
  - exp_id が候補ファイルと一致すること
  - submission_csv_sha256 が実ファイルと一致すること
  - 承認日時が古すぎないこと（デフォルト72時間）

承認ファイルフォーマット（submissions/approved/exp_XXXX_approval.yaml）:
    exp_id: "0001"
    candidate_id: "candidate_0001"
    submission_file: "submissions/candidates/submission_blend_50_50.csv"
    submission_csv_sha256: "abc123..."    # validate_submission.py の出力から取得
    notebook_kernel: "your_user/birdclef2026-inference"
    notebook_version: 12
    approved_by: "your_name"
    approved_at: "2026-05-15T10:00:00+09:00"
    reason: "SED baseline のLBテスト"
    allow_submit: true                   # ← これが true でないと提出不可
    expected_public_lb: 0.945
    risk: low
    rollback_plan: "LBが0.942を下回ったら再提出しない"

使用例:
    python scripts/submit_code_competition.py \\
        --competition birdclef-2026 \\
        --approval-file submissions/approved/exp_0001_approval.yaml

    python scripts/submit_code_competition.py \\
        --competition birdclef-2026 \\
        --approval-file submissions/approved/exp_0001_approval.yaml \\
        --dry-run
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVENTS = ROOT / "experiments" / "events.jsonl"

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

APPROVAL_MAX_AGE_HOURS = 72  # 承認ファイルの有効期間


def parse_args():
    parser = argparse.ArgumentParser(
        description="Kaggle code competition へ提出（承認ファイル + allow_submit:true 必須）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--competition", required=True,
                        help="コンペティション名 (例: birdclef-2026)")
    parser.add_argument("--approval-file", required=True,
                        help="承認YAMLファイルのパス")
    parser.add_argument("--message", default=None,
                        help="提出メッセージ（省略時はreasonを使用）")
    parser.add_argument("--max-age-hours", type=int, default=APPROVAL_MAX_AGE_HOURS,
                        help=f"承認ファイルの最大有効期間（時間）default: {APPROVAL_MAX_AGE_HOURS}")
    parser.add_argument("--dry-run", action="store_true",
                        help="提出せず内容を表示するだけ")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_approval(path: Path) -> dict:
    if not path.exists():
        print(f"\n[BLOCKED] 承認ファイルが見つかりません: {path}", file=sys.stderr)
        print(f"\n承認ファイルを作成してください:", file=sys.stderr)
        print(f"  submissions/approved/exp_XXXX_approval.yaml", file=sys.stderr)
        print(f"\n必須フィールド: allow_submit: true  が含まれていること", file=sys.stderr)
        sys.exit(1)

    if HAS_YAML:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    else:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("ERROR: PyYAML が未インストールです。pip install pyyaml", file=sys.stderr)
            sys.exit(1)


def validate_approval(approval: dict, max_age_hours: int) -> list[str]:
    errors = []

    # 1. allow_submit: true の厳格チェック
    allow = approval.get("allow_submit")
    if allow is not True:
        errors.append(
            f"allow_submit が true ではありません（現在: {allow!r}）。\n"
            f"  承認ファイルに「allow_submit: true」を明示してください。"
        )

    # 2. 必須フィールドの確認
    required = ["exp_id", "submission_file", "approved_by", "approved_at",
                "submission_csv_sha256", "notebook_kernel", "notebook_version"]
    for f in required:
        if f not in approval:
            errors.append(f"必須フィールドが不足: {f}")

    if errors:
        return errors  # 必須フィールドなければ以降のチェックを省略

    # 3. submission_file の存在確認
    sub_path = ROOT / approval["submission_file"]
    if not sub_path.exists():
        errors.append(f"submission_file が見つかりません: {sub_path}")
        return errors

    # 4. SHA256 の一致確認
    actual_sha = sha256_file(sub_path)
    expected_sha = approval.get("submission_csv_sha256", "")
    if actual_sha != expected_sha:
        errors.append(
            f"submission_csv_sha256 が一致しません。\n"
            f"  承認時 : {expected_sha}\n"
            f"  現在   : {actual_sha}\n"
            f"  ファイルが変更された可能性があります。再度承認してください。"
        )

    # 5. 承認日時の有効期限チェック
    approved_at_str = approval.get("approved_at", "")
    if approved_at_str:
        try:
            approved_at = datetime.fromisoformat(str(approved_at_str))
            if approved_at.tzinfo is None:
                approved_at = approved_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age = now - approved_at
            if age > timedelta(hours=max_age_hours):
                errors.append(
                    f"承認ファイルが古すぎます（{age.total_seconds()/3600:.1f}時間経過）。\n"
                    f"  最大有効期間: {max_age_hours}時間。再度承認してください。"
                )
        except ValueError:
            errors.append(f"approved_at の日時フォーマットが不正です: {approved_at_str}")

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
        print(f"\n[DRY-RUN] 実際の提出はスキップします。承認ゲートは通過しました。")
        return True

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(f"[OK] 提出成功")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"[ERROR] 提出失敗 (exit code {result.returncode})")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("ERROR: kaggle CLI が見つかりません。pip install kaggle", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("ERROR: kaggle コマンドがタイムアウトしました。", file=sys.stderr)
        return False


def append_event(event: dict):
    line = json.dumps(event, ensure_ascii=False)
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def archive_submission(approval: dict):
    src = ROOT / approval["submission_file"]
    submitted_dir = ROOT / "submissions" / "submitted"
    submitted_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = submitted_dir / f"exp_{approval['exp_id']}_{ts}_{src.name}"
    import shutil
    shutil.copy2(src, dst)
    print(f"[OK] submission をアーカイブ: {dst}")


def main():
    args = parse_args()

    print(f"\n{'='*58}")
    print(f" BirdCLEF+ 2026 — Kaggle 提出ゲート（多段承認チェック）")
    print(f"{'='*58}")

    approval_path = Path(args.approval_file)
    approval = load_approval(approval_path)

    print(f"\n--- 承認ファイル ---")
    for k, v in approval.items():
        print(f"  {k}: {v}")

    print(f"\n--- 承認ゲートチェック ---")
    errors = validate_approval(approval, args.max_age_hours)

    if errors:
        print(f"\n[BLOCKED] {len(errors)}件の検証エラー:")
        for i, e in enumerate(errors, 1):
            print(f"\n  {i}. {e}")
        sys.exit(1)

    print(f"  ✓ allow_submit: true")
    print(f"  ✓ 必須フィールド全て存在")
    print(f"  ✓ submission_csv_sha256 一致")
    print(f"  ✓ 承認日時有効期間内")
    print(f"\n[OK] 全ての承認ゲートを通過しました")

    message = args.message or approval.get("reason", f"exp_{approval['exp_id']}")
    success = run_kaggle_submit(
        competition=args.competition,
        kernel=str(approval["notebook_kernel"]),
        version=int(approval["notebook_version"]),
        sub_file=str(ROOT / approval["submission_file"]),
        message=message,
        dry_run=args.dry_run,
    )

    if success and not args.dry_run:
        sub_path = ROOT / approval["submission_file"]
        ts = datetime.now(timezone.utc).isoformat()
        event = {
            "ts": ts,
            "event": "submitted",
            "exp_id": approval["exp_id"],
            "competition": args.competition,
            "kernel": approval["notebook_kernel"],
            "version": approval["notebook_version"],
            "submission_file": approval["submission_file"],
            "submission_csv_sha256": approval["submission_csv_sha256"],
            "approved_by": approval["approved_by"],
            "reason": approval.get("reason", ""),
            "expected_public_lb": approval.get("expected_public_lb"),
        }
        append_event(event)
        archive_submission(approval)

        print(f"\n次のステップ:")
        print(f"  LBスコアを確認したら:")
        print(f"  python scripts/ingest_lb_result.py --exp-id {approval['exp_id']} --public-lb <score>")

    elif not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
