# BirdCLEF+ 2026 — Claude Code Experiment Environment

## プロジェクト概要

BirdCLEF+ 2026 Kaggleコンペティション用のTom-style実験管理システム。
EDA → 実験キュー → 実験実行 → ログ監視 → レポート → 知識更新 → 次実験提案 → 提出候補生成 の循環を管理する。

## ディレクトリ構造

```
BirdCLEF_Claude/
├── CLAUDE.md                    # このファイル（Claude Code向け指示書）
├── README.md                    # 運用手順
├── experiments/
│   └── registry.csv             # 実験レジストリ（上書き禁止・追記のみ）
├── knowledge/
│   ├── master_report.md         # 累積知識ベース
│   ├── failed_methods.md        # 失敗した手法一覧
│   └── lb_history.md            # LBスコア履歴
├── logs/                        # 実験ログ（上書き禁止）
├── reports/
│   └── experiment/              # 実験レポート（上書き禁止）
│       └── template.md
├── scripts/
│   ├── ingest_lb_result.py      # LB結果の取り込み
│   ├── update_master_report.py  # master_report.md の更新
│   ├── summarize_log.py         # ログ要約
│   ├── suggest_next_experiments.py  # 次実験の提案
│   └── run_blend_ab.py          # submission ブレンドA/Bテスト
└── submissions/
    ├── candidates/              # 提出候補（レビュー待ち）
    └── submitted/               # 提出済み（上書き禁止）
```

## 厳守ルール（Claude Codeが必ず守ること）

### 実験設計
- **one experiment, one variable**: 1実験で変更するのは1変数のみ
- **ベースライン比較必須**: 全実験でベースラインとの差分を記録する
- **CV/OOF ≠ LB**: ローカルAUCをLBの代替と断定しない。傾向参考に留める

### ファイル管理
- **上書き禁止**: `logs/`, `submissions/submitted/`, `reports/experiment/` のファイルは絶対に上書き・削除しない
- **命名規則**: `exp_{id:04d}_{name}_{YYYYMMDD}.{ext}` 形式を守る
- **registry.csv**: 追記専用。既存行の変更禁止

### Kaggle提出
- **人間確認必須**: 提出前に必ず `submissions/candidates/` に置いてユーザー確認を取る
- **自動submit禁止**: `kaggle competitions submit` を自動実行しない
- **submission監査**: NaN/Inf チェック、sample_submission.csv との列順一致確認を必ず行う
- **Internet OFF対応**: 提出環境はオフライン。外部ダウンロードに依存するコードを書かない

### 知識管理
- **失敗記録**: 失敗した手法は必ず `knowledge/failed_methods.md` に追記する
- **繰り返し禁止**: `failed_methods.md` に記載済みの手法を再提案しない
- **hidden test前提**: 訓練データの過学習に注意。ローカルスコアを過信しない

## Tom-style実験ループ

```
1. EDA / 仮説立案
2. experiments/registry.csv に実験を登録 (status=planned)
3. 実験実行 → logs/ に記録
4. scripts/summarize_log.py でログ要約
5. reports/experiment/ にレポート作成
6. scripts/update_master_report.py で知識更新
7. LB提出後 → scripts/ingest_lb_result.py でLB結果取り込み
8. scripts/suggest_next_experiments.py で次実験提案
9. 1に戻る
```

## よく使うコマンド

```bash
# 実験登録
python scripts/suggest_next_experiments.py

# LB結果取り込み
python scripts/ingest_lb_result.py --exp-id 0001 --lb-score 0.7234 --note "SED baseline"

# master_report 更新
python scripts/update_master_report.py

# submission監査 & ブレンド
python scripts/run_blend_ab.py --help
```

## submission.csv 品質基準

- `sample_submission.csv` と列順・行数完全一致
- NaN, Inf 値ゼロ
- 全スコア値 [0.0, 1.0] の範囲内
- 種ラベルは公式リストと完全一致

## モデル・実験メモ

実験の知見は必ず `knowledge/master_report.md` に追記すること。
失敗した場合は `knowledge/failed_methods.md` にも追記。
LBスコアは `knowledge/lb_history.md` で一元管理。
