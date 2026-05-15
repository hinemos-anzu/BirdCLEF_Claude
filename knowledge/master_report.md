# BirdCLEF+ 2026 — Master Knowledge Report

最終更新: 2026-05-15 (submission_audit_20260515)
更新スクリプト: `python scripts/update_master_report.py`

---

## サマリー

| 項目 | 値 |
|------|-----|
| 実験総数 | 0 |
| 完了実験数 | 0 |
| 現在のベストLB | — |
| ベストsubmission | — |
| 最終更新 | 2026-05-15 05:25 |

---

## 現在の最良アーキテクチャ

*(実験完了後に更新)*

---

## 確認済みの有効な手法

*(実験完了後に追記)*

---

## LBスコア推移

詳細は `knowledge/lb_history.md` を参照。

| 実験ID | モデル/手法 | CV | LB | 日付 |
|--------|------------|----|----|------|
| — | — | — | — | — |

---

## データ知見

### 音声データの特性
*(EDA後に追記)*

### クラス分布
*(EDA後に追記)*

### 難しいクラス・混同しやすいペア
*(実験後に追記)*

---

## アーキテクチャ比較

| モデル | 特徴 | CV | LB | 推奨度 |
|--------|------|----|----|--------|
| — | — | — | — | — |

---

## ブレンド・アンサンブル知見

### submission_audit_20260515 (SYNTHETIC DATA — replace with real files)

**実施日**: 2026-05-15
**対象**: SED × ProtoSSM ブレンドスイープ (SED_W ∈ {0.35, 0.38, 0.40, 0.42, 0.45})

#### モデル特性比較

| モデル | max score | cells>0.5 | mean | 特徴 |
|--------|-----------|-----------|------|------|
| SED | 0.786 | 5,450 | 0.008 | 上位20種集中・疎な予測 |
| ProtoSSM | 0.574 | 193 | 0.013 | 広域均一・recall寄り |
| blend(40/60) | 0.556 | 25 | 0.011 | 精度・多様性バランス |

#### ブレンド重み感度

- rank相関: SED比率±0.05調整でSpearman ≥ 0.996（影響小）
- top-1変化率: ±0.02調整で約7%の行、±0.05で約17%の行で最高スコア種が変化
- SED比率を上げるほど最大スコアが上昇（SEDの疎な高スコア成分が強化）
- **推奨baseline**: SED=0.40 / ProtoSSM=0.60

#### 提出監査ルール確認事項

- SED比率 > 0.50 → REJECT (high risk: SEDの過信)
- 全候補のNaN/Inf = 0、列順・行数一致確認必須
- 承認YAMLの `allow_submit: false` は人間のみ変更可

#### 現在の推奨blend

`submissions/candidates/blend_sweep_20260515/submission_blend_sed040_protossm060.csv`
SHA256: `45eab7d37e5ec371f7ce500ab4ddb4864497352b7abdd1f2a34e117c2bcc5455`
(SYNTHETIC DATA — 実ファイルに要更新)

---

## 後処理知見

*(実験後に追記)*

---

## 未解決の疑問点

- [ ] SEDベースとclassificationベースのどちらがBirdCLEFに適しているか？
- [ ] ブレンド重みの最適化はどこまで効くか？
- [ ] hidden testのドメインシフトはどの程度か？

---

## 次の実験候補

`python scripts/suggest_next_experiments.py` を実行して最新の提案を取得。

---

*このファイルは手動編集可。update_master_report.py による自動更新も可。*
