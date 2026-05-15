# Submission Audit Report — 2026-05-15 (実ファイル版)

**実施日**: 2026-05-15
**対象コンペ**: BirdCLEF+ 2026
**使用ファイル**: Kaggle Notebook dry-run 出力（実ファイル）

---

## 1. 概要

Kaggle Notebook（tedBirdCLEF+ 2026 Improved / Ensemble v.9）をsubmitモードで実行し、
出力された実ファイルを監査パイプラインで検証した。

**dry-run の制約**: 今回の実行では Kaggle の公開 test soundscape が 3 件のみ。
実際の本番提出では full test set（数千行規模）が対象となる。

---

## 2. 検証対象ファイル一覧

| ファイル | shape | NaN | SHA256 (先頭16) |
|---------|-------|-----|--------|
| `data/sample_submission.csv` | (3, 235) | 0 | `4920b7c5f4a3b3ab...` |
| `submissions/candidates/subm_41.csv` | (3, 235) | 0 | `d9041c7d810ec113...` |
| `submissions/candidates/subm_42.csv` | (3, 235) | 0 | `67e00181ab97d478...` |
| `submissions/candidates/subm_3.csv` | **(240, 235)** | 0 | `6b5910239e37bd4b...` |
| `submissions/candidates/submission_46_buggy.csv` | **(243, 235)** | **56,862** | `0ee04c918f807616...` |
| `submissions/candidates/submission_blend_41_42.csv` | (3, 235) | 0 | `6b367272e4d5f952...` |

SHA256 (フル):
- sample_submission: `4920b7c5f4a3b3ab30a54ee2858b2bfe4de06991a695c30608d9c22d5554d1bd`
- subm_41: `d9041c7d810ec1135197fe7e894905feb70d8ded6af6004cff3871b8dca0798d`
- subm_42: `67e00181ab97d478ecc81e6afdee993279da39104c578c402ab3d50a4544ef01`
- subm_3: `6b5910239e37bd4b7e7de0fa5a001caac1a214c8ec74004f2a6cf69c9005bd37`
- submission_46_buggy: `0ee04c918f807616bff9c418e9c1b39c9abc38c0991d342dd9cbee594fbf4cc7`
- blend_41_42: `6b367272e4d5f952cd84f860dfecc8030a70ccbc6dd0ec4968746e1367046895`

---

## 3. 個別監査結果

### 3.1 subm_41.csv（Model_41 / LightProtoSSM）

| 項目 | 値 |
|------|-----|
| shape | (3, 235) |
| row_id prefix | `BC2026_Test_*` ✓ |
| NaN / Inf | 0 / 0 |
| スコア範囲 | [0.4767, 0.5530] |
| mean / std | 0.5014 / 0.0108 |
| 列順一致 | ✓ |
| 行数一致 | ✓ |
| **総合判定** | **✓ PASS** |

**特性**: スコアが 0.48〜0.55 に集中。234種全体に均等な中スコアを持つ広域予測型。
最高スコア種: `47158son09` (0.553), `47158son12` (0.540)。

### 3.2 subm_42.csv（Model_42 / LightProtoSSM variant）

| 項目 | 値 |
|------|-----|
| shape | (3, 235) |
| row_id prefix | `BC2026_Test_*` ✓ |
| NaN / Inf | 0 / 0 |
| スコア範囲 | [0.4770, 0.5537] |
| mean / std | 0.5015 / 0.0109 |
| 列順一致 | ✓ |
| 行数一致 | ✓ |
| **総合判定** | **✓ PASS** |

**特性**: subm_41と非常に近いスコア分布（同アーキテクチャの別fold）。
最高スコア種: `47158son09` (0.554), `47158son12` (0.540)。

### 3.3 subm_3.csv（Model_3 / ProtoSSM+ResSSM）

| 項目 | 値 |
|------|-----|
| shape | **(240, 235)** |
| row_id prefix | **`BC2026_Train_*` ← 訓練データ** |
| NaN / Inf | 0 / 0 |
| スコア範囲 | [0.0000, 0.9999] |
| mean / std | 0.2451 / 0.2470 |
| 行数一致 | **✗ FAIL（期待: 3, 実際: 240）** |
| **総合判定** | **✗ FAIL** |

**原因**: dry-run モードで Model_3 が訓練用サウンドスケープ（20 ファイル × 12 窓 = 240 行）を
処理した。本番提出時は `BC2026_Test_*` IDで正常動作する見込み。
スコア分布は正常（[0, 1]、mean 0.245、strong sparse peaks あり）。

### 3.4 submission_46_buggy.csv（Ensemble v.9 最終ブレンド）

| 項目 | 値 |
|------|-----|
| shape | **(243, 235)** |
| NaN件数 | **56,862** |
| 行数一致 | **✗ FAIL（期待: 3, 実際: 243）** |
| **総合判定** | **✗ FAIL** |

**根本原因（NaN バグ）**:
ブレンドセルの `direct_add3()` が `set_index("row_id")` で pandas 加算する際、
subm_3（240行: `BC2026_Train_*`）と subm_41/42（3行: `BC2026_Test_*`）のrow_idが
不一致 → outer join → 243行 × 全NaN。

dry-run 固有の問題。本番実行では subm_3 も `BC2026_Test_*` IDを生成するため
ブレンドは正常動作する。

---

## 4. 修正ブレンド（subm_41 + subm_42）

subm_3 が使えないため、subm_41（weight=0.533）+ subm_42（weight=0.433）で
暫定ブレンドを生成。

| 項目 | 値 |
|------|-----|
| shape | (3, 235) |
| NaN / Inf | 0 / 0 |
| スコア範囲 | [0.4769, 0.5533] |
| mean / std | 0.5014 / 0.0109 |
| **総合判定** | **✓ PASS** |

出力: `submissions/candidates/submission_blend_41_42.csv`

---

## 5. バグ分析サマリー

### Bug #1: subm_3 が Train ID を生成（dry-run 限定）

**影響**: dry-run のみ。本番提出では自動修正される。
**推奨対応**: 本番 submit 実行後に subm_3 の row_id prefix を確認すること。

### Bug #2: submission_46 の NaN（Bug #1 の派生）

**影響**: dry-run 出力の submission_46_buggy.csv は提出不可。
**推奨対応**: 本番実行後に再ブレンド。Notebook の `direct_add3()` に row_id 不一致検出を追加推奨。

---

## 6. Notebook 修正推奨

ブレンドセルに以下の防御コードを追加することを推奨（本番実行後の NaN 再発防止）:

```python
# blend後のNaNチェック
nan_count = final_sub[class_list].isna().sum().sum()
assert nan_count == 0, f"BLEND BUG: {nan_count} NaN values detected. Check row_id alignment."
# 行数チェック
assert len(final_sub) == len(sample_sub), \
    f"BLEND BUG: row count mismatch. got={len(final_sub)}, expected={len(sample_sub)}"
```

---

## 7. 次のアクション

| 優先度 | アクション |
|-------|-----------|
| 高 | Kaggle Notebook を **フル submit モード**で実行（全 test soundscape） |
| 高 | 本番実行後: subm_3 の行数・row_id prefix を確認 |
| 高 | 本番実行後: `validate_submission.py --sample ... --submission submission.csv` で監査 |
| 中 | Notebook ブレンドセルに NaN/行数アサーションを追加 |
| 低 | LBスコア取得後: `python scripts/ingest_lb_result.py --exp-id 0002 --lb-score <スコア>` |
