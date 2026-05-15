#!/usr/bin/env python3
"""
Kaggle notebook の本番互換性を静的チェックするスクリプト。
Docker不要で実行可能。Pythonファイルを静的解析して問題を検出する。

チェック項目:
  1. /kaggle/input を参照しているか（データ参照の確認）
  2. /kaggle/working/submission.csv に出力しているか
  3. sample_submission.csv から列順を取得しているか
  4. インターネット依存コードがないか（requests/urllib/wget/curl）
  5. GPU必須コード (.cuda() / device="cuda") がないか
  6. train fallback パターンがないか

使用例:
    # Kaggle notebookを検査
    python scripts/check_kaggle_parity.py \\
        --target kaggle_notebook/notebook.ipynb

    # Pythonスクリプトを検査
    python scripts/check_kaggle_parity.py \\
        --target scripts/run_local_submission.py

    # ディレクトリ全体を検査
    python scripts/check_kaggle_parity.py \\
        --target kaggle_notebook/ \\
        --recursive
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Kaggle notebook の本番互換性を静的チェック",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--target", required=True,
                        help="検査対象ファイルまたはディレクトリ")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="ディレクトリを再帰的に検査")
    parser.add_argument("--strict", action="store_true",
                        help="警告もエラーとして扱う")
    parser.add_argument("--output", default=None,
                        help="結果をMarkdownファイルに保存")
    return parser.parse_args()


def extract_code_from_notebook(path: Path) -> str:
    """Jupyter Notebookからコードセルを抽出する。"""
    try:
        with open(path, encoding="utf-8") as f:
            nb = json.load(f)
        cells = nb.get("cells", [])
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        lines = []
        for cell in code_cells:
            source = cell.get("source", [])
            if isinstance(source, list):
                lines.extend(source)
            else:
                lines.append(source)
        return "\n".join(lines)
    except Exception as e:
        return f"# ERROR reading notebook: {e}"


def get_source_code(path: Path) -> str:
    """ファイルからソースコードを取得する。"""
    if path.suffix == ".ipynb":
        return extract_code_from_notebook(path)
    else:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"# ERROR: {e}"


CHECKS = [
    {
        "id": "C01",
        "name": "/kaggle/input 参照",
        "severity": "INFO",
        "patterns": [r"/kaggle/input"],
        "mode": "must_have",
        "message": "/kaggle/input を参照していません。本番ではデータはここにあります。",
    },
    {
        "id": "C02",
        "name": "/kaggle/working/submission.csv 出力",
        "severity": "ERROR",
        "patterns": [r"/kaggle/working/submission\.csv"],
        "mode": "must_have",
        "message": "/kaggle/working/submission.csv への出力が見当たりません。Kaggle本番ではここに生成する必要があります。",
    },
    {
        "id": "C03",
        "name": "sample_submission.csv から列順を取得",
        "severity": "WARN",
        "patterns": [r"sample_submission"],
        "mode": "must_have",
        "message": "sample_submission.csv の参照が見当たりません。列順の取得に使っているか確認してください。",
    },
    {
        "id": "C04",
        "name": "インターネット依存コード禁止",
        "severity": "ERROR",
        "patterns": [
            r"\brequests\.get\b",
            r"\burllib\.request\b",
            r"subprocess.*wget",
            r"subprocess.*curl",
            r"gdown\.",
            r"huggingface_hub\.hf_hub_download",
        ],
        "mode": "must_not_have",
        "message": "インターネットアクセスが必要なコードを検出しました。提出環境は Internet OFF です。",
    },
    {
        "id": "C05",
        "name": "GPU必須コード禁止（CPU推論確認）",
        "severity": "WARN",
        "patterns": [
            r'\.cuda\(\)',
            r'device\s*=\s*["\']cuda["\']',
            r'torch\.cuda\.is_available\(\)\s*else\s*["\']cpu["\']',  # これはOK（後述）
        ],
        "mode": "must_not_have",
        "message": "GPU必須コードを検出しました。BirdCLEF提出はCPUのみです。device='cuda'ではなく自動検出か'cpu'固定を推奨します。",
        "exceptions": [
            r'torch\.cuda\.is_available\(\)\s*else\s*["\']cpu["\']',
            r'if\s+torch\.cuda\.is_available',
        ],
    },
    {
        "id": "C06",
        "name": "学習データへのtrain fallback禁止",
        "severity": "WARN",
        "patterns": [
            r"train_audio",
            r"train_metadata",
            r"/kaggle/input/birdclef-2026/train",
        ],
        "mode": "must_not_have",
        "message": "学習データへの参照を検出しました。提出Notebookは推論のみで、学習データに依存しないことを確認してください。",
    },
    {
        "id": "C07",
        "name": "90分制限の意識（推論時間）",
        "severity": "INFO",
        "patterns": [
            r"time\.time\(\)",
            r"tqdm",
            r"timeout",
        ],
        "mode": "should_have",
        "message": "推論時間の計測コードが見当たりません。CPU 90分制限内に完了することを確認してください。",
    },
]


def check_file(code: str, file_path: Path) -> list[dict]:
    results = []

    for check in CHECKS:
        found_patterns = []
        for pattern in check["patterns"]:
            matches = re.findall(pattern, code)
            if matches:
                found_patterns.append(pattern)

        # 例外パターンを除外（C05）
        exceptions = check.get("exceptions", [])
        if exceptions:
            exception_found = any(re.search(ep, code) for ep in exceptions)
            if exception_found:
                # 例外パターンが含まれている場合は除外
                found_patterns = [p for p in found_patterns
                                  if not any(re.search(ep, code) for ep in exceptions)]

        mode = check["mode"]
        passed = True
        detail = ""

        if mode == "must_have":
            passed = len(found_patterns) > 0
            if not passed:
                detail = check["message"]
        elif mode == "must_not_have":
            passed = len(found_patterns) == 0
            if not passed:
                detail = f"{check['message']}\n    検出パターン: {found_patterns}"
        elif mode == "should_have":
            passed = len(found_patterns) > 0
            if not passed:
                detail = check["message"]
            # should_have は INFO 扱い（エラーにしない）

        results.append({
            "id": check["id"],
            "name": check["name"],
            "severity": check["severity"],
            "passed": passed,
            "detail": detail,
            "file": str(file_path.relative_to(ROOT) if file_path.is_relative_to(ROOT) else file_path),
        })

    return results


def format_results(all_results: list[dict], strict: bool) -> tuple[str, bool]:
    errors = [r for r in all_results if not r["passed"] and r["severity"] == "ERROR"]
    warnings = [r for r in all_results if not r["passed"] and r["severity"] == "WARN"]
    infos = [r for r in all_results if not r["passed"] and r["severity"] == "INFO"]

    overall_pass = len(errors) == 0 and (not strict or len(warnings) == 0)

    lines = ["# Kaggle Parity Check 結果\n"]
    lines.append(f"{'='*55}\n")

    status = "✓ PASS" if overall_pass else "✗ FAIL"
    lines.append(f"総合判定: {status}\n")
    lines.append(f"ERROR: {len(errors)}件 | WARN: {len(warnings)}件 | INFO: {len(infos)}件\n")
    lines.append(f"{'='*55}\n\n")

    if errors:
        lines.append("## ❌ ERROR（提出前に必ず修正）\n\n")
        for r in errors:
            lines.append(f"### [{r['id']}] {r['name']}\n")
            lines.append(f"ファイル: `{r['file']}`\n\n")
            lines.append(f"{r['detail']}\n\n")

    if warnings:
        lines.append("## ⚠ WARN（確認推奨）\n\n")
        for r in warnings:
            lines.append(f"### [{r['id']}] {r['name']}\n")
            lines.append(f"ファイル: `{r['file']}`\n\n")
            lines.append(f"{r['detail']}\n\n")

    if infos:
        lines.append("## ℹ INFO（参考）\n\n")
        for r in infos:
            lines.append(f"- [{r['id']}] {r['name']}: {r['file']}\n")
        lines.append("\n")

    passing = [r for r in all_results if r["passed"]]
    if passing:
        lines.append("## ✓ 通過したチェック\n\n")
        for r in passing:
            lines.append(f"- [{r['id']}] {r['name']}\n")

    return "".join(lines), overall_pass


def collect_files(target: Path, recursive: bool) -> list[Path]:
    if target.is_file():
        return [target]
    exts = {".py", ".ipynb"}
    if recursive:
        return [f for f in target.rglob("*") if f.suffix in exts]
    else:
        return [f for f in target.iterdir() if f.suffix in exts]


def main():
    args = parse_args()
    target = Path(args.target)

    if not target.exists():
        print(f"ERROR: 対象が見つかりません: {target}", file=sys.stderr)
        sys.exit(1)

    files = collect_files(target, args.recursive)
    if not files:
        print(f"ERROR: 検査対象ファイルが見つかりません: {target}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Kaggle Parity Check ===")
    print(f"対象: {target} ({len(files)}ファイル)")

    all_results = []
    for file_path in files:
        code = get_source_code(file_path)
        results = check_file(code, file_path)
        all_results.extend(results)

    report, overall_pass = format_results(all_results, args.strict)
    print(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"[OK] 結果を保存: {out_path}")

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
