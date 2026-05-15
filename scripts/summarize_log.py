#!/usr/bin/env python3
"""
学習ログを解析してサマリーを生成するスクリプト。
PyTorch Lightning / timm / カスタム学習ループのログ形式に対応。

使用例:
    python scripts/summarize_log.py --log logs/exp_0001_train.log --exp-id 0001
    python scripts/summarize_log.py --log logs/exp_0001_train.log --exp-id 0001 --save
    python scripts/summarize_log.py --log logs/exp_0001_train.log  # exp-id 自動推定
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="学習ログを解析してサマリーを生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--log", required=True, help="ログファイルのパス")
    parser.add_argument("--exp-id", default=None, help="実験ID (例: 0001)")
    parser.add_argument("--save", action="store_true", help="サマリーをreports/experiment/に保存")
    parser.add_argument("--format", choices=["text", "markdown"], default="markdown",
                        help="出力フォーマット")
    return parser.parse_args()


def extract_metrics(log_path: Path) -> dict:
    """ログファイルからメトリクスを抽出する。"""
    content = log_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    metrics = {
        "epochs": [],
        "train_loss": [],
        "val_loss": [],
        "val_auc": [],
        "val_acc": [],
        "errors": [],
        "warnings": [],
        "final_cv": None,
        "best_epoch": None,
        "best_val_auc": None,
        "total_time": None,
        "oom_errors": 0,
        "nan_detected": False,
    }

    # エポックごとのメトリクスを抽出
    epoch_pattern = re.compile(
        r"[Ee]poch[\s:]+(\d+).*?(?:loss|Loss)[\s:=]+([0-9.]+).*?(?:val|Val|valid).*?(?:loss|Loss)[\s:=]+([0-9.]+)",
        re.IGNORECASE,
    )
    auc_pattern = re.compile(r"(?:auc|AUC|roc_auc)[\s:=]+([0-9.]+)", re.IGNORECASE)
    cv_pattern = re.compile(r"(?:CV|OOF|mean.*?auc|fold.*?mean)[\s:=]+([0-9.]+)", re.IGNORECASE)
    time_pattern = re.compile(r"(?:total.*?time|elapsed|duration)[\s:=]+([0-9.]+\s*(?:s|sec|min|hour))", re.IGNORECASE)
    best_pattern = re.compile(r"(?:best|Best).*?(?:epoch|Epoch)[\s:=]+(\d+).*?(?:auc|AUC)[\s:=]+([0-9.]+)")

    for line in lines:
        # エラー検出
        if re.search(r"(?:Error|Exception|Traceback|CUDA out of memory)", line):
            if "CUDA out of memory" in line:
                metrics["oom_errors"] += 1
            elif "Error" in line or "Exception" in line:
                metrics["errors"].append(line[:120])

        # NaN検出
        if re.search(r"\bnan\b|\bNaN\b|\binf\b|\bInf\b", line):
            metrics["nan_detected"] = True
            metrics["warnings"].append(f"NaN/Inf detected: {line[:80]}")

        # 警告
        if re.search(r"(?:Warning|WARN)", line):
            metrics["warnings"].append(line[:100])

        # AUC
        m = auc_pattern.search(line)
        if m:
            val = float(m.group(1))
            if 0.0 <= val <= 1.0:
                metrics["val_auc"].append(val)

        # CV/OOF
        m = cv_pattern.search(line)
        if m:
            val = float(m.group(1))
            if 0.0 <= val <= 1.0:
                metrics["final_cv"] = val

        # ベストエポック
        m = best_pattern.search(line)
        if m:
            metrics["best_epoch"] = int(m.group(1))
            metrics["best_val_auc"] = float(m.group(2))

        # 総学習時間
        m = time_pattern.search(line)
        if m:
            metrics["total_time"] = m.group(1)

    # best val AUC を val_auc リストから推定
    if metrics["val_auc"] and metrics["best_val_auc"] is None:
        metrics["best_val_auc"] = max(metrics["val_auc"])

    # final_cv を val_auc リストから推定
    if metrics["final_cv"] is None and metrics["val_auc"]:
        metrics["final_cv"] = metrics["val_auc"][-1]

    return metrics


def format_summary(log_path: Path, exp_id: str | None, metrics: dict, fmt: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_name = log_path.name
    lines_count = len(log_path.read_text(encoding="utf-8", errors="replace").splitlines())

    if fmt == "markdown":
        parts = [
            f"## ログサマリー: {log_name}",
            f"",
            f"- **実験ID**: {exp_id or '不明'}",
            f"- **解析日時**: {now}",
            f"- **ログ行数**: {lines_count}",
            f"",
            f"### メトリクス",
            f"",
            f"| 項目 | 値 |",
            f"|------|-----|",
            f"| ベストval AUC | {metrics['best_val_auc']:.4f if metrics['best_val_auc'] else '—'} |",
            f"| ベストエポック | {metrics['best_epoch'] or '—'} |",
            f"| 最終CV/OOF | {metrics['final_cv']:.4f if metrics['final_cv'] else '—'} |",
            f"| 総学習時間 | {metrics['total_time'] or '—'} |",
            f"| OOMエラー数 | {metrics['oom_errors']} |",
            f"| NaN/Inf検出 | {'あり ⚠' if metrics['nan_detected'] else 'なし'} |",
            f"",
        ]

        if metrics["val_auc"]:
            auc_trend = " → ".join(f"{v:.4f}" for v in metrics["val_auc"][-5:])
            parts.append(f"### AUC推移 (最終5エポック)")
            parts.append(f"```\n{auc_trend}\n```\n")

        if metrics["errors"]:
            parts.append(f"### エラー ({len(metrics['errors'])}件)")
            for e in metrics["errors"][:5]:
                parts.append(f"- `{e}`")
            parts.append("")

        if metrics["warnings"]:
            parts.append(f"### 警告 ({len(metrics['warnings'])}件)")
            for w in metrics["warnings"][:3]:
                parts.append(f"- `{w}`")
            parts.append("")

        return "\n".join(parts)

    else:  # text
        parts = [
            f"=== ログサマリー: {log_name} ===",
            f"実験ID    : {exp_id or '不明'}",
            f"解析日時  : {now}",
            f"ベストAUC : {metrics['best_val_auc']:.4f if metrics['best_val_auc'] else '—'}",
            f"最終CV    : {metrics['final_cv']:.4f if metrics['final_cv'] else '—'}",
            f"OOMエラー : {metrics['oom_errors']}",
            f"NaN/Inf   : {'あり' if metrics['nan_detected'] else 'なし'}",
        ]
        return "\n".join(parts)


def save_summary(exp_id: str, summary: str):
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = ROOT / "reports" / "experiment" / f"exp_{exp_id}_log_summary_{date_str}.md"
    if out_path.exists():
        print(f"WARNING: {out_path} は既に存在します。上書きしません。", file=sys.stderr)
        suffix = datetime.now().strftime("%H%M%S")
        out_path = ROOT / "reports" / "experiment" / f"exp_{exp_id}_log_summary_{date_str}_{suffix}.md"
    out_path.write_text(summary, encoding="utf-8")
    print(f"[OK] サマリーを保存: {out_path}")


def main():
    args = parse_args()
    log_path = Path(args.log)

    if not log_path.exists():
        print(f"ERROR: ログファイルが見つかりません: {log_path}", file=sys.stderr)
        sys.exit(1)

    # exp_id をファイル名から推定
    exp_id = args.exp_id
    if exp_id is None:
        m = re.search(r"exp[_-](\d{4})", log_path.name)
        if m:
            exp_id = m.group(1)
            print(f"[INFO] exp_id をファイル名から推定: {exp_id}")

    print(f"ログ解析中: {log_path}")
    metrics = extract_metrics(log_path)
    summary = format_summary(log_path, exp_id, metrics, args.format)

    print(summary)

    if args.save:
        if exp_id is None:
            print("ERROR: --save には --exp-id が必要です", file=sys.stderr)
            sys.exit(1)
        save_summary(exp_id, summary)


if __name__ == "__main__":
    main()
