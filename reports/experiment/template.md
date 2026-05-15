# 実験レポート: exp_{EXP_ID} — {EXP_NAME}

**実験ID**: exp_{EXP_ID}  
**実施日**: {DATE}  
**ステータス**: {STATUS}  
**作成者**: Claude Code / {AUTHOR}

---

## 1. 仮説

{HYPOTHESIS}

**one variable チェック**: 今回変更した変数は「{VARIABLE_CHANGED}」のみ。

---

## 2. ベースライン比較

| 項目 | ベースライン (exp_{BASELINE_ID}) | 今回 (exp_{EXP_ID}) | 差分 |
|------|----------------------------------|---------------------|------|
| CV/OOF | — | — | — |
| LB (public) | — | — | — |
| 推論時間 | — | — | — |

---

## 3. 実験設定

```yaml
# 変更したパラメータ・設定
変更項目: {VARIABLE_CHANGED}
変更前: {VALUE_BEFORE}
変更後: {VALUE_AFTER}
```

**固定した条件**:
- モデルアーキテクチャ: {ARCH}
- 学習データ: {TRAIN_DATA}
- 評価方法: {EVAL_METHOD}

---

## 4. 結果

### CVスコア

| fold | score |
|------|-------|
| fold0 | — |
| fold1 | — |
| fold2 | — |
| fold3 | — |
| fold4 | — |
| **mean** | **—** |
| **std** | **—** |

### LBスコア

| public LB | private LB (コンペ後) |
|-----------|----------------------|
| — | — |

### 注意事項

- CV/LB差: —（正 = CVがLBより高い = 過学習傾向）
- CV ≠ LB の解釈: {CV_LB_COMMENT}

---

## 5. 学習曲線・ログ要約

```
# scripts/summarize_log.py の出力をここに貼る
```

---

## 6. エラー・例外

| 種類 | 内容 | 対処 |
|------|------|------|
| — | — | — |

---

## 7. submission監査結果

```
NaN件数: 0
Inf件数: 0
スコア範囲: [0.0, 1.0]
列数: sample_submission.csvと一致 (Yes/No)
行数: sample_submission.csvと一致 (Yes/No)
```

---

## 8. 考察

### 成功した場合
{SUCCESS_ANALYSIS}

### 失敗した場合
{FAILURE_ANALYSIS}

---

## 9. 次のアクション

- [ ] {NEXT_ACTION_1}
- [ ] {NEXT_ACTION_2}

---

## 10. 知識ベースへの反映

- [ ] `knowledge/master_report.md` に追記済み
- [ ] 失敗の場合: `knowledge/failed_methods.md` に追記済み
- [ ] LB提出後: `knowledge/lb_history.md` に追記済み

---

*テンプレート。実際のレポートは `reports/experiment/exp_{EXP_ID}_{EXP_NAME}_{DATE}.md` として保存すること。上書き禁止。*
