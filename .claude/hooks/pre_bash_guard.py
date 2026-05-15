#!/usr/bin/env python3
"""
PreToolUse hook: Bash コマンドの破壊的操作を防ぐ。

保護対象:
  - logs/        : 実験ログ（上書き・削除禁止）
  - reports/     : レポート（上書き・削除禁止）
  - submissions/submitted/ : 提出済み（上書き・削除禁止）
  - knowledge/   : 知識ベース（直接削除禁止）
  - experiments/events.jsonl : イベントログ（上書き禁止）
  - experiments/registry.csv : レジストリ（上書き禁止 ※追記はOK）

阻止するパターン:
  - rm, rm -rf  保護対象パスへの削除
  - > (上書きリダイレクト) 保護対象への上書き
  - mv           保護対象の外部への移動
  - submit_code_competition.py --approval-file なしの実行
"""

import json
import re
import sys


PROTECTED_PATTERNS = [
    r"logs/(?!\.gitkeep)",
    r"reports/experiment/(?!template\.md)",
    r"reports/master/",
    r"submissions/submitted/",
    r"experiments/events\.jsonl",
]

OVERWRITE_PROTECTED = [
    r"experiments/registry\.csv",
    r"knowledge/",
]

DESTRUCTIVE_OPS = [
    r"\brm\s",
    r"\brm\s+-[rf]+",
    r">\s*(?!>)",   # > だが >> ではない（上書きリダイレクト）
]


def is_destructive_on_protected(command: str) -> tuple[bool, str]:
    """コマンドが保護対象に対して破壊的操作をしているか判定する。"""
    # submit_code_competition.py の承認ゲートチェック
    if "submit_code_competition.py" in command:
        if "--approval-file" not in command:
            return True, (
                "submit_code_competition.py には --approval-file が必須です。\n"
                "先に submissions/approved/exp_XXXX_approval.yaml を作成してください。"
            )

    # 破壊的操作のパターンを確認
    has_destructive = any(re.search(p, command) for p in DESTRUCTIVE_OPS)
    if not has_destructive:
        return False, ""

    # 保護対象パスへの操作を確認
    for pattern in PROTECTED_PATTERNS:
        if re.search(pattern, command):
            return True, (
                f"保護対象パスへの破壊的操作を検出しました。\n"
                f"パターン: {pattern}\n"
                f"コマンド: {command[:100]}\n\n"
                f"logs/, reports/experiment/, submissions/submitted/,\n"
                f"experiments/events.jsonl は上書き・削除禁止です。"
            )

    # 上書きリダイレクト（>）のチェック（追記 >> はOK）
    if re.search(r">\s*(?!>)", command):
        for pattern in OVERWRITE_PROTECTED:
            if re.search(pattern, command):
                return True, (
                    f"保護対象ファイルへの上書きリダイレクトを検出しました。\n"
                    f"パターン: {pattern}\n"
                    f"コマンド: {command[:100]}\n\n"
                    f"追記（>>）は使用可能ですが、上書き（>）は禁止です。"
                )

    return False, ""


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    blocked, reason = is_destructive_on_protected(command)
    if blocked:
        # exit code 2 = block with feedback
        print(f"🚫 [GUARD] 操作をブロックしました:\n\n{reason}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
