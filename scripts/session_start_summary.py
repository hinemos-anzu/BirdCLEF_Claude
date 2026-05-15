#!/usr/bin/env python3
"""SessionStart hookから呼ばれる実験状況サマリー表示スクリプト。"""

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_registry():
    path = ROOT / "experiments" / "registry.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("exp_id") != "0000"]


def load_recent_events(n: int = 5) -> list[dict]:
    path = ROOT / "experiments" / "events.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    events = []
    for line in reversed(lines[-20:]):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return events[:n]


def main():
    rows = load_registry()
    events = load_recent_events()

    completed = [r for r in rows if r.get("status") == "completed"]
    planned = [r for r in rows if r.get("status") == "planned"]
    running = [r for r in rows if r.get("status") == "running"]

    lb_scores = []
    for r in completed:
        try:
            lb_scores.append(float(r["lb_score"]))
        except (ValueError, KeyError):
            pass

    best_lb = f"{max(lb_scores):.4f}" if lb_scores else "—"

    print(f"\n{'━'*55}")
    print(f" BirdCLEF+ 2026 — 実験状況 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"{'━'*55}")
    print(f" 完了: {len(completed)}件  |  実行中: {len(running)}件  |  計画中: {len(planned)}件")
    print(f" ベストLB: {best_lb}")

    if running:
        print(f"\n 🔄 実行中の実験:")
        for r in running:
            print(f"   exp_{r['exp_id']}: {r['name']}")

    if planned:
        print(f"\n 📋 次の実験 (上位3件):")
        for r in planned[:3]:
            print(f"   exp_{r['exp_id']}: {r['name']} [{r['variable_changed']}]")

    if events:
        print(f"\n 📝 最近のイベント:")
        for e in events[:3]:
            ts = e.get("ts", "")[:16].replace("T", " ")
            print(f"   {ts} | {e.get('event')} | exp_{e.get('exp_id', '?')}")

    print(f"{'━'*55}")
    print(f" python scripts/suggest_next_experiments.py  # 次実験を提案")
    print(f" python scripts/update_master_report.py      # 知識ベース更新")
    print(f"{'━'*55}\n")


if __name__ == "__main__":
    main()
