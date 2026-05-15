# BirdCLEF+ 2026 — Tom-style Claude Code 実験環境

BirdCLEF+ 2026 Kaggleコンペ向けの自律実験管理システム。
Tomが示したようなEDA → 実験 → ログ → レポート → 知識更新 → 次実験提案 の循環をClaude Codeで再現する。

## クイックスタート

```bash
# ヘルプ確認
python scripts/ingest_lb_result.py --help
python scripts/run_blend_ab.py --help
python scripts/summarize_log.py --help
python scripts/suggest_next_experiments.py --help

# 知識ベース更新
python scripts/update_master_report.py

# 次の実験候補を確認
python scripts/suggest_next_experiments.py
```

## Tom-style 実験ループ運用手順

### ステップ 1: EDA・仮説立案

```bash
# 仮説をregistry.csvに登録（手動 or スクリプト）
# experiments/registry.csv を編集して新行を追加
# status=planned で登録
```

### ステップ 2: 実験登録

`experiments/registry.csv` に以下の形式で追記（既存行は変更禁止）：

```csv
exp_id,name,hypothesis,variable_changed,baseline_exp_id,status,cv_score,lb_score,date,notes
0001,sed_baseline,"SEDモデルをベースラインとして確立","model_arch","none","planned","","","2026-05-15",""
```

### ステップ 3: 実験実行

```bash
# 学習スクリプト実行（例）
python train.py --config configs/exp_0001.yaml 2>&1 | tee logs/exp_0001_train.log

# ログ要約
python scripts/summarize_log.py --log logs/exp_0001_train.log --exp-id 0001
```

### ステップ 4: submission監査 & ブレンド

```bash
# submission品質チェック
python scripts/run_blend_ab.py \
    --submission-a submissions/candidates/submission_sed.csv \
    --submission-b submissions/candidates/submission_protossm.csv \
    --sample-submission data/sample_submission.csv \
    --weight-a 0.5 --weight-b 0.5 \
    --output submissions/candidates/submission_blend_50_50.csv

# ブレンド比率スイープ
python scripts/run_blend_ab.py \
    --submission-a submissions/candidates/submission_sed.csv \
    --submission-b submissions/candidates/submission_protossm.csv \
    --sample-submission data/sample_submission.csv \
    --sweep
```

### ステップ 5: 人間レビュー → Kaggle提出

```bash
# candidates/ を確認し、問題なければ手動でsubmit
# !! kaggle competitions submit は自動実行禁止 !!
kaggle competitions submit -c birdclef-2026 \
    -f submissions/candidates/submission_blend_50_50.csv \
    -m "exp_0001: SED baseline blend 50/50"

# 提出後、candidates/ → submitted/ に移動
mv submissions/candidates/submission_blend_50_50.csv submissions/submitted/
```

### ステップ 6: LB結果取り込み

```bash
python scripts/ingest_lb_result.py \
    --exp-id 0001 \
    --lb-score 0.7234 \
    --submission-file submissions/submitted/submission_blend_50_50.csv \
    --note "SED baseline, public LB"
```

### ステップ 7: 知識ベース更新

```bash
python scripts/update_master_report.py
```

### ステップ 8: 次実験提案

```bash
python scripts/suggest_next_experiments.py
# 提案を確認してステップ2へ
```

---

## ディレクトリ構造

```
BirdCLEF_Claude/
├── CLAUDE.md                    # Claude Code向け動作ルール
├── README.md                    # このファイル
├── experiments/
│   └── registry.csv             # 実験レジストリ（追記専用）
├── knowledge/
│   ├── master_report.md         # 累積知識ベース（実験から学んだこと）
│   ├── failed_methods.md        # 失敗した手法（再試行禁止リスト）
│   └── lb_history.md            # LBスコア履歴
├── logs/                        # 実験ログ（上書き禁止）
├── reports/
│   └── experiment/              # 実験レポート（上書き禁止）
│       └── template.md
├── scripts/
│   ├── ingest_lb_result.py      # LB結果の取り込み
│   ├── update_master_report.py  # master_report.md の自動更新
│   ├── summarize_log.py         # ログ要約
│   ├── suggest_next_experiments.py  # 次実験の提案
│   └── run_blend_ab.py          # submission ブレンドA/Bテスト
└── submissions/
    ├── candidates/              # 提出候補（人間レビュー待ち）
    └── submitted/               # 提出済みアーカイブ（上書き禁止）
```

## 重要ルール

| ルール | 内容 |
|--------|------|
| one variable | 1実験で変える変数は1つだけ |
| 上書き禁止 | logs/, submitted/, reports/ は追記のみ |
| 自動submit禁止 | 提出前に必ず人間確認 |
| CV≠LB | ローカルスコアを過信しない |
| hidden test前提 | 過学習に常に注意 |
| 失敗記録 | failed_methods.md に必ず追記 |
| Internet OFF | 提出環境はオフライン前提で実装 |

## submission.csv チェックリスト

提出前に必ず確認：

- [ ] `sample_submission.csv` と列順が完全一致している
- [ ] 行数が一致している
- [ ] NaN / Inf 値がゼロ
- [ ] 全スコアが [0.0, 1.0] の範囲内
- [ ] 種ラベルが公式リストと一致
- [ ] ファイルサイズが妥当（空ファイルでない）
