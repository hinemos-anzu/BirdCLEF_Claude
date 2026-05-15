#!/usr/bin/env python3
"""
submission.csv の品質を検査するスクリプト。
Kaggle提出前の必須チェック。pandasを使用。

使用例:
    # 基本チェック（sample_submissionなし）
    python scripts/validate_submission.py \
        --submission submissions/candidates/submission_sed.csv

    # フルチェック（sample_submission必須）
    python scripts/validate_submission.py \
        --sample data/sample_submission.csv \
        --submission submissions/candidates/submission_sed.csv

    # 厳格モード（row_id順序も検証）
    python scripts/validate_submission.py \
        --sample data/sample_submission.csv \
        --submission submissions/candidates/submission_sed.csv \
        --strict-row-order

    # Kaggle notebook内での使用（パス固定）
    python scripts/validate_submission.py \
        --sample /kaggle/input/birdclef-2026/sample_submission.csv \
        --submission /kaggle/working/submission.csv
"""

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="submission.csv の品質検査（Kaggle提出前必須）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--submission", required=True, help="検査するsubmission.csvのパス")
    parser.add_argument("--sample", default=None,
                        help="sample_submission.csvのパス（列順・行数検証に必須）")
    parser.add_argument("--strict-row-order", action="store_true",
                        help="row_id の順序まで一致を要求する")
    parser.add_argument("--score-min", type=float, default=0.0,
                        help="スコアの最小値 (default: 0.0)")
    parser.add_argument("--score-max", type=float, default=1.0,
                        help="スコアの最大値 (default: 1.0)")
    parser.add_argument("--quiet", action="store_true", help="エラーのみ表示")
    parser.add_argument("--allow-nonstandard-class-count", action="store_true",
                        help="クラス列数が標準(234)と異なる場合もERRORにしない（合成データ検証用）")
    return parser.parse_args()


def check_pass(name: str, ok: bool, detail: str = "", quiet: bool = False) -> bool:
    status = "✓ PASS" if ok else "✗ FAIL"
    if not quiet or not ok:
        print(f"  [{status}] {name}{': ' + detail if detail else ''}")
    return ok


def main():
    args = parse_args()

    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas が必要です。pip install pandas", file=sys.stderr)
        sys.exit(1)

    sub_path = Path(args.submission)
    if not sub_path.exists():
        print(f"ERROR: ファイルが見つかりません: {sub_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*55}")
    print(f"Submission 品質検査")
    print(f"{'='*55}")
    print(f"対象: {sub_path}")

    # 読み込み
    try:
        sub = pd.read_csv(sub_path)
    except Exception as e:
        print(f"ERROR: CSVの読み込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    sample = None
    if args.sample:
        sample_path = Path(args.sample)
        if not sample_path.exists():
            print(f"ERROR: sample_submission が見つかりません: {sample_path}", file=sys.stderr)
            sys.exit(1)
        try:
            sample = pd.read_csv(sample_path)
        except Exception as e:
            print(f"ERROR: sample_submission の読み込みに失敗しました: {e}", file=sys.stderr)
            sys.exit(1)

    all_pass = True

    print(f"\n--- 基本情報 ---")
    print(f"  行数: {len(sub):,}")
    print(f"  列数: {len(sub.columns)}")
    print(f"  列名: {list(sub.columns)}")

    print(f"\n--- 検査結果 ---")

    # 1. ファイルが空でないか
    ok = len(sub) > 0
    all_pass &= check_pass("空でないこと", ok, f"行数={len(sub)}", args.quiet)

    # 2. 列数・列順の確認
    if sample is not None:
        ok = list(sub.columns) == list(sample.columns)
        detail = "" if ok else f"expected={list(sample.columns)[:4]}..., got={list(sub.columns)[:4]}..."
        all_pass &= check_pass("列順がsample_submissionと一致", ok, detail, args.quiet)

        # 3. 行数の確認
        ok = len(sub) == len(sample)
        detail = "" if ok else f"expected={len(sample):,}, got={len(sub):,}"
        all_pass &= check_pass("行数がsample_submissionと一致", ok, detail, args.quiet)

    # クラス列数チェック（BirdCLEF 2026標準: 234種）
    # sample_submission がある場合はそちらから期待列数を取得、なければ 234 を使用
    if sample is not None:
        expected_class_count = len(sample.columns) - 1  # row_id 以外
    else:
        expected_class_count = 234
    score_cols_preview = [c for c in sub.columns if c not in ("row_id", "filename", "file_id", "id")]
    actual_class_count = len(score_cols_preview)
    if actual_class_count != expected_class_count:
        detail = f"期待={expected_class_count}, 実際={actual_class_count}"
        if args.allow_nonstandard_class_count:
            if not args.quiet:
                print(f"  [WARN] クラス列数不一致（--allow-nonstandard-class-count で許可）: {detail}")
        else:
            print(f"  [ERROR] クラス列数が標準({expected_class_count})と異なります: {detail}")
            print(f"          合成データ等で意図的に列数が異なる場合は --allow-nonstandard-class-count を使用してください。")
            all_pass = False

    # ID列の特定
    id_col = None
    for c in ("row_id", "filename", "file_id", "id"):
        if c in sub.columns:
            id_col = c
            break

    if id_col is None:
        id_col = sub.columns[0]
        print(f"  INFO: ID列を推定: {id_col}")

    # 4. IDの重複チェック
    dup_count = sub[id_col].duplicated().sum()
    ok = dup_count == 0
    all_pass &= check_pass("IDに重複なし", ok, f"重複数={dup_count}", args.quiet)

    # 5. ID順序チェック（strict_row_orderが指定された場合）
    if sample is not None and args.strict_row_order:
        ok = list(sub[id_col]) == list(sample[id_col])
        all_pass &= check_pass("row_idの順序が一致", ok, quiet=args.quiet)

    # スコア列の特定
    score_cols = [c for c in sub.columns if c != id_col]
    if not score_cols:
        print("ERROR: スコア列が見つかりません", file=sys.stderr)
        sys.exit(1)

    # スコア列を数値に変換
    score_df = sub[score_cols].apply(pd.to_numeric, errors="coerce")

    # 6. NaN チェック
    nan_count = score_df.isna().sum().sum()
    ok = nan_count == 0
    all_pass &= check_pass("NaN値がゼロ", ok, f"NaN数={nan_count:,}", args.quiet)

    # 7. Inf チェック
    import numpy as np
    inf_count = np.isinf(score_df.values).sum()
    ok = int(inf_count) == 0
    all_pass &= check_pass("Inf値がゼロ", ok, f"Inf数={inf_count:,}", args.quiet)

    # 8. スコア範囲チェック
    valid_scores = score_df.values[~np.isnan(score_df.values) & ~np.isinf(score_df.values)]
    if len(valid_scores) > 0:
        score_min_actual = float(valid_scores.min())
        score_max_actual = float(valid_scores.max())
        out_of_range = ((valid_scores < args.score_min) | (valid_scores > args.score_max)).sum()
        ok = int(out_of_range) == 0
        detail = (f"実際の範囲=[{score_min_actual:.4f}, {score_max_actual:.4f}]"
                  + (f", 範囲外={out_of_range:,}件" if not ok else ""))
        all_pass &= check_pass(f"スコアが[{args.score_min}, {args.score_max}]の範囲内", ok, detail, args.quiet)

    # 9. スコア分布の確認（情報のみ）
    if not args.quiet and len(valid_scores) > 0:
        print(f"\n--- スコア分布（参考） ---")
        print(f"  min : {float(valid_scores.min()):.4f}")
        print(f"  max : {float(valid_scores.max()):.4f}")
        print(f"  mean: {float(valid_scores.mean()):.4f}")
        print(f"  std : {float(valid_scores.std()):.4f}")
        # ゼロスコアが多すぎる警告
        zero_ratio = (valid_scores == 0).mean()
        if zero_ratio > 0.95:
            print(f"  WARNING: スコアの {zero_ratio:.1%} がゼロです。モデルが正常に動いているか確認してください。")

    # 最終判定
    print(f"\n{'='*55}")
    if all_pass:
        print(f"結果: ✓ 全チェック PASS — 提出可能")
        print(f"{'='*55}\n")
        sys.exit(0)
    else:
        print(f"結果: ✗ チェック失敗 — 提出前に修正が必要")
        print(f"{'='*55}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
