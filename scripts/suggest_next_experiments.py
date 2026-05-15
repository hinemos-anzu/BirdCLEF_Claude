#!/usr/bin/env python3
"""
knowledge/ ディレクトリを読んで次の実験候補を提案するスクリプト。
failed_methods.md / knowledge/failed_methods/ に記載済みの手法は提案しない。

使用例:
    python scripts/suggest_next_experiments.py
    python scripts/suggest_next_experiments.py --top-k 10 --exclude-failed
    python scripts/suggest_next_experiments.py --category augmentation
    python scripts/suggest_next_experiments.py --register
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent

# 実験候補テンプレート（知見が増えるにつれて手動・自動で拡張）
EXPERIMENT_TEMPLATES = [
    {
        "name": "sed_baseline",
        "hypothesis": "SED (Sound Event Detection) アーキテクチャでベースラインを確立する",
        "variable": "model_arch",
        "category": "architecture",
        "priority": 10,
        "requires": [],
        "conflicts": [],  # failed_methods.md のキーワード
        "rationale": "BirdCLEFではSEDが有効とされる。まず性能を測る。",
    },
    {
        "name": "mixup_augmentation",
        "hypothesis": "Mixup augmentationでモデルの汎化性能を向上させる",
        "variable": "augmentation_mixup",
        "category": "augmentation",
        "priority": 8,
        "requires": ["sed_baseline"],
        "conflicts": ["mixup"],
        "rationale": "音声分類でMixupは定番の改善手法。",
    },
    {
        "name": "specaugment",
        "hypothesis": "SpecAugmentでtemporal/frequencyマスキングにより汎化を改善",
        "variable": "augmentation_specaugment",
        "category": "augmentation",
        "priority": 8,
        "requires": ["sed_baseline"],
        "conflicts": ["specaugment"],
        "rationale": "音声タスクでspecaugmentは効果的。",
    },
    {
        "name": "longer_duration",
        "hypothesis": "入力音声を5秒→10秒に延長してコンテキストを増やす",
        "variable": "input_duration_sec",
        "category": "input",
        "priority": 7,
        "requires": ["sed_baseline"],
        "conflicts": ["duration"],
        "rationale": "長い音声は鳥の鳴き声の文脈を捉えやすい。",
    },
    {
        "name": "efficientnet_b3",
        "hypothesis": "EfficientNet-B3に変更してモデル容量を増やす",
        "variable": "backbone",
        "category": "architecture",
        "priority": 7,
        "requires": ["sed_baseline"],
        "conflicts": ["efficientnet_b3"],
        "rationale": "B0→B3でパラメータ増加。容量不足の可能性あり。",
    },
    {
        "name": "label_smoothing",
        "hypothesis": "Label smoothing (0.05) で過学習を抑制する",
        "variable": "label_smoothing",
        "category": "training",
        "priority": 6,
        "requires": ["sed_baseline"],
        "conflicts": ["label_smooth"],
        "rationale": "ソフトラベルで汎化改善が期待できる。",
    },
    {
        "name": "blend_sed_protossm_50_50",
        "hypothesis": "SEDとProtoSSMのsubmissionを50/50でブレンドする",
        "variable": "ensemble_weight",
        "category": "ensemble",
        "priority": 9,
        "requires": ["sed_baseline"],
        "conflicts": [],
        "rationale": "多様なアーキテクチャのアンサンブルはLBを改善しやすい。",
    },
    {
        "name": "cosine_annealing_lr",
        "hypothesis": "CosineAnnealingLRでより良い収束を狙う",
        "variable": "lr_scheduler",
        "category": "training",
        "priority": 6,
        "requires": ["sed_baseline"],
        "conflicts": ["cosine"],
        "rationale": "学習率スケジューラの変更は低コストで効果的。",
    },
    {
        "name": "secondary_labels",
        "hypothesis": "secondary_labels をソフトラベルとして学習に利用する",
        "variable": "use_secondary_labels",
        "category": "data",
        "priority": 7,
        "requires": ["sed_baseline"],
        "conflicts": ["secondary"],
        "rationale": "BirdCLEFのsecondary_labelsは見落とされがちだが有効。",
    },
    {
        "name": "nocall_hard_negative",
        "hypothesis": "nocall（鳥なし）サンプルをhard negativeとして追加学習",
        "variable": "nocall_sampling_rate",
        "category": "data",
        "priority": 7,
        "requires": ["sed_baseline"],
        "conflicts": ["nocall"],
        "rationale": "hidden testにはnocallが多い可能性がある。",
    },
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="knowledge/ を読んで次の実験候補を提案する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--top-k", type=int, default=5, help="提案する実験の最大数 (default: 5)")
    parser.add_argument("--category", default=None,
                        help="フィルタするカテゴリ (architecture/augmentation/ensemble/training/data/input)")
    parser.add_argument("--exclude-failed", action="store_true",
                        help="failed_methods に記載済みの手法を厳格に除外する（デフォルトでも除外するが、より厳格に）")
    parser.add_argument("--register", action="store_true", help="提案をinit_experiment.pyで登録するモード")
    parser.add_argument("--all", action="store_true", help="フィルタなしで全候補を表示")
    return parser.parse_args()


def load_failed_methods() -> set[str]:
    """failed_methods.md と knowledge/failed_methods/ からキーワードを抽出する。"""
    keywords = set()

    # 単一ファイル版
    path = ROOT / "knowledge" / "failed_methods.md"
    if path.exists():
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if any(marker in line for marker in ("**再試行禁止条件**", "**手法**", "### [FAIL")):
                words = re.findall(r"\w+", line.lower())
                keywords.update(words)

    # versioned snapshot ディレクトリ版
    snap_dir = ROOT / "knowledge" / "failed_methods"
    if snap_dir.exists():
        for snap_file in snap_dir.glob("*.md"):
            content = snap_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                words = re.findall(r"\w+", line.lower())
                keywords.update(words)

    return keywords


def load_completed_experiments() -> list[str]:
    """registry.csv から完了済み実験の名前リストを返す。"""
    path = ROOT / "experiments" / "registry.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r["name"] for r in rows if r.get("status") in ("completed", "running")]


def load_planned_experiments() -> list[str]:
    path = ROOT / "experiments" / "registry.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r["name"] for r in rows if r.get("status") == "planned"]


def filter_candidates(
    templates: list[dict],
    failed_keywords: set[str],
    completed: list[str],
    planned: list[str],
    category: str | None,
    show_all: bool,
) -> list[dict]:
    results = []
    for t in templates:
        # カテゴリフィルタ
        if category and t["category"] != category:
            continue

        # 完了済み・計画済みはスキップ
        if not show_all:
            if t["name"] in completed:
                t["_skip_reason"] = "完了済み"
                continue
            if t["name"] in planned:
                t["_skip_reason"] = "計画済み"
                continue

        # failed_methods のキーワードと衝突チェック
        blocked = False
        for conflict_kw in t["conflicts"]:
            if conflict_kw.lower() in failed_keywords:
                t["_skip_reason"] = f"failed_methods に {conflict_kw} が記録済み"
                blocked = True
                break
        if blocked and not show_all:
            continue

        # 前提実験のチェック
        missing_requires = [r for r in t["requires"] if r not in completed]
        if missing_requires and not show_all:
            t["_skip_reason"] = f"前提実験未完了: {', '.join(missing_requires)}"
            # 警告のみ（priorityを下げて追加）
            t["priority"] = max(0, t["priority"] - 3)
            t["_warning"] = f"⚠ 前提実験未完了: {', '.join(missing_requires)}"

        results.append(t)

    results.sort(key=lambda x: -x["priority"])
    return results


def get_next_exp_id() -> str:
    path = ROOT / "experiments" / "registry.csv"
    if not path.exists():
        return "0001"
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids = []
    for r in rows:
        try:
            ids.append(int(r["exp_id"]))
        except ValueError:
            pass
    return f"{max(ids) + 1:04d}" if ids else "0001"


def register_experiment(exp: dict):
    path = ROOT / "experiments" / "registry.csv"
    exp_id = get_next_exp_id()
    date_str = datetime.now().strftime("%Y-%m-%d")

    row = {
        "exp_id": exp_id,
        "name": exp["name"],
        "hypothesis": exp["hypothesis"],
        "variable_changed": exp["variable"],
        "baseline_exp_id": "none",
        "status": "planned",
        "cv_score": "",
        "lb_score": "",
        "date": date_str,
        "notes": exp["rationale"],
    }

    with open(path, newline="", encoding="utf-8") as f:
        existing = list(csv.DictReader(f))

    fieldnames = list(existing[0].keys()) if existing else list(row.keys())
    existing.append(row)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing)

    print(f"[OK] exp_{exp_id} ({exp['name']}) をregistry.csvに登録しました")
    return exp_id


def main():
    args = parse_args()

    failed_keywords = load_failed_methods()
    completed = load_completed_experiments()
    planned = load_planned_experiments()

    candidates = filter_candidates(
        EXPERIMENT_TEMPLATES,
        failed_keywords,
        completed,
        planned,
        args.category,
        args.all,
    )

    top_k = len(candidates) if args.all else args.top_k
    display = candidates[:top_k]

    print(f"\n{'='*60}")
    print(f"BirdCLEF+ 2026 — 次実験の提案")
    print(f"{'='*60}")
    print(f"完了済み実験: {len(completed)}件 | 計画中: {len(planned)}件")
    print(f"失敗記録キーワード: {len(failed_keywords)}件")
    print(f"{'='*60}\n")

    if not display:
        print("提案できる実験候補がありません。")
        print("knowledge/failed_methods.md や registry.csv を確認してください。")
        return

    for i, exp in enumerate(display, 1):
        warning = exp.get("_warning", "")
        print(f"[{i}] {exp['name']} (優先度: {exp['priority']}/10) [{exp['category']}]")
        print(f"     仮説: {exp['hypothesis']}")
        print(f"     変更変数: {exp['variable']}")
        print(f"     根拠: {exp['rationale']}")
        if warning:
            print(f"     {warning}")
        print()

    if args.register:
        print("\n登録する実験番号を入力してください (複数可: 1,2,3 / all / q=キャンセル): ", end="")
        choice = input().strip()

        if choice.lower() == "q":
            print("キャンセルしました。")
            return

        if choice.lower() == "all":
            indices = list(range(len(display)))
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
            except ValueError:
                print("ERROR: 無効な入力です", file=sys.stderr)
                sys.exit(1)

        for idx in indices:
            if 0 <= idx < len(display):
                exp = display[idx]
                import subprocess
                cmd = [
                    sys.executable, "scripts/init_experiment.py",
                    "--name", exp["name"],
                    "--hypothesis", exp["hypothesis"],
                    "--one-variable", exp["variable"],
                    "--notes", exp["rationale"],
                ]
                print(f"\n実行: {' '.join(cmd)}")
                subprocess.run(cmd)
            else:
                print(f"WARNING: {idx+1} は無効な番号です")

        print("\n次のステップ:")
        print("  configs/experiments/exp_XXXX.yaml を作成して学習設定を記述してください")
    else:
        print(f"実験をregistryに登録するには: python scripts/suggest_next_experiments.py --register")


if __name__ == "__main__":
    main()
