#!/usr/bin/env python3
"""
2つのsubmission.csvをブレンドし、品質監査レポートを生成するスクリプト。
BirdCLEF+ 2026 Internet OFF提出環境を意識してpandas以外の標準ライブラリで動作する。

使用例:
    # 品質監査のみ（ブレンドなし）
    python scripts/run_blend_ab.py \
        --submission-a submissions/candidates/submission_sed.csv \
        --sample-submission data/sample_submission.csv \
        --audit-only

    # 50/50ブレンド
    python scripts/run_blend_ab.py \
        --submission-a submissions/candidates/submission_sed.csv \
        --submission-b submissions/candidates/submission_protossm.csv \
        --sample-submission data/sample_submission.csv \
        --weight-a 0.5 --weight-b 0.5 \
        --output submissions/candidates/submission_blend_50_50.csv

    # 重み比率スイープ（0.1刻みで全ブレンド生成）
    python scripts/run_blend_ab.py \
        --submission-a submissions/candidates/submission_sed.csv \
        --submission-b submissions/candidates/submission_protossm.csv \
        --sample-submission data/sample_submission.csv \
        --sweep

    # 3ファイルブレンド
    python scripts/run_blend_ab.py \
        --submission-a submissions/candidates/sub_a.csv \
        --submission-b submissions/candidates/sub_b.csv \
        --submission-c submissions/candidates/sub_c.csv \
        --weight-a 0.4 --weight-b 0.4 --weight-c 0.2 \
        --output submissions/candidates/submission_blend_3way.csv
"""

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="submission.csv のブレンドと品質監査",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--submission-a", required=True, help="submission A のパス")
    parser.add_argument("--submission-b", default=None, help="submission B のパス（省略可）")
    parser.add_argument("--submission-c", default=None, help="submission C のパス（3wayブレンド用）")
    parser.add_argument("--weight-a", type=float, default=1.0, help="submission A の重み (default: 1.0)")
    parser.add_argument("--weight-b", type=float, default=0.0, help="submission B の重み (default: 0.0)")
    parser.add_argument("--weight-c", type=float, default=0.0, help="submission C の重み (default: 0.0)")
    parser.add_argument("--sample-submission", default=None,
                        help="sample_submission.csv のパス（列順・行数チェック用）")
    parser.add_argument("--output", default=None, help="出力先のパス（省略時は表示のみ）")
    parser.add_argument("--sweep", action="store_true",
                        help="0.0〜1.0 (0.1刻み) でブレンド比率をスイープして全ファイルを生成")
    parser.add_argument("--sweep-step", type=float, default=0.1, help="スイープのステップ幅 (default: 0.1)")
    parser.add_argument("--audit-only", action="store_true",
                        help="ブレンドせず品質監査レポートのみ出力")
    parser.add_argument("--clip", action="store_true", default=True,
                        help="スコアを[0,1]にクリップする (default: True)")
    parser.add_argument("--no-clip", dest="clip", action="store_false",
                        help="クリップを無効化")
    return parser.parse_args()


class SubmissionData:
    def __init__(self, path: str):
        self.path = Path(path)
        self.headers: list[str] = []
        self.rows: list[dict] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            print(f"ERROR: ファイルが見つかりません: {self.path}", file=sys.stderr)
            sys.exit(1)
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.headers = list(reader.fieldnames or [])
            self.rows = list(reader)

    @property
    def score_columns(self) -> list[str]:
        return [c for c in self.headers if c not in ("row_id", "filename", "file_id", "id")]

    @property
    def id_column(self) -> str:
        for c in ("row_id", "filename", "file_id", "id"):
            if c in self.headers:
                return c
        return self.headers[0]

    def audit(self, sample: "SubmissionData | None" = None) -> dict:
        result = {
            "file": str(self.path),
            "n_rows": len(self.rows),
            "n_cols": len(self.headers),
            "headers": self.headers,
            "nan_count": 0,
            "inf_count": 0,
            "out_of_range_count": 0,
            "score_min": math.inf,
            "score_max": -math.inf,
            "errors": [],
        }

        for row in self.rows:
            for col in self.score_columns:
                val_str = row.get(col, "")
                if val_str == "" or val_str is None:
                    result["nan_count"] += 1
                    continue
                try:
                    val = float(val_str)
                except ValueError:
                    result["nan_count"] += 1
                    result["errors"].append(f"非数値: col={col}, val={val_str!r}")
                    continue

                if math.isnan(val):
                    result["nan_count"] += 1
                elif math.isinf(val):
                    result["inf_count"] += 1
                else:
                    result["score_min"] = min(result["score_min"], val)
                    result["score_max"] = max(result["score_max"], val)
                    if not (0.0 <= val <= 1.0):
                        result["out_of_range_count"] += 1

        if result["score_min"] == math.inf:
            result["score_min"] = None
        if result["score_max"] == -math.inf:
            result["score_max"] = None

        if sample is not None:
            result["col_order_match"] = self.headers == sample.headers
            result["row_count_match"] = len(self.rows) == len(sample.rows)
            if not result["col_order_match"]:
                result["errors"].append(
                    f"列順不一致: expected={sample.headers[:5]}..., got={self.headers[:5]}..."
                )
            if not result["row_count_match"]:
                result["errors"].append(
                    f"行数不一致: expected={len(sample.rows)}, got={len(self.rows)}"
                )
        else:
            result["col_order_match"] = None
            result["row_count_match"] = None

        result["ok"] = (
            result["nan_count"] == 0
            and result["inf_count"] == 0
            and result["out_of_range_count"] == 0
            and (result["col_order_match"] is not False)
            and (result["row_count_match"] is not False)
        )
        return result


def print_audit(audit: dict, label: str = ""):
    ok_str = "✓ PASS" if audit["ok"] else "✗ FAIL"
    print(f"\n--- 監査結果: {label or audit['file']} [{ok_str}] ---")
    print(f"  行数      : {audit['n_rows']}")
    print(f"  列数      : {audit['n_cols']}")
    print(f"  NaN件数   : {audit['nan_count']}")
    print(f"  Inf件数   : {audit['inf_count']}")
    print(f"  範囲外    : {audit['out_of_range_count']}")
    if audit["score_min"] is not None:
        print(f"  スコア範囲: [{audit['score_min']:.4f}, {audit['score_max']:.4f}]")
    if audit["col_order_match"] is not None:
        match_str = "一致" if audit["col_order_match"] else "不一致 ⚠"
        print(f"  列順      : {match_str}")
    if audit["row_count_match"] is not None:
        match_str = "一致" if audit["row_count_match"] else "不一致 ⚠"
        print(f"  行数一致  : {match_str}")
    if audit["errors"]:
        print(f"  エラー:")
        for e in audit["errors"][:5]:
            print(f"    - {e}")


def blend_submissions(
    subs: list[SubmissionData],
    weights: list[float],
    clip: bool,
) -> SubmissionData | None:
    if not subs:
        return None

    # 重みの正規化
    total_w = sum(weights)
    if total_w == 0:
        print("ERROR: 重みの合計が0です", file=sys.stderr)
        return None
    weights = [w / total_w for w in weights]

    base = subs[0]
    id_col = base.id_column
    score_cols = base.score_columns

    # インデックス構築
    indexed = []
    for sub in subs:
        idx = {row[id_col]: row for row in sub.rows}
        indexed.append(idx)

    blended_rows = []
    for base_row in base.rows:
        row_id = base_row[id_col]
        new_row = {id_col: row_id}

        for col in score_cols:
            blended_val = 0.0
            valid = True
            for sub_idx, w in zip(indexed, weights):
                sub_row = sub_idx.get(row_id, {})
                val_str = sub_row.get(col, "0")
                try:
                    val = float(val_str)
                    if math.isnan(val) or math.isinf(val):
                        valid = False
                        break
                    blended_val += w * val
                except (ValueError, TypeError):
                    valid = False
                    break

            if not valid:
                blended_val = 0.0

            if clip:
                blended_val = max(0.0, min(1.0, blended_val))

            new_row[col] = f"{blended_val:.6f}"

        blended_rows.append(new_row)

    # 仮のSubmissionDataを構築
    result = object.__new__(SubmissionData)
    result.path = Path("blended")
    result.headers = base.headers
    result.rows = blended_rows
    return result


def save_submission(sub: SubmissionData, output_path: Path):
    if output_path.exists():
        print(f"ERROR: {output_path} は既に存在します。上書き禁止ルールにより保存しません。", file=sys.stderr)
        ts = datetime.now().strftime("%H%M%S")
        output_path = output_path.with_stem(output_path.stem + f"_{ts}")
        print(f"       代わりに {output_path} に保存します。")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sub.headers)
        writer.writeheader()
        writer.writerows(sub.rows)

    print(f"[OK] ブレンド済みsubmissionを保存: {output_path}")
    return output_path


def run_sweep(
    sub_a: SubmissionData,
    sub_b: SubmissionData,
    sample: SubmissionData | None,
    step: float,
    clip: bool,
    base_dir: Path,
):
    print(f"\n=== スイープ開始 (step={step}) ===")
    results = []
    wa = 0.0
    while wa <= 1.0 + 1e-9:
        wb = 1.0 - wa
        wa_clamped = round(wa, 2)
        wb_clamped = round(wb, 2)

        blended = blend_submissions([sub_a, sub_b], [wa_clamped, wb_clamped], clip)
        if blended is None:
            wa += step
            continue

        audit = blended.audit(sample)
        status = "✓" if audit["ok"] else "✗"
        out_name = f"submission_blend_a{int(wa_clamped*10):02d}_b{int(wb_clamped*10):02d}.csv"
        out_path = base_dir / out_name
        saved_path = save_submission(blended, out_path)
        results.append((wa_clamped, wb_clamped, audit["ok"], saved_path))
        print(f"  {status} A={wa_clamped:.1f} / B={wb_clamped:.1f} → {out_name}")
        wa += step

    print(f"\nスイープ完了: {len(results)}ファイル生成")
    print("次のステップ: 各ファイルを確認してKaggleに手動提出してください。")


def main():
    args = parse_args()

    sub_a = SubmissionData(args.submission_a)
    sub_b = SubmissionData(args.submission_b) if args.submission_b else None
    sub_c = SubmissionData(args.submission_c) if args.submission_c else None
    sample = SubmissionData(args.sample_submission) if args.sample_submission else None

    print(f"\n=== BirdCLEF+ 2026 Submission Tool ===")
    print(f"時刻: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 監査
    audit_a = sub_a.audit(sample)
    print_audit(audit_a, "submission A")

    if sub_b:
        audit_b = sub_b.audit(sample)
        print_audit(audit_b, "submission B")

    if sub_c:
        audit_c = sub_c.audit(sample)
        print_audit(audit_c, "submission C")

    if args.audit_only:
        print("\n[audit-only モード] ブレンドをスキップします。")
        n_fails = sum(1 for a in [audit_a] + ([] if not sub_b else [audit_b]) if not a["ok"])
        if n_fails:
            print(f"WARNING: {n_fails}件の監査が失敗しました。提出前に修正してください。")
            sys.exit(1)
        else:
            print("全監査PASS。")
        return

    if args.sweep:
        if sub_b is None:
            print("ERROR: --sweep には --submission-b が必要です", file=sys.stderr)
            sys.exit(1)
        out_dir = Path(args.output).parent if args.output else ROOT / "submissions" / "candidates"
        run_sweep(sub_a, sub_b, sample, args.sweep_step, args.clip, out_dir)
        return

    # 通常ブレンド
    subs = [s for s in [sub_a, sub_b, sub_c] if s is not None]
    weights_raw = [args.weight_a, args.weight_b, args.weight_c]
    weights = weights_raw[:len(subs)]

    if len(subs) == 1:
        blended = sub_a
        print(f"\n[INFO] submission B が未指定のため、submission A をそのまま使用します。")
    else:
        total_w = sum(weights)
        norm_w = [w / total_w for w in weights]
        print(f"\n=== ブレンド設定 ===")
        labels = ["A", "B", "C"]
        for label, w, nw in zip(labels, weights, norm_w):
            print(f"  submission {label}: weight={w} (normalized={nw:.2f})")

        blended = blend_submissions(subs, weights, args.clip)
        if blended is None:
            sys.exit(1)

        blend_audit = blended.audit(sample)
        print_audit(blend_audit, "ブレンド結果")

        if not blend_audit["ok"]:
            print("\nERROR: ブレンド結果が監査を通過しませんでした。出力をスキップします。", file=sys.stderr)
            sys.exit(1)

    if args.output:
        save_submission(blended, Path(args.output))
        print("\n次のステップ:")
        print(f"  1. {args.output} を確認する")
        print(f"  2. 問題なければ手動でKaggleに提出する")
        print(f"  3. 提出後: submissions/candidates/ → submissions/submitted/ に移動")
        print(f"  4. python scripts/ingest_lb_result.py でLBスコアを記録する")
    else:
        print("\n[INFO] --output 未指定のため、ファイルは保存されません。")


if __name__ == "__main__":
    main()
