# 受け入れテスト結果

**実施日**: 2026-05-15  
**レビュアー**: まとめ役フィードバック対応  
**実施環境**: Claude Code クラウドセッション（Python 3.x）

---

## 総合判定: ✓ 全テスト PASS

| # | テスト内容 | 期待結果 | 実結果 | 判定 |
|---|-----------|---------|--------|------|
| 1 | `init_experiment.py` smoke_test 登録 | registry.csv追記 + events.jsonl追記 + queue/作成 | 全て確認 | ✓ |
| 2 | `watch_experiments.py --once` | エラーなく終了、running/なければ0件 | 正常終了 0件 | ✓ |
| 3 | `suggest_next_experiments.py --exclude-failed` | failed_methods参照、候補3件以上 | sed_baseline等を提案 | ✓ |
| 4 | `validate_submission.py --help` | helpが表示される | 正常表示 | ✓ |
| 5 | `submit_code_competition.py` 承認ファイルなしで失敗 | exit code 1, エラーメッセージ | BLOCKED, exit=1 | ✓ |
| 6 | 承認YAML `allow_submit: false` で失敗 | BLOCKED メッセージ | 1件の検証エラー, exit=1 | ✓ |
| 7 | 承認YAML `allow_submit: true` + SHA256一致でdry-run通過 | 承認ゲート全通過, DRY-RUN | 全✓, exit=0 | ✓ |

---

## テスト詳細

### Test 1: init_experiment.py

```
=== 実験登録: exp_0001 (smoke_test) ===
  仮説      : Tom-style environment smoke test
  変更変数  : none
  ベースライン: exp_none
[OK] registry.csv に exp_0001 を追記しました
[OK] events.jsonl にイベントを記録しました
[OK] queue config: experiments/queue/exp_0001_smoke_test.json
```

確認項目:
- [x] experiments/queue/exp_0001_smoke_test.json が作成された
- [x] experiments/events.jsonl に {"event": "registered", "exp_id": "0001"} が追記された
- [x] experiments/registry.csv に exp_0001 行が追記された（既存行は変更なし）

### Test 2: watch_experiments.py --once

```
[2026-05-15 07:24:06] === BirdCLEF Experiment Watcher 起動 ===
[2026-05-15 07:24:06] 完了判定条件: status.json[status==completed] + metrics.json + stdout.log
[2026-05-15 07:24:06] チェック完了: 0件の完了実験を処理しました
```

確認項目:
- [x] エラーなく終了（exit 0）
- [x] 完了判定条件が明示された
- [x] running/が空の場合は 0件で正常終了

### Test 3: suggest_next_experiments.py --exclude-failed

```
完了済み実験: 0件 | 計画中: 1件
失敗記録キーワード: 5件
[1] sed_baseline (優先度: 10/10) [architecture]
```

確認項目:
- [x] failed_methods.md / knowledge/failed_methods/ を参照
- [x] 候補が優先度順に表示される
- [x] 前提実験未完了の警告が表示される

### Test 4: validate_submission.py --help

確認項目:
- [x] helpが正常表示される
- [x] --sample / --strict-row-order / --quiet オプションあり

### Test 5–7: submit_code_competition.py 承認ゲート

**Test 5（承認ファイルなし → BLOCKED）**:
```
[BLOCKED] 承認ファイルが見つかりません
exit_code=1
```

**Test 6（allow_submit: false → BLOCKED）**:
```
[BLOCKED] 1件の検証エラー:
  1. allow_submit が true ではありません（現在: False）
exit_code=1
```

**Test 7（allow_submit: true + SHA256一致 → dry-run PASS）**:
```
  ✓ allow_submit: true
  ✓ 必須フィールド全て存在
  ✓ submission_csv_sha256 一致
  ✓ 承認日時有効期間内
[OK] 全ての承認ゲートを通過しました
[DRY-RUN] 実際の提出はスキップします。承認ゲートは通過しました。
exit_code=0
```

---

## フィードバック対応状況

| 修正項目 | 実装内容 | 状態 |
|---------|---------|------|
| 1. approval YAML に `allow_submit: true` 必須化 | allow_submit チェック + SHA256検証 + 有効期間チェック | ✓ |
| 2. events.jsonl に成果物 SHA256 記録 | watch_experiments.py で status.json/metrics.json/submission.csv のSHA256・shape を記録 | ✓ |
| 3. watch_experiments.py 完了判定条件の明文化 | status.json[status==completed] + metrics.json + stdout.log | ✓ |
| 4. check_kaggle_parity.py 追加 | 7項目の静的チェック（C01〜C07） | ✓ |
| 5. 受け入れテスト実行 + 本ファイルに保存 | 全7テスト PASS | ✓ |

---

## 残課題（フェーズC・D）

| 項目 | 優先度 | 概要 |
|------|-------|------|
| `push_kaggle_notebook.py` | 高 | notebookをKaggle APIでpushするスクリプト |
| `prepare_model_dataset.py` | 高 | 学習成果物をKaggle Datasetに格納 |
| `build_perch_cache.py` | 中 | frozen Perch embeddingの前計算 |
| `materialize_knowledge_views.py` | 中 | events.jsonlからknowledge snapshotを再構成 |
| `env_fingerprint.py` | 低 | 実行環境のpackage version記録 |
| Kaggle互換Docker最終検証ゲート | 低 | 提出候補ごとに1回実行（ローカルではWSL2不要） |

---

## 次のアクション

フィードバックにある通り、まず **現在の提出物監査** に使うのが適切：

```bash
# 既存submissionの監査
python scripts/validate_submission.py \
    --sample data/sample_submission.csv \
    --submission submission_protossm.csv

python scripts/validate_submission.py \
    --sample data/sample_submission.csv \
    --submission submission_sed.csv

# ブレンド比較
python scripts/run_blend_ab.py \
    --submission-a submission_sed.csv \
    --submission-b submission_protossm.csv \
    --sample-submission data/sample_submission.csv \
    --sweep
```
